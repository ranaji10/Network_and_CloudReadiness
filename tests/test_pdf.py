"""PDF export (API-04): rendered from the model, readable back with pypdf, honest in share-safe mode."""

import io
import sys
from pathlib import Path

import pytest
from pypdf import PdfReader

from readiness.models import AssessmentReport
from readiness.pipeline import run_assessment
from readiness.report import pdf as pdf_module
from readiness.report.pdf import PdfExportUnavailableError, render_pdf


def _text(data: bytes) -> str:
    return "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(data)).pages)


@pytest.fixture(scope="module")
def report(tmp_path_factory) -> AssessmentReport:
    from readiness.config import DEFAULT_CONFIG_DIR, Settings

    settings = Settings(
        _env_file=None,
        provider="local",
        llm_provider="mock",
        workspace_dir=tmp_path_factory.mktemp("ws"),
        config_dir=DEFAULT_CONFIG_DIR,
        tenant_id="test",
        include_evidence_snippets=True,
    )
    fixtures = Path(__file__).parent / "fixtures" / "synthetic_acme"
    report, _ = run_assessment(f"file://{fixtures}", settings, "default")
    return report


def test_render_pdf_contains_the_report(report):
    data = render_pdf(report)
    assert data.startswith(b"%PDF")
    text = _text(data)
    assert report.id in text
    for domain in report.domains:
        assert domain.name in text
    actions = [r for r in report.recommendations if r.kind == "action"]
    assert actions and actions[0].title in text
    assert "4a. Actions" in text and "4b. Discovery" in text and "5. Data handling" in text
    assert report.documents[0].name in text  # documents table
    assert f"Redaction mode {report.redaction.mode}" in text


def test_share_safe_pdf_has_no_document_names(report):
    safe = report.model_copy(update={"extra": {**report.extra, "share_safe": True}})
    text = _text(render_pdf(safe))
    for ref in report.documents:
        assert ref.name not in text
    assert "Share-safe report" in text and "document 1" in text


def test_non_latin1_text_is_mapped_not_fatal(report):
    odd = report.model_copy(update={"warnings": ["em dash — ellipsis … “quotes” → arrow 中"]})
    text = _text(render_pdf(odd))
    assert 'em dash - ellipsis ... "quotes" -> arrow ?' in text


def test_missing_fpdf2_raises_install_hint(report, monkeypatch):
    monkeypatch.setitem(sys.modules, "fpdf", None)  # makes `import fpdf` raise ImportError
    with pytest.raises(PdfExportUnavailableError, match="pdf"):
        render_pdf(report)
    assert "uv sync --extra pdf" in pdf_module.INSTALL_HINT
