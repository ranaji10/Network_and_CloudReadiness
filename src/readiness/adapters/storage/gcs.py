from __future__ import annotations


class GCSBlobStore:
    name = "gcs"

    def __init__(self, bucket: str, project: str | None = None):
        from google.cloud import storage

        self._bucket = storage.Client(project=project).bucket(bucket)
        self.bucket = bucket

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        self._bucket.blob(key).upload_from_string(data, content_type=content_type)
        return f"gs://{self.bucket}/{key}"

    def get(self, key: str) -> bytes:
        return self._bucket.blob(key).download_as_bytes()

    def exists(self, key: str) -> bool:
        return self._bucket.blob(key).exists()
