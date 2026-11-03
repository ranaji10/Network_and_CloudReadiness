"""Migration wave planning from inventory documents (REC-05, the V1 "roadmap generator" waves).

Pure functions, no I/O beyond `load_wave_config`. The planner reads the *redacted* text of every document the
classifier put in the `inventory` class, treats each line as one row (CSV and XLSX rows are one line each after
extraction), skips header-looking lines and places each row in the first wave, tested from the highest `order`
down, whose signals match it. Rows that match nothing go to `default_wave`. Output ordering is deterministic:
documents in pipeline order, rows in document order, waves by `order`.

The `reason` recorded for a row is the configured signal, never document text, and the `system` label is the
first cell of the redacted row (so a hostname appears as `<host-NN>`), capped at `MAX_LABEL_CHARS`."""

from __future__ import annotations

import re
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

from readiness.models import DocClass, ExtractedDocument, MigrationWave, MigrationWavePlan, WaveSystem
from readiness.scoring.engine import compile_signal

MAX_LABEL_CHARS = 60
NO_MATCH_REASON = "no signal matched (default wave)"
_CELL_SPLIT = re.compile(r"[,|\t;]")
_SEPARATOR_LINE = re.compile(r"^[\s|:\-=+]+$")  # markdown table rules such as |---|:--:|
_SHEET_MARKER = "## sheet:"  # emitted by ingestion.extract._xlsx


class WaveDef(BaseModel):
    id: str
    name: str
    order: int
    description: str = ""
    signals: list[str] = Field(min_length=1)

    @field_validator("signals")
    @classmethod
    def _compile(cls, signals: list[str]) -> list[str]:
        for s in signals:
            try:
                compile_signal(s)
            except re.error as exc:
                raise ValueError(f"invalid wave signal {s!r}: {exc}") from exc
        return signals


class WaveConfig(BaseModel):
    version: str = "1"
    default_wave: str
    max_rows_per_wave: int = Field(default=25, ge=1)
    header_cells: list[str] = []
    waves: list[WaveDef] = Field(min_length=1)

    @model_validator(mode="after")
    def _consistent(self) -> WaveConfig:
        ids = [w.id for w in self.waves]
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        if dupes:
            raise ValueError(f"duplicate wave ids: {dupes}")
        if self.default_wave not in ids:
            raise ValueError(f"default_wave {self.default_wave!r} is not one of {ids}")
        return self


def load_wave_config(config_dir: Path) -> WaveConfig:
    path = config_dir / "recommendations" / "waves.yaml"
    return WaveConfig.model_validate(yaml.safe_load(path.read_text()))


def _normalise_cell(cell: str) -> str:
    return " ".join(cell.strip().strip("\"'`*").split()).lower()


def split_rows(text: str, header_cells: list[str]) -> list[tuple[str, str]]:
    """Turn a document's text into `(system_label, row_text)` pairs, dropping headers, blank and separator
    lines, XLSX sheet markers and lines without a letter. Exposed for tests."""
    headers = {_normalise_cell(h) for h in header_cells}
    rows: list[tuple[str, str]] = []
    first_row = True
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.lower().startswith(_SHEET_MARKER) or _SEPARATOR_LINE.match(line):
            continue
        if not any(ch.isalpha() for ch in line):
            continue
        cells = [c for c in (c.strip() for c in _CELL_SPLIT.split(line)) if c]
        if not cells:
            continue
        label = cells[0] if len(cells) > 1 else line.split()[0]
        is_header = _normalise_cell(label) in headers or (first_row and not any(ch.isdigit() for ch in line))
        first_row = False
        if is_header:
            continue
        rows.append((label.strip("\"'`*")[:MAX_LABEL_CHARS], line))
    return rows


def plan_waves(docs: list[ExtractedDocument], config: WaveConfig) -> MigrationWavePlan:
    """Build the wave plan from the inventory documents in `docs` (already redacted). Always returns a plan;
    `inventory_documents` is empty when nothing was classified as inventory."""
    inventory = [d for d in docs if d.classification == DocClass.INVENTORY and d.text.strip()]
    # highest order first: a legacy signal beats a core signal beats a quick win
    by_precedence = sorted(config.waves, key=lambda w: (-w.order, w.id))
    compiled = {w.id: [(s, compile_signal(s)) for s in w.signals] for w in config.waves}
    placed: dict[str, list[WaveSystem]] = {w.id: [] for w in config.waves}
    for d in inventory:
        seen: set[str] = set()
        for label, row in split_rows(d.text, config.header_cells):
            if label in seen:  # the same system listed twice in one document (several sheets, duplicates)
                continue
            seen.add(label)
            wave_id, reason = config.default_wave, NO_MATCH_REASON
            for w in by_precedence:
                hit = next((s for s, rx in compiled[w.id] if rx.search(row)), None)
                if hit is not None:
                    wave_id, reason = w.id, hit
                    break
            placed[wave_id].append(WaveSystem(system=label, reason=reason, source_doc=d.ref.name))
    waves = [
        MigrationWave(
            id=w.id,
            name=w.name,
            order=w.order,
            description=w.description,
            count=len(placed[w.id]),
            systems=placed[w.id][: config.max_rows_per_wave],
        )
        for w in sorted(config.waves, key=lambda w: (w.order, w.id))
    ]
    return MigrationWavePlan(
        waves=waves,
        inventory_documents=[d.ref.name for d in inventory],
        total_systems=sum(w.count for w in waves),
        default_wave=config.default_wave,
        max_rows_per_wave=config.max_rows_per_wave,
    )
