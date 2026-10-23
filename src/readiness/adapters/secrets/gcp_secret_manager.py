from __future__ import annotations

import os


class GCPSecretManagerStore:
    """Reads `projects/<project>/secrets/<KEY>/versions/latest`; falls back to env for local overrides."""

    name = "gcp-secret-manager"

    def __init__(self, project: str):
        from google.cloud import secretmanager

        self._client = secretmanager.SecretManagerServiceClient()
        self.project = project

    def get(self, key: str) -> str | None:
        if os.environ.get(key):
            return os.environ[key]
        try:
            name = f"projects/{self.project}/secrets/{key}/versions/latest"
            return self._client.access_secret_version(name=name).payload.data.decode()
        except Exception:  # noqa: BLE001 - missing secret is a normal condition
            return None
