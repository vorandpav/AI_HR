import io
import os

from minio import Minio
from minio.deleteobjects import DeleteObject
from minio.error import S3Error

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minio")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minio123")
MINIO_SECURE = os.getenv("MINIO_SECURE", "false").lower() in ("1", "true", "yes")
DEFAULT_BUCKET = os.getenv("MINIO_BUCKET", "audio")


class MinioClient:
    def __init__(self):
        self.client = Minio(
            MINIO_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=MINIO_SECURE,
        )
        # --- БОЛЕЕ НАДЁЖНЫЙ БЛОК ---
        try:
            # Проверяем, существует ли бакет.
            if not self.client.bucket_exists(DEFAULT_BUCKET):
                # Если нет, пытаемся создать.
                self.client.make_bucket(DEFAULT_BUCKET)
        except S3Error as e:
            # Если при создании бакета возникла ошибка 'BucketAlreadyOwnedByYou',
            # игнорируем ее, так как это ожидаемое поведение в конкурентной среде.
            if e.code == "BucketAlreadyOwnedByYou":
                pass
            else:
                # Если ошибка другая, то это реальная проблема, и ее нужно пробросить дальше.
                raise

    def put_bytes(
        self,
        object_name: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ):
        data_io = io.BytesIO(data)
        data_io.seek(0)
        self.client.put_object(
            bucket_name=DEFAULT_BUCKET,
            object_name=object_name,
            data=data_io,
            length=len(data),
            content_type=content_type,
        )

    # --- ДОБАВЛЕННЫЙ МЕТОД ---
    def delete_objects(self, object_names: list):
        """Массово удаляет объекты из бакета."""
        if not object_names:
            return

        delete_object_list = [DeleteObject(name) for name in object_names]
        errors = self.client.remove_objects(DEFAULT_BUCKET, delete_object_list)

        error_count = 0
        for error in errors:
            error_count += 1
            # Логируем ошибки, но не прерываем процесс
            print(f"Error occurred when deleting object {error.object_name}: {error}")

        if error_count > 0:
            # Можно добавить более серьезное логирование или обработку
            print(f"Encountered {error_count} errors during object deletion.")

    def presigned_get(self, object_name: str, expires=3600):
        return self.client.presigned_get_object(DEFAULT_BUCKET, object_name)


_minio_client = None


def get_minio_client():
    global _minio_client
    if _minio_client is None:
        _minio_client = MinioClient()
    return _minio_client
