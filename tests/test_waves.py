"""REC-05: migration wave planning from inventory documents."""

import json
import re

import pytest
from pydantic import ValidationError

from readiness.config import DEFAULT_CONFIG_DIR
from readiness.ingestion.classify import classify
from readiness.models import AssessmentReport, DocClass, DocumentRef, ExtractedDocument, RedactionSummary
from readiness.pipeline import run_assessment
from readiness.recommend.waves import NO_MATCH_REASON, WaveConfig, load_wave_config, plan_waves, split_rows
from readiness.report.markdown import render
from readiness.scoring.profiles import load_profile


def _doc(text: str, name: str = "inv.csv", cls: DocClass = DocClass.INVENTORY) -> ExtractedDocument:
    ref = DocumentRef(id=DocumentRef.make_id(name), name=name, uri=f"file:///{name}", source="local")
    return ExtractedDocument(ref=ref, text=text, classification=cls, classification_confidence=0.9)


def _small_config(**overrides) -> WaveConfig:
    data = {
        "default_wave": "core",
        "max_rows_per_wave": 25,
        "header_cells": ["hostname", "name"],
        "waves": [
            {"id": "quick_wins", "name": "W1", "order": 1, "signals": ["web", "docker", "file share"]},
            {"id": "core", "name": "W2", "order": 2, "signals": ["database", "erp", "tier 1"]},
            {"id": "legacy", "name": "W3", "order": 3, "signals": ["windows server 2008", "cobol", "end of life"]},
        ],
    }
    data.update(overrides)
    return WaveConfig.model_validate(data)


def _wave(plan, wave_id):
    return next(w for w in plan.waves if w.id == wave_id)


# --- configuration -----------------------------------------------------------------------------------------


def test_shipped_wave_config_loads():
    cfg = load_wave_config(DEFAULT_CONFIG_DIR)
    assert [w.id for w in sorted(cfg.waves, key=lambda w: w.order)] == ["quick_wins", "core", "legacy"]
    assert cfg.default_wave in {w.id for w in cfg.waves}
    assert len({w.order for w in cfg.waves}) == 3 and cfg.max_rows_per_wave >= 1
    assert all(w.signals and w.description for w in cfg.waves)


def test_invalid_regex_signal_fails_at_load():
    with pytest.raises(ValidationError, match="invalid wave signal"):
        _small_config(
            waves=[{"id": "quick_wins", "name": "W1", "order": 1, "signals": ["(unclosed"]}],
            default_wave="quick_wins",
        )


def test_default_wave_must_exist_and_ids_unique():
    with pytest.raises(ValidationError, match="default_wave"):
        _small_config(default_wave="nope")
    with pytest.raises(ValidationError, match="duplicate wave ids"):
        _small_config(
            waves=[
                {"id": "core", "name": "a", "order": 1, "signals": ["x"]},
                {"id": "core", "name": "b", "order": 2, "signals": ["y"]},
            ]
        )


def test_profile_switch_defaults_off_and_on_for_gcp_migration():
    assert load_profile(DEFAULT_CONFIG_DIR, "default").migration_waves is False
    assert load_profile(DEFAULT_CONFIG_DIR, "gcp_migration").migration_waves is True


# --- row splitting ------------------------------------------------------------------------------------------


def test_split_rows_skips_headers_markers_and_separators():
    text = "\n".join(
        [
            "## sheet: servers",
            "hostname,role,os",  # header by first cell
            "<host-01>,web,Ubuntu 22.04",
            "",
            "| name | role |",  # markdown header by first cell
            "|---|---|",
            "| <host-02> | database |",
            "--- --- ---",
            "12345",  # no letters
            "<host-03>,erp,RHEL 8",
        ]
    )
    rows = split_rows(text, ["hostname", "name"])
    assert [label for label, _ in rows] == ["<host-01>", "<host-02>", "<host-03>"]


def test_split_rows_first_row_without_digits_is_a_header_and_free_text_uses_first_token():
    rows = split_rows("System;Role\nmainframe-a;batch COBOL\nWarehouse scanner fleet 12 units", ["hostname"])
    assert rows[0][0] == "mainframe-a"
    assert rows[1][0] == "Warehouse"  # single-cell line: first token


def test_label_is_capped():
    label = "x" * 200
    rows = split_rows(f"{label},web,1", [])
    assert len(rows[0][0]) == 60


# --- planning -----------------------------------------------------------------------------------------------


def test_each_wave_and_default():
    doc = _doc(
        "hostname,role,os,notes\n"
        "<host-01>,web,Ubuntu 22.04,docker\n"
        "<host-02>,database,Windows Server 2019,tier 1\n"
        "<host-03>,batch,Windows Server 2008 R2,COBOL\n"
        "<host-04>,unknown,Ubuntu 22.04,\n"
    )
    plan = plan_waves([doc], _small_config())
    assert plan.inventory_documents == ["inv.csv"] and plan.total_systems == 4
    assert [(s.system, s.reason) for s in _wave(plan, "quick_wins").systems] == [("<host-01>", "web")]
    assert [(s.system, s.reason) for s in _wave(plan, "core").systems] == [
        ("<host-02>", "database"),
        ("<host-04>", NO_MATCH_REASON),
    ]
    assert [(s.system, s.reason) for s in _wave(plan, "legacy").systems] == [("<host-03>", "windows server 2008")]
    assert all(s.source_doc == "inv.csv" for w in plan.waves for s in w.systems)
    assert [w.order for w in plan.waves] == [1, 2, 3]


def test_precedence_legacy_beats_core_beats_quick_wins():
    doc = _doc("hostname,notes\n<host-01>,web docker database\n<host-02>,web docker end of life\n")
    plan = plan_waves([doc], _small_config())
    assert _wave(plan, "core").systems[0].system == "<host-01>"
    assert _wave(plan, "legacy").systems[0].system == "<host-02>"
    assert _wave(plan, "quick_wins").count == 0


def test_cap_limits_listed_rows_but_not_count():
    doc = _doc("hostname,role\n" + "".join(f"<host-{i:02d}>,web\n" for i in range(1, 6)))
    plan = plan_waves([doc], _small_config(max_rows_per_wave=2))
    w = _wave(plan, "quick_wins")
    assert w.count == 5 and [s.system for s in w.systems] == ["<host-01>", "<host-02>"]
    assert plan.total_systems == 5 and plan.max_rows_per_wave == 2


def test_only_inventory_documents_are_read_and_duplicates_collapse():
    inv = _doc("hostname,role\n<host-01>,web\n<host-01>,web\n", name="a.csv")
    other = _doc("hostname,role\n<host-09>,web\n", name="b.csv", cls=DocClass.DATA_STORAGE)
    plan = plan_waves([other, inv], _small_config())
    assert plan.inventory_documents == ["a.csv"] and plan.total_systems == 1
    assert _wave(plan, "quick_wins").systems[0].system == "<host-01>"


def test_no_inventory_document_gives_empty_plan():
    plan = plan_waves([_doc("x", cls=DocClass.NETWORK)], _small_config())
    assert plan.inventory_documents == [] and plan.total_systems == 0 and all(w.count == 0 for w in plan.waves)


def test_shipped_signals_sort_synthetic_rows_as_expected():
    cfg = load_wave_config(DEFAULT_CONFIG_DIR)
    doc = _doc(
        "hostname,role,os,notes\n"
        "<host-01>,web,Ubuntu 22.04,kubernetes dev cluster\n"
        "<host-02>,files,Windows Server 2016,SMB file share\n"
        "<host-03>,erp,RHEL 8,Oracle 19c mission critical\n"
        "<host-04>,crm,Ubuntu 22.04,customer-facing payments\n"
        "<host-05>,batch,AS/400,RPG programs no vendor support\n"
        "<host-06>,appliance,proprietary,physical appliance end of life\n"
        "<host-07>,misc,Ubuntu 22.04,\n"
    )
    plan = plan_waves([doc], cfg)
    assert [s.system for s in _wave(plan, "quick_wins").systems] == ["<host-01>", "<host-02>"]
    assert [s.system for s in _wave(plan, "core").systems] == ["<host-03>", "<host-04>", "<host-07>"]
    assert [s.system for s in _wave(plan, "legacy").systems] == ["<host-05>", "<host-06>"]
    assert _wave(plan, "core").systems[-1].reason == NO_MATCH_REASON


# --- classifier, renderer and pipeline ----------------------------------------------------------------------


def test_fixture_inventory_is_classified_as_inventory(fixtures_dir):
    text = (fixtures_dir / "synthetic_acme" / "server_inventory.csv").read_text()
    assert classify("server_inventory.csv", text)[0] == DocClass.INVENTORY


def test_render_without_inventory_writes_one_line(settings, fixtures_dir):
    report, md = run_assessment(f"file://{fixtures_dir / 'synthetic_acme'}", settings, "gcp_migration")
    bare = report.model_copy(
        update={"migration_waves": report.migration_waves.model_copy(update={"inventory_documents": []})}
    )
    md = render(bare)
    assert "## 5. Migration waves" not in md and "no wave plan was produced" in md and "## 5. Data handling" in md


def test_pipeline_gcp_migration_has_wave_table(settings, fixtures_dir):
    report, md = run_assessment(f"file://{fixtures_dir / 'synthetic_acme'}", settings, "gcp_migration")
    plan = report.migration_waves
    assert plan is not None and plan.inventory_documents == ["server_inventory.csv"]
    assert plan.total_systems == 6 and {w.id for w in plan.waves} == {"quick_wins", "core", "legacy"}
    assert all(w.count >= 1 for w in plan.waves), plan
    legacy = _wave(plan, "legacy")
    assert legacy.systems[0].reason in {"cobol", "windows server 2008", "vendor support ended"}
    # labels come from redacted text: pseudonyms only, never the fixture hostnames
    systems = [s.system for w in plan.waves for s in w.systems]
    assert all(s.startswith("<host-") for s in systems), systems
    assert "acme.internal" not in md and "acme.internal" not in report.model_dump_json()
    # source document names are the ones listed in the report's document table
    assert {s.source_doc for w in plan.waves for s in w.systems} <= {d.name for d in report.documents}
    assert "## 5. Migration waves" in md and "## 6. Data handling" in md
    # pseudonym numbers depend on the order documents are redacted, so match the shape, not the number
    assert re.search(r"\| `<host-\d\d>` \| web \| server_inventory\.csv \|", md), md
    on_disk = json.loads((settings.workspace_dir / "test" / report.id / "report.json").read_text())
    assert on_disk["migration_waves"]["total_systems"] == 6
    assert "Migration waves" in (settings.workspace_dir / "test" / report.id / "report.md").read_text()


def test_pipeline_default_profile_has_no_wave_section(settings, fixtures_dir):
    report, md = run_assessment(f"file://{fixtures_dir / 'synthetic_acme'}", settings, "default")
    assert report.migration_waves is None
    assert "Migration waves" not in md and "## 5. Data handling" in md
    assert AssessmentReport.model_validate_json(report.model_dump_json()).migration_waves is None
    assert isinstance(report.redaction, RedactionSummary)


def test_share_safe_wave_table_uses_document_labels(settings, fixtures_dir):
    s = settings.model_copy(update={"share_safe": True})
    report, md = run_assessment(f"file://{fixtures_dir / 'synthetic_acme'}", s, "gcp_migration")
    plan = report.migration_waves
    assert plan is not None and plan.inventory_documents and all(d.startswith("doc-") for d in plan.inventory_documents)
    assert "server_inventory" not in md and "acme.internal" not in md
    assert all(x.source_doc.startswith("doc-") for w in plan.waves for x in w.systems)


def test_pdf_has_migration_waves_section(settings, fixtures_dir):
    from io import BytesIO

    from pypdf import PdfReader

    from readiness.report.pdf import render_pdf

    report, _ = run_assessment(f"file://{fixtures_dir / 'synthetic_acme'}", settings, "gcp_migration")
    text = "\n".join(p.extract_text() for p in PdfReader(BytesIO(render_pdf(report))).pages)
    assert "Migration waves" in text and "6. Data handling" in text
    report2, _ = run_assessment(f"file://{fixtures_dir / 'synthetic_acme'}", settings, "default")
    text2 = "\n".join(p.extract_text() for p in PdfReader(BytesIO(render_pdf(report2))).pages)
    assert "Migration waves" not in text2 and "5. Data handling" in text2
