import io
import uuid
from datetime import timedelta

from minio import Minio
from minio.error import S3Error

from app.config import settings

_client: Minio | None = None


def get_minio_client() -> Minio:
    global _client
    if _client is None:
        _client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
    return _client


def ensure_buckets() -> None:
    client = get_minio_client()
    for bucket in (settings.minio_bucket_recordings, settings.minio_bucket_processed):
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)


def upload_audio(file_bytes: bytes, original_filename: str, content_type: str) -> str:
    client = get_minio_client()
    ensure_buckets()

    ext = original_filename.rsplit(".", 1)[-1].lower()
    object_key = f"{uuid.uuid4()}.{ext}"

    client.put_object(
        bucket_name=settings.minio_bucket_recordings,
        object_name=object_key,
        data=io.BytesIO(file_bytes),
        length=len(file_bytes),
        content_type=content_type,
    )
    return object_key


def get_presigned_url(object_key: str, expires_hours: int = 2) -> str:
    client = get_minio_client()
    return client.presigned_get_object(
        bucket_name=settings.minio_bucket_recordings,
        object_name=object_key,
        expires=timedelta(hours=expires_hours),
    )


def delete_audio(object_key: str) -> None:
    client = get_minio_client()
    try:
        client.remove_object(settings.minio_bucket_recordings, object_key)
    except S3Error:
        pass
