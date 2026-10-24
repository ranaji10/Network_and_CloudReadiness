"""Ports (abstract interfaces). The core depends only on these; adapters implement them.

Adding a new cloud = implementing these four protocols in readiness/adapters/* and registering
them in readiness/adapters/registry.py. No other module should change."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel

from readiness.models import DocumentRef

T = TypeVar("T", bound=BaseModel)


@runtime_checkable
class DocumentSource(Protocol):
    """Lists and reads documents from somewhere. Must never follow links outside its root."""

    name: str

    def list(self) -> Iterable[DocumentRef]: ...

    def read(self, ref: DocumentRef) -> bytes: ...


@runtime_checkable
class LLMProvider(Protocol):
    """Structured generation. Implementations must not log prompt contents."""

    name: str

    def generate_structured(self, system: str, prompt: str, schema: type[T]) -> T: ...


@runtime_checkable
class BlobStore(Protocol):
    """Where reports and uploads live. Keys are tenant-prefixed by the caller."""

    name: str

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str: ...

    def get(self, key: str) -> bytes: ...

    def exists(self, key: str) -> bool: ...

    def list(self, prefix: str = "") -> Iterable[str]: ...

    def delete(self, key: str) -> None: ...


@runtime_checkable
class SecretStore(Protocol):
    name: str

    def get(self, key: str) -> str | None: ...
