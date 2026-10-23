from __future__ import annotations

import os


class AWSSecretsManagerStore:
    name = "aws-secrets-manager"

    def __init__(self, region: str | None = None):
        import boto3

        self._client = boto3.client("secretsmanager", region_name=region)

    def get(self, key: str) -> str | None:
        if os.environ.get(key):
            return os.environ[key]
        try:
            return self._client.get_secret_value(SecretId=key).get("SecretString")
        except Exception:  # noqa: BLE001
            return None
