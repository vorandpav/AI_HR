import logging
import uuid
import time
from typing import Tuple

from fastapi import UploadFile
from sqlalchemy.orm import Session

from .. import models
from .minio_client import get_minio_client

logger = logging.getLogger("uvicorn.error")

BUCKET_FOLDERS = {
    "vacancy": "vacancies",
    "resume": "resumes",
    "audio_chunk": "audio-chunks",
    "final_recording": "final-recordings",
}


def save_document(
        db: Session,
        file: UploadFile,
        file_type: str,
        record: models.Vacancy | models.Resume,
) -> None:
    """
    Сохраняет документ (вакансию или резюме) в MinIO и обновляет запись.
    """
    folder = BUCKET_FOLDERS.get(file_type)
    if not folder:
        raise ValueError(f"Unknown file type for document: {file_type}")

    file_extension = file.filename.split(".")[-1] if "." in file.filename else "file"
    object_key = f"{folder}/{record.id}/{uuid.uuid4().hex}.{file_extension}"

    minio = get_minio_client()
    file_content = file.file.read()

    minio.put_bytes(object_key, file_content, content_type=file.content_type)
    logger.info(f"Document '{file.filename}' saved to MinIO as '{object_key}'")

    record.object_key = object_key
    db.flush([record])


def save_audio_chunk(
        db: Session,
        data: bytes,
        session_id: str,
        role: str,
        content_type: str = "audio/webm",
) -> models.AudioObject:
    """
    Сохраняет аудио-чанк в MinIO и создает запись в базе данных.
    """
    if not data:
        logger.warning(f"Attempted to save empty audio chunk for session {session_id}")
        return None

    folder = BUCKET_FOLDERS["audio_chunk"]
    ts = int(time.time() * 1000)
    object_key = f"{folder}/{session_id}/{role}_{ts}_{uuid.uuid4().hex}.webm"

    minio = get_minio_client()
    minio.put_bytes(object_key, data, content_type=content_type)
    logger.info(f"Audio chunk saved to MinIO: {object_key}")

    audio_obj = models.AudioObject(
        session_id=session_id,
        object_key=object_key,
        role=role,
        size_bytes=len(data),
        is_final=False,
    )
    db.add(audio_obj)
    db.commit()
    db.refresh(audio_obj)

    return audio_obj


def get_file(object_key: str) -> Tuple[bytes, str]:
    """
    Получает файл из MinIO по ключу объекта.
    """
    minio = get_minio_client()
    response = minio.get_object(object_key)
    content_type = response.headers.get("Content-Type", "application/octet-stream")
    return response.read(), content_type
