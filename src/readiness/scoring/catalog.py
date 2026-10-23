"""CSA CCM v4.1 / CAIQ control catalog (generated into readiness/data by scripts/build_control_catalog.py)."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data" / "ccm_v4.1.json"


@lru_cache(maxsize=1)
def load_catalog() -> dict:
    return json.loads(DATA.read_text())


@lru_cache(maxsize=1)
def controls_by_id() -> dict[str, dict]:
    return {c["id"]: c for c in load_catalog()["controls"]}


def control(control_id: str) -> dict | None:
    return controls_by_id().get(control_id)


def caiq_questions(control_ids: list[str]) -> list[str]:
    out: list[str] = []
    for cid in control_ids:
        c = control(cid)
        if c:
            out.extend(f"{q['id']}: {q['text']}" for q in c["questions"])
    return out


def search(term: str, limit: int = 20) -> list[dict]:
    t = term.lower()
    hits = [
        c
        for c in load_catalog()["controls"]
        if t in c["id"].lower() or t in c["title"].lower() or t in c["specification"].lower()
    ]
    return hits[:limit]
