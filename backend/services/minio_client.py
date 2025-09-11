import io
import os
import logging

from minio import Minio
from minio.deleteobjects import DeleteObject
from minio.error import S3Error

logger = logging.getLogger("uvicorn.error")

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minio")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minio123")
MINIO_SECURE = os.getenv("MINIO_SECURE", "false").lower() in ("true", "yes")
DEFAULT_BUCKET = os.getenv("MINIO_BUCKET", "hr-bucket")


class MinioClient:
    """Синглтон-клиент для работы с MinIO."""

    def __init__(self):
        self.client = Minio(
            MINIO_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=MINIO_SECURE,
        )
        self.bucket_name = DEFAULT_BUCKET
        self._ensure_bucket()

    def _ensure_bucket(self):
        """Проверяет наличие бакета при старте и создает его, если необходимо."""
        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
                logger.info(f"MinIO bucket '{self.bucket_name}' created.")
        except S3Error as e:
            if e.code == "BucketAlreadyOwnedByYou":
                pass  # Бакет уже существует, все в порядке.
            else:
                logger.exception("Failed to ensure MinIO bucket")
                raise

    def put_bytes(self, object_name: str, data: bytes, content_type: str):
        """Загружает байты в MinIO."""
        data_io = io.BytesIO(data)
        self.client.put_object(
            bucket_name=self.bucket_name,
            object_name=object_name,
            data=data_io,
            length=len(data),
            content_type=content_type,
        )

    def get_object(self, object_name: str):
        """Возвращает объект ответа MinIO, из которого можно прочитать данные."""
        return self.client.get_object(self.bucket_name, object_name)

    def delete_objects(self, object_names: list):
        """Массово удаляет объекты из MinIO."""
        if not object_names:
            return
        delete_object_list = [DeleteObject(name) for name in object_names]
        errors = self.client.remove_objects(self.bucket_name, delete_object_list)
        for error in errors:
            logger.error(f"Error deleting object {error.object_name} from MinIO: {error}")

    def presigned_get(self, object_name: str, expires: int = 3600) -> str:
        """Генерирует временную ссылку для скачивания объекта."""
        return self.client.presigned_get_object(self.bucket_name, object_name, expires=expires)


_minio_client = None


def get_minio_client() -> MinioClient:
    """Возвращает единственный экземпляр MinioClient."""
    global _minio_client
    if _minio_client is None:
        _minio_client = MinioClient()
    return _minio_client
