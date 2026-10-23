from __future__ import annotations


class S3BlobStore:
    name = "s3"

    def __init__(self, bucket: str, region: str | None = None):
        import boto3

        self._s3 = boto3.client("s3", region_name=region)
        self.bucket = bucket

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        self._s3.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)
        return f"s3://{self.bucket}/{key}"

    def get(self, key: str) -> bytes:
        return self._s3.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def exists(self, key: str) -> bool:
        try:
            self._s3.head_object(Bucket=self.bucket, Key=key)
            return True
        except self._s3.exceptions.ClientError:
            return False
