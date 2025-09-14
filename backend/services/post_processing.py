import asyncio
import logging
import os
import tempfile
from typing import Dict, List

import ffmpeg
from sqlalchemy.orm import Session

from .. import database, models
from .minio_client import BUCKET_NAME, get_minio_client

logger = logging.getLogger("uvicorn.error")


# --- НОВЫЕ ФУНКЦИИ ДЛЯ ОЧИСТКИ ---


def _cleanup_temp_files(files: List[str]):
    """Удаляет список временных файлов с диска."""
    for path in files:
        try:
            if os.path.exists(path):
                os.unlink(path)
                logger.debug(f"Deleted temp file {path}")
        except OSError as e:
            logger.warning(f"Could not delete temp file {path}: {e}")


def _cleanup_source_data(object_keys: List[str], object_ids: List[int]):
    """Удаляет исходные чанки из MinIO и записи из БД."""
    # 1. Удаление из MinIO
    try:
        minio_client = get_minio_client()
        minio_client.delete_objects(object_keys)
        logger.info(f"Deleted {len(object_keys)} source chunks from MinIO.")
    except Exception as e:
        logger.error(f"Error deleting source chunks from MinIO: {e}")

    # 2. Удаление из БД
    db: Session = database.SessionLocal()
    try:
        if object_ids:
            db.query(models.AudioObject).filter(
                models.AudioObject.id.in_(object_ids)
            ).delete(synchronize_session=False)
            db.commit()
            logger.info(
                f"Deleted {len(object_ids)} source AudioObject records from DB."
            )
    except Exception as e:
        logger.error(f"Error deleting source AudioObject records from DB: {e}")
        db.rollback()
    finally:
        db.close()


# --- СУЩЕСТВУЮЩИЕ, НО МОДИФИЦИРОВАННЫЕ ФУНКЦИИ ---


async def _download_audio_object_bytes(object_key: str) -> bytes:
    """Асинхронно скачивает байты аудио объекта из MinIO."""
    loop = asyncio.get_event_loop()

    def _sync_get():
        minio_client = get_minio_client()
        response = minio_client.client.get_object(
            bucket_name=BUCKET_NAME, object_name=object_key  # ИСПРАВЛЕНО
        )
        return response.read()

    try:
        data = await loop.run_in_executor(None, _sync_get)
        logger.debug(f"Downloaded {len(data)} bytes from MinIO object {object_key}")
        return data
    except Exception as e:
        logger.error(f"Error downloading object {object_key} from MinIO: {e}")
        raise


def _concatenate_audio_files(input_files: List[str], output_file: str):
    """
    Объединяет (конкатенирует) список аудио файлов в один с помощью concat фильтра.
    Этот метод более надежен на Windows, так как не использует внешний текстовый файл.
    """
    if not input_files:
        logger.warning("No input files provided for concatenation.")
        return

    logger.info(
        f"Starting FFmpeg concatenation of {len(input_files)} files into {output_file}"
    )
    try:
        # Если файл один, просто копируем его, чтобы не вызывать сложную логику FFmpeg.
        if len(input_files) == 1:
            ffmpeg.input(input_files[0]).output(
                output_file, acodec="copy"
            ).overwrite_output().run(quiet=True)
            logger.info(f"Successfully copied single audio file to {output_file}")
            return

        # Создаем список входных потоков для FFmpeg
        input_streams = [ffmpeg.input(f) for f in input_files]

        # Используем concat ФИЛЬТР для объединения всех потоков.
        # v=0 (video=0), a=1 (audio=1) - говорим, что на выходе должен быть один аудиопоток.
        concatenated_stream = ffmpeg.concat(*input_streams, v=0, a=1)

        # Запускаем процесс. Используем 'copy' кодек, так как исходные файлы уже в webm.
        (
            ffmpeg.output(concatenated_stream, output_file, acodec="copy")
            .overwrite_output()
            .run(quiet=True)
        )

        logger.info(f"Successfully concatenated audio files into {output_file}")
    except ffmpeg.Error as e:
        # Логируем stderr от ffmpeg для детальной диагностики в случае будущих проблем
        stderr_output = (
            e.stderr.decode("utf8", errors="ignore") if e.stderr else "No stderr"
        )
        logger.error(f"FFmpeg error during concatenation: {stderr_output}")
        raise


# --- НОВАЯ ФУНКЦИЯ ДЛЯ СМЕШИВАНИЯ ---
def _mix_audio_tracks_ffmpeg(track_files: List[str], output_file: str):
    """
    Смешивает (микширует) несколько аудио дорожек в одну.
    """
    if not track_files:
        logger.warning("No track files provided for mixing.")
        return

    if len(track_files) == 1:
        logger.warning("Only one track provided. Copying instead of mixing.")
        ffmpeg.input(track_files[0]).output(
            output_file, acodec="libopus", audio_bitrate="128k"
        ).overwrite_output().run(quiet=True)
        return

    logger.info(f"Starting FFmpeg mix of {len(track_files)} tracks into {output_file}")
    try:
        inputs = [ffmpeg.input(f) for f in track_files]
        # Используем фильтр amix для смешивания дорожек
        mixed_audio = ffmpeg.filter(
            inputs, "amix", inputs=len(inputs), duration="longest"
        )

        (
            ffmpeg.output(
                mixed_audio, output_file, acodec="libopus", audio_bitrate="128k"
            )
            .overwrite_output()
            .run(quiet=True)
        )
        logger.info(f"Successfully mixed tracks into {output_file}")
    except ffmpeg.Error as e:
        logger.error(
            f"FFmpeg error during mixing: {e.stderr.decode('utf8') if e.stderr else 'No stderr'}"
        )
        raise


def _save_final_file_and_update_db(meeting_id: int, session_id: str, file_path: str):
    """Сохраняет финальный файл в MinIO и обновляет БД."""
    # 1. Сохранение в MinIO
    final_object_name = f"recordings/meeting_{meeting_id}/final_recording.ogg"
    with open(file_path, "rb") as f:
        file_data = f.read()

    minio_client = get_minio_client()
    minio_client.put_bytes(
        object_name=final_object_name, data=file_data, content_type="audio/ogg"
    )
    logger.info(f"Final merged audio saved to MinIO: {final_object_name}")

    # 2. Обновление БД
    db: Session = database.SessionLocal()
    try:
        ao = models.AudioObject(
            session_id=session_id,
            meeting_id=meeting_id,
            object_key=final_object_name,
            role="merged",
            size_bytes=len(file_data),
            is_final=True,
        )
        db.add(ao)
        db.commit()
        logger.info(
            f"Final AudioObject record created in DB for key {final_object_name}"
        )
    except Exception as e:
        logger.error(f"Error updating DB with final recording info: {e}")
        db.rollback()
        raise
    finally:
        db.close()

    return final_object_name


# --- ОСНОВНАЯ ФУНКЦИЯ, ПОЛНОСТЬЮ ПЕРЕРАБОТАНА ---
async def process_and_merge_audio(meeting_id: int, session_id: str):
    """
    Асинхронная функция для обработки и смешивания аудио записей после звонка.
    Финальная версия, использующая конкатенацию байтов перед обработкой в FFmpeg.
    """
    logger.info(
        f"Starting post-processing for meeting {meeting_id}, session {session_id}"
    )

    db: Session = database.SessionLocal()
    all_temp_files = []
    source_object_keys = []
    source_object_ids = []

    try:
        # 1. Получаем все аудио чанки для сессии
        audio_objects = (
            db.query(models.AudioObject)
            .filter(
                models.AudioObject.session_id == session_id,
                models.AudioObject.is_final == False,
            )
            .order_by(models.AudioObject.created_at)
            .all()
        )

        if not audio_objects:
            logger.warning(
                f"No audio chunks found for session {session_id}. Aborting post-processing."
            )
            return

        logger.info(f"Found {len(audio_objects)} audio chunks for session {session_id}")
        source_object_keys = [ao.object_key for ao in audio_objects]
        source_object_ids = [ao.id for ao in audio_objects]

        # 2. Разделяем чанки по ролям
        chunks_by_role: Dict[str, List[models.AudioObject]] = {
            "participant": [],
            "bot": [],
        }
        for ao in audio_objects:
            if ao.role in chunks_by_role:
                chunks_by_role[ao.role].append(ao)

        # 3. Обрабатываем каждую роль: скачиваем и КОНКАТЕНИРУЕМ БАЙТЫ в один файл
        concatenated_tracks = []
        for role, chunks in chunks_by_role.items():
            if not chunks:
                continue

            logger.info(f"Processing {len(chunks)} chunks for role '{role}'")

            # Скачиваем все чанки для текущей роли
            download_tasks = [
                _download_audio_object_bytes(chunk.object_key) for chunk in chunks
            ]
            chunks_data = await asyncio.gather(*download_tasks)

            # --- ГЛАВНОЕ ИЗМЕНЕНИЕ ---
            # Создаем ОДИН временный файл для всей дорожки и пишем в него все байты подряд.
            if any(chunks_data):
                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=f"_{role}_track.webm"
                ) as track_file:
                    for data in chunks_data:
                        if data:
                            track_file.write(data)

                    track_path = track_file.name
                    logger.info(
                        f"Created single concatenated track for role '{role}' at {track_path}"
                    )

                concatenated_tracks.append(track_path)
                all_temp_files.append(track_path)
            else:
                logger.warning(f"No data found for role '{role}' after download.")

        # 4. Смешиваем (микшируем) полученные дорожки
        if not concatenated_tracks:
            logger.warning("No audio tracks were created for mixing. Aborting.")
            return

        with tempfile.NamedTemporaryFile(
            delete=False, suffix="_final_mixed.ogg"
        ) as final_output_file:
            final_output_path = final_output_file.name
        all_temp_files.append(final_output_path)

        _mix_audio_tracks_ffmpeg(concatenated_tracks, final_output_path)

        # 5. Сохраняем финальный файл в MinIO и обновляем БД
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            _save_final_file_and_update_db,
            meeting_id,
            session_id,
            final_output_path,
        )
        logger.info(
            f"Successfully mixed and saved final recording for session {session_id}"
        )

        # 6. Очистка исходных данных (чанки в MinIO и записи в БД)
        await loop.run_in_executor(
            None, _cleanup_source_data, source_object_keys, source_object_ids
        )

    except Exception as e:
        logger.exception(
            f"Critical error during post-processing for meeting {meeting_id}: {e}"
        )
    finally:
        # 7. Гарантированная очистка временных файлов на диске
        _cleanup_temp_files(all_temp_files)
        db.close()
        logger.info(
            f"Post-processing finished for meeting {meeting_id}, session {session_id}"
        )
