from __future__ import annotations

from collections.abc import Iterable


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

    def list(self, prefix: str = "") -> Iterable[str]:
        return [b.name for b in self._bucket.client.list_blobs(self.bucket, prefix=prefix or None)]

    def delete(self, key: str) -> None:
        self._bucket.blob(key).delete()
