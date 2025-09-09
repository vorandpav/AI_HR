# backend/services/audio_store.py
import logging
import time
import uuid
from typing import Dict

from .. import database, models
from .minio_client import get_minio_client

logger = logging.getLogger("uvicorn.error")


def save_audio_chunk_sync(
    data: bytes, session_id: str, role: str, content_type: str = "audio/webm"
) -> Dict:
    """
    Синхронная функция: сохраняет байты аудио в MinIO и создает запись AudioObject в БД.
    Вызывается через anyio.to_thread.run_sync.

    Args:
        data: Байты аудио данных.
        session_id: Уникальный идентификатор сессии звонка.
        role: Роль отправителя ('participant' или 'bot').
        content_type: MIME-тип аудио файла.
    """
    if not data:
        logger.warning(
            f"Attempted to save empty audio chunk for session {session_id}, role {role}"
        )
        return None

    logger.debug(
        f"Saving audio chunk: {len(data)} bytes, session_id: {session_id}, role: {role}, content_type: {content_type}"
    )

    try:
        minio = get_minio_client()
        ts = int(time.time() * 1000)
        # Используем роль в имени объекта для будущего удобства
        object_name = f"calls/{session_id}/{role}_{ts}_{uuid.uuid4().hex}.webm"

        # положить в minio
        minio.put_bytes(object_name, data, content_type=content_type)
        logger.info(f"Audio chunk saved to MinIO: {object_name}")

        # записать метаданные в БД (синхронно)
        db = database.SessionLocal()
        try:
            ao = models.AudioObject(
                session_id=session_id,
                object_key=object_name,
                role=role,  # Сохраняем роль
                duration_sec=None,  # Пока не определяем
                size_bytes=len(data),
                is_final=False,  # Чанк, не финальный файл
            )
            db.add(ao)
            db.commit()
            db.refresh(ao)
            logger.debug(f"AudioObject record created in DB: ID {ao.id}")
            return {
                "id": ao.id,
                "object_key": ao.object_key,
                "size_bytes": ao.size_bytes,
                "created_at": ao.created_at,
                "role": ao.role,
            }
        finally:
            db.close()
    except Exception as e:
        logger.exception(
            "Failed to save audio chunk (session_id=%s, role=%s): %s",
            session_id,
            role,
            e,
        )
        raise  # Перебрасываем исключение, чтобы вызывающая функция могла обработать ошибку
