from __future__ import annotations

import mimetypes
from collections.abc import Iterable

from readiness.models import DocumentRef


class GCSSource:
    """Google Cloud Storage prefix as a document source. Requires `readiness[gcp]`."""

    name = "gcs"

    def __init__(self, bucket: str, prefix: str = "", project: str | None = None, max_bytes: int = 25 * 1024 * 1024):
        from google.cloud import storage  # lazy: optional dependency

        self._client = storage.Client(project=project)
        self._bucket = self._client.bucket(bucket)
        self.bucket, self.prefix, self.max_bytes = bucket, prefix, max_bytes

    def list(self) -> Iterable[DocumentRef]:
        for blob in self._client.list_blobs(self.bucket, prefix=self.prefix or None):
            if blob.name.endswith("/") or (blob.size or 0) > self.max_bytes:
                continue
            uri = f"gs://{self.bucket}/{blob.name}"
            yield DocumentRef(
                id=DocumentRef.make_id(uri),
                name=blob.name.removeprefix(self.prefix).lstrip("/"),
                uri=uri,
                source=self.name,
                mime=blob.content_type or mimetypes.guess_type(blob.name)[0],
                size_bytes=blob.size,
                sha256=None,
            )

    def read(self, ref: DocumentRef) -> bytes:
        name = ref.uri.removeprefix(f"gs://{self.bucket}/")
        return self._bucket.blob(name).download_as_bytes()
