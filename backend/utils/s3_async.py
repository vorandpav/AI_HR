import os

import aioboto3

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minio")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minio123")
AUDIO_BUCKET = os.getenv("AUDIO_BUCKET", "aihr-audio")

_session = None


def _get_session():
    global _session
    if _session is None:
        _session = aioboto3.Session()
    return _session


async def ensure_bucket():
    session = _get_session()
    async with session.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
    ) as s3:
        try:
            await s3.head_bucket(Bucket=AUDIO_BUCKET)
        except Exception:
            # create bucket (simple, not region-aware)
            await s3.create_bucket(Bucket=AUDIO_BUCKET)


async def upload_bytes(
    key: str, data: bytes, content_type: str = "application/octet-stream"
):
    session = _get_session()
    async with session.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
    ) as s3:
        await s3.put_object(
            Bucket=AUDIO_BUCKET, Key=key, Body=data, ContentType=content_type
        )
    return key


async def generate_presigned_url(key: str, expires: int = 3600):
    session = _get_session()
    async with session.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
    ) as s3:
        url = await s3.generate_presigned_url(
            "get_object", Params={"Bucket": AUDIO_BUCKET, "Key": key}, ExpiresIn=expires
        )
        return url
