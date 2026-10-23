"""Offline LLM used by default, in CI, and whenever egress is disabled.

It returns schema-valid, conservative answers (everything 'unknown') unless canned responses are
registered, so the whole pipeline runs end-to-end without any network access."""

from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class MockLLM:
    name = "mock"

    def __init__(self, canned: dict[str, Any] | None = None):
        self.canned = canned or {}
        self.calls: list[tuple[str, str]] = []

    def generate_structured(self, system: str, prompt: str, schema: type[T]) -> T:
        self.calls.append((system, prompt))
        if schema.__name__ in self.canned:
            return schema.model_validate(self.canned[schema.__name__])
        return _conservative_default(schema)


def _conservative_default[S: BaseModel](schema: type[S]) -> S:
    """Build an instance with safe defaults: empty lists, 'unknown' statuses, zero confidence."""
    values: dict[str, Any] = {}
    for name, field in schema.model_fields.items():
        if not field.is_required():
            continue
        ann = field.annotation
        origin = getattr(ann, "__origin__", None)
        if origin is list:
            values[name] = []
        elif ann is str:
            values[name] = "unknown"
        elif ann is float or ann is int:
            values[name] = 0
        elif ann is bool:
            values[name] = False
        else:
            values[name] = None
    return schema.model_validate(values)
