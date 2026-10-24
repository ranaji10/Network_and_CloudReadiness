from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path


class LocalBlobStore:
    name = "local"

    def __init__(self, root: Path):
        self.root = root.expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if self.root not in p.parents and p != self.root:
            raise PermissionError("Key escapes blob store root")
        return p

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        p = self._path(key)
        if p == self.root:
            raise PermissionError("Key must name a file inside the store")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return f"file://{p}"

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def list(self, prefix: str = "") -> Iterable[str]:
        """Keys (posix, relative to the root) whose path starts with `prefix`."""
        base = self._path(prefix) if prefix else self.root
        start = base if base.is_dir() else base.parent
        if not start.exists():
            return []
        keys = [p.relative_to(self.root).as_posix() for p in start.rglob("*") if p.is_file()]
        return sorted(k for k in keys if k.startswith(prefix))

    def delete(self, key: str) -> None:
        p = self._path(key)
        if p.is_file():
            p.unlink()
        parent = p.parent
        while parent != self.root and parent.exists() and not any(parent.iterdir()):
            parent.rmdir()
            parent = parent.parent
