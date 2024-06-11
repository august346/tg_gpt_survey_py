import io
import os
import uuid

from minio import Minio, S3Error

MINIO_URL = os.environ['MINIO_URL']
MINIO_ACCESS_KEY = os.environ['MINIO_ACCESS_KEY']
MINIO_SECRET_KEY = os.environ['MINIO_SECRET_KEY']

MINIO_BUCKET_NAME = os.environ['MINIO_BUCKET_NAME']


class MinioClient:
    def __init__(self):
        self._client = Minio(
            MINIO_URL,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=False
        )

    def create_buckets(self):
        for name in (MINIO_BUCKET_NAME,):
            if not self._client.bucket_exists(name):
                self._client.make_bucket(name)

    def save(self, file_name: str, data: bytes, content_type: str, size: int) -> str:
        key: str = f"{uuid.uuid4()}_{file_name}"

        self._client.put_object(
            bucket_name=MINIO_BUCKET_NAME,
            object_name=key,
            data=io.BytesIO(data),
            length=size,
            content_type=content_type
        )

        return key

    def get(self, key: str):
        try:
            return self._client.get_object(MINIO_BUCKET_NAME, key)
        except S3Error:
            return None
