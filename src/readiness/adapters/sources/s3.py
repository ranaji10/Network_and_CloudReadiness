from __future__ import annotations

import mimetypes
from collections.abc import Iterable

from readiness.models import DocumentRef


class S3Source:
    """Amazon S3 prefix as a document source. Requires `readiness[aws]`. Untested against a live account."""

    name = "s3"

    def __init__(self, bucket: str, prefix: str = "", region: str | None = None, max_bytes: int = 25 * 1024 * 1024):
        import boto3  # lazy: optional dependency

        self._s3 = boto3.client("s3", region_name=region)
        self.bucket, self.prefix, self.max_bytes = bucket, prefix, max_bytes

    def list(self) -> Iterable[DocumentRef]:
        paginator = self._s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=self.prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if key.endswith("/") or obj.get("Size", 0) > self.max_bytes:
                    continue
                uri = f"s3://{self.bucket}/{key}"
                yield DocumentRef(
                    id=DocumentRef.make_id(uri),
                    name=key.removeprefix(self.prefix).lstrip("/"),
                    uri=uri,
                    source=self.name,
                    mime=mimetypes.guess_type(key)[0],
                    size_bytes=obj.get("Size"),
                )

    def read(self, ref: DocumentRef) -> bytes:
        key = ref.uri.removeprefix(f"s3://{self.bucket}/")
        return self._s3.get_object(Bucket=self.bucket, Key=key)["Body"].read()
