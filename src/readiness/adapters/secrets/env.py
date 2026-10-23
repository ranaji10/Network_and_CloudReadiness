from __future__ import annotations

import os


class EnvSecretStore:
    """Local development only. Production deployments use a platform secret manager."""

    name = "env"

    def get(self, key: str) -> str | None:
        return os.environ.get(key) or None
