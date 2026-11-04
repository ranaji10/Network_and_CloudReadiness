"""SCR-05 evaluation set: 20 SYNTHETIC document packs with pinned scores (see packs/README.md).

Every pack runs through `run_assessment` offline, with the mock LLM, in two modes: rules only and rules
plus the LLM judge. The pinned numbers in each pack's `expected.yaml` fail the build when the scoring
configuration or engine drifts beyond the pack's tolerance; the designed check statuses, document
classes and warnings pin the behaviour each pack was written to exercise. Refresh after an intended
scoring change with `make evals-refresh` and review the diff."""

from __future__ import annotations

from pathlib import Path

import pytest
from generate_expected import (
    MODES,
    check_statuses,
    document_classes,
    drift,
    list_packs,
    load_expected,
    run_pack,
    summarise,
)

PACKS = list_packs()


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("pack", PACKS, ids=[p.name for p in PACKS])
def test_pack_matches_expected(pack: Path, mode: str, tmp_path: Path) -> None:
    expected = load_expected(pack)
    report = run_pack(pack, mode, expected["profile"], tmp_path)

    problems = drift(expected, mode, summarise(report))
    assert not problems, "\n".join(problems)

    statuses = check_statuses(report)
    for check_id, want in (expected.get("checks") or {}).items():
        assert check_id in statuses, f"{pack.name}: expected.yaml names unknown check {check_id}"
        assert statuses[check_id] == want, f"{pack.name}[{mode}] {check_id}: expected {want}, got {statuses[check_id]}"

    if "documents" in expected:
        assert len(report.documents) == expected["documents"]
    classes = document_classes(report)
    for name, cls in (expected.get("document_classes") or {}).items():
        assert classes.get(name) == cls, f"{pack.name}: {name} classified {classes.get(name)!r}, expected {cls!r}"
    for fragment in expected.get("warnings_contain") or []:
        assert any(fragment in w for w in report.warnings), f"{pack.name}: no warning containing {fragment!r}"

    # The judge mode must really go through the guarded mock provider, and never a real one.
    if mode == "judge":
        assert report.llm_provider == "mock"
        assert report.extra["llm_usage"]["calls"] > 0
    else:
        assert report.llm_provider == "none" and "llm_usage" not in report.extra


def test_evaluation_set_is_complete() -> None:
    assert len(PACKS) == 20, [p.name for p in PACKS]
    for pack in PACKS:
        expected = load_expected(pack)
        assert expected.get("rules"), f"{pack.name}: no pinned values; run `make evals-refresh`"
        assert expected.get("checks"), f"{pack.name}: pin at least one designed check status"
        assert any(p.is_file() for p in (pack / "docs").iterdir()), f"{pack.name}: empty docs folder"
