"""Append-only audit log. Records *that* something happened with hashes and counts, never content."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class AuditLog:
    def __init__(self, path: Path | None, run_id: str, tenant_id: str):
        self.path, self.run_id, self.tenant_id = path, run_id, tenant_id
        self.events: list[dict[str, Any]] = []
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)

    def event(self, kind: str, **fields: Any) -> None:
        for k, v in fields.items():
            if isinstance(v, str) and len(v) > 200:
                raise ValueError(f"Audit field '{k}' looks like content, not metadata; refusing to log it")
        rec = {
            "ts": datetime.now(UTC).isoformat(),
            "run": self.run_id,
            "tenant": self.tenant_id,
            "event": kind,
            **fields,
        }
        self.events.append(rec)
        if self.path:
            with self.path.open("a") as f:
                f.write(json.dumps(rec) + "\n")
