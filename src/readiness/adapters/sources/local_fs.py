from __future__ import annotations

import hashlib
import mimetypes
from collections.abc import Iterable
from pathlib import Path

from readiness.models import DocumentRef

SKIP_DIRS = {".git", "node_modules", ".venv", "__pycache__", ".terraform"}


class LocalFolderSource:
    """Reads a local folder recursively. Refuses to escape its root (symlinks resolved and checked)."""

    name = "local"

    def __init__(self, root: Path, max_bytes: int = 25 * 1024 * 1024):
        self.root = root.expanduser().resolve()
        if not self.root.is_dir():
            raise FileNotFoundError(f"Not a directory: {self.root}")
        self.max_bytes = max_bytes

    def list(self) -> Iterable[DocumentRef]:
        for p in sorted(self.root.rglob("*")):
            if any(part in SKIP_DIRS or part.startswith(".") for part in p.relative_to(self.root).parts):
                continue
            if not p.is_file():
                continue
            real = p.resolve()
            if self.root not in real.parents and real != self.root:
                continue  # symlink pointing outside the root
            size = real.stat().st_size
            if size > self.max_bytes:
                continue
            uri = f"file://{real}"
            yield DocumentRef(
                id=DocumentRef.make_id(uri),
                name=str(p.relative_to(self.root)),
                uri=uri,
                source=self.name,
                mime=mimetypes.guess_type(p.name)[0],
                size_bytes=size,
                sha256=hashlib.sha256(real.read_bytes()).hexdigest(),
            )

    def read(self, ref: DocumentRef) -> bytes:
        path = Path(ref.uri.removeprefix("file://")).resolve()
        if self.root not in path.parents:
            raise PermissionError("Refusing to read outside source root")
        return path.read_bytes()
