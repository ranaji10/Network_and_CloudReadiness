"""ING-08: OCR for scanned PDFs and images behind the `ocr` extra.

The fixtures in tests/fixtures/synthetic_scanned/ are SYNTHETIC (see its README): an image-only PDF and a PNG.
Tests that need Tesseract's real output skip, with a reason, when the `tesseract` binary is not on PATH; the
dispatch, budget, disabled and missing-dependency behaviour is covered with monkeypatched OCR calls so it
runs everywhere."""

from __future__ import annotations

import io
import json
import shutil
import sys
from pathlib import Path

import pytest

from readiness.config import Settings
from readiness.ingestion import extract
from readiness.ingestion.extract import OcrOptions, extract_document, extract_text
from readiness.pipeline import run_assessment

SCANNED = Path(__file__).parent / "fixtures" / "synthetic_scanned"
HAS_TESSERACT = shutil.which("tesseract") is not None
needs_tesseract = pytest.mark.skipif(
    not HAS_TESSERACT, reason="tesseract-ocr binary not on PATH (apt-get install tesseract-ocr)"
)


def _read(name: str) -> bytes:
    return (SCANNED / name).read_bytes()


def _text_pdf(*lines: str) -> bytes:
    """A real text PDF (fpdf2), the kind that must never reach OCR."""
    from fpdf import FPDF

    pdf = FPDF()
    pdf.set_font("Helvetica", size=14)
    for line in lines:
        pdf.add_page()
        pdf.cell(text=line)
    return bytes(pdf.output())


def _merge(*pdfs: bytes) -> bytes:
    from pypdf import PdfReader, PdfWriter

    writer = PdfWriter()
    for data in pdfs:
        for page in PdfReader(io.BytesIO(data)).pages:
            writer.add_page(page)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


@pytest.fixture
def fake_ocr(monkeypatch):
    """Replace the Tesseract call with a stub and record the PDF page indices that were rendered."""
    calls: list[list[int]] = []

    def pages(data: bytes, indices: list[int], ocr: OcrOptions) -> list[str]:
        calls.append(list(indices))
        return [f"OCR TEXT page {i}" for i in indices]

    monkeypatch.setattr(extract, "_ocr_pdf_pages", pages)
    monkeypatch.setattr(extract, "_ocr_image", lambda image, ocr: "OCR TEXT image")
    return calls


# --- text PDFs never touch OCR -----------------------------------------------------------------------


def test_text_pdf_is_extracted_without_ocr(fake_ocr):
    result = extract_document("policy.pdf", _text_pdf("Nightly backups are encrypted and stored offsite."))
    assert result.error is None and result.ocr_pages == 0 and not result.truncated
    assert "Nightly backups are encrypted" in result.text
    assert fake_ocr == []


def test_only_sparse_pages_are_ocrd_in_a_mixed_pdf(fake_ocr):
    mixed = _merge(
        _text_pdf("Firewall rules are reviewed quarterly by the network team."), _read("backup_standard_scanned.pdf")
    )
    result = extract_document("mixed.pdf", mixed)
    assert fake_ocr == [[1, 2]]  # page 0 has text; the two scanned pages follow
    assert result.ocr_pages == 2 and result.error is None and not result.truncated
    lines = result.text.split("\n")
    assert "Firewall rules are reviewed quarterly" in lines[0]
    assert lines[1:] == ["OCR TEXT page 1", "OCR TEXT page 2"]


def test_min_chars_per_page_decides_what_counts_as_scanned(fake_ocr):
    data = _text_pdf("short")
    assert extract_document("a.pdf", data, ocr=OcrOptions(min_chars_per_page=3)).ocr_pages == 0
    assert extract_document("a.pdf", data, ocr=OcrOptions(min_chars_per_page=10)).ocr_pages == 1
    assert fake_ocr == [[0]]


# --- the real thing (needs the tesseract binary) ------------------------------------------------------


@needs_tesseract
def test_scanned_pdf_yields_its_text():
    text, truncated, err = extract_text("backup_standard_scanned.pdf", _read("backup_standard_scanned.pdf"))
    assert err is None and not truncated
    assert "Acme Widgets backup and disaster" in text
    assert "RPO is 1 hour and RTO is 4 hours." in text
    assert "Firewall rules" in text and "multi-factor authentication" in text  # page 2


@needs_tesseract
def test_png_yields_its_text():
    result = extract_document("firewall_change_notice.png", _read("firewall_change_notice.png"))
    assert result.error is None and result.ocr_pages == 1 and not result.truncated
    assert "Acme Widgets firewall change notice" in result.text
    assert "ticket and a peer review" in result.text


@needs_tesseract
def test_page_cap_is_honoured_with_real_ocr():
    result = extract_document(
        "backup_standard_scanned.pdf", _read("backup_standard_scanned.pdf"), ocr=OcrOptions(max_pages=1)
    )
    assert result.ocr_pages == 1 and result.truncated and result.error is None
    assert "Acme Widgets backup and disaster" in result.text
    assert "Firewall rules" not in result.text


@needs_tesseract
def test_ocr_text_respects_max_chars():
    text, truncated, err = extract_text("firewall_change_notice.png", _read("firewall_change_notice.png"), max_chars=20)
    assert err is None and truncated and len(text) == 20


# --- page budget and the disabled switch (no tesseract needed) ------------------------------------------


def test_page_cap_skips_the_rest_and_marks_truncated(fake_ocr):
    scanned = _merge(_read("backup_standard_scanned.pdf"), _read("backup_standard_scanned.pdf"))  # 4 scanned pages
    result = extract_document("long.pdf", scanned, ocr=OcrOptions(max_pages=3))
    assert fake_ocr == [[0, 1, 2]]
    assert result.ocr_pages == 3 and result.truncated and result.error is None
    assert result.text.split("\n") == ["OCR TEXT page 0", "OCR TEXT page 1", "OCR TEXT page 2", ""]


def test_disabled_ocr_skips_scanned_pdf_pages(fake_ocr):
    result = extract_document(
        "backup_standard_scanned.pdf", _read("backup_standard_scanned.pdf"), ocr=OcrOptions(enabled=False)
    )
    assert fake_ocr == []
    assert result.text.strip() == "" and result.error is None and result.ocr_pages == 0


def test_disabled_ocr_reports_images_as_unreadable(fake_ocr):
    text, truncated, err = extract_text(
        "firewall_change_notice.png", _read("firewall_change_notice.png"), ocr=OcrOptions(enabled=False)
    )
    assert text == "" and not truncated and err is not None
    assert "READINESS_OCR_ENABLED" in err and fake_ocr == []


@pytest.mark.parametrize("name", ["diagram.jpg", "diagram.jpeg", "scan.tif", "scan.tiff", "scan.png"])
def test_image_extensions_dispatch_to_ocr(fake_ocr, name):
    result = extract_document(name, _read("firewall_change_notice.png"))  # PNG bytes; Pillow sniffs the format
    assert result.text == "OCR TEXT image" and result.ocr_pages == 1 and result.error is None


# --- missing extra or binary: an error string, never an exception --------------------------------------


def test_missing_ocr_extra_keeps_pdf_text_and_reports_the_hint(monkeypatch):
    monkeypatch.setitem(sys.modules, "pypdfium2", None)  # makes `import pypdfium2` raise ImportError
    text, truncated, err = extract_text("backup_standard_scanned.pdf", _read("backup_standard_scanned.pdf"))
    assert text.strip() == "" and not truncated
    assert err is not None and "2 scanned page(s)" in err and "readiness[ocr]" in err and "tesseract-ocr" in err


def test_missing_ocr_extra_reports_error_for_images(monkeypatch):
    monkeypatch.setitem(sys.modules, "PIL", None)
    text, truncated, err = extract_text("firewall_change_notice.png", _read("firewall_change_notice.png"))
    assert text == "" and not truncated and err is not None and ".png needs" in err and "readiness[ocr]" in err


def test_missing_tesseract_binary_reports_the_hint(monkeypatch):
    import pytesseract

    monkeypatch.setattr(pytesseract.pytesseract, "tesseract_cmd", "/nonexistent/tesseract")
    pdf = extract_document("backup_standard_scanned.pdf", _read("backup_standard_scanned.pdf"))
    assert pdf.error is not None and "tesseract-ocr" in pdf.error and pdf.ocr_pages == 0
    png = extract_document("firewall_change_notice.png", _read("firewall_change_notice.png"))
    assert png.text == "" and png.error is not None and "tesseract-ocr" in png.error


def test_corrupt_image_is_an_error_not_an_exception():
    text, truncated, err = extract_text("broken.png", b"\x89PNG not really")
    assert text == "" and not truncated and err is not None


# --- settings wiring ----------------------------------------------------------------------------------


def test_settings_map_to_ocr_options(monkeypatch):
    assert Settings(_env_file=None).ocr_options() == OcrOptions()
    monkeypatch.setenv("READINESS_OCR_ENABLED", "false")
    monkeypatch.setenv("READINESS_OCR_MAX_PAGES", "7")
    monkeypatch.setenv("READINESS_OCR_LANGUAGES", "eng+deu")
    options = Settings(_env_file=None).ocr_options()
    assert options == OcrOptions(enabled=False, max_pages=7, languages="eng+deu")


# --- end to end, offline ----------------------------------------------------------------------------


def test_pipeline_reads_scanned_folder_offline(settings, fixtures_dir):
    report, md = run_assessment(f"file://{fixtures_dir / 'synthetic_scanned'}", settings, "default")
    assert report.llm_provider == "none"
    by_name = {d.name: d for d in report.documents}
    scanned = ("backup_standard_scanned.pdf", "firewall_change_notice.png")
    assert set(by_name) == {"README.md", *scanned}
    audit = [
        json.loads(line)
        for line in (settings.workspace_dir / "test" / report.id / "audit.jsonl").read_text().splitlines()
    ]
    ingested = {e["doc"]: e for e in audit if e["event"] == "doc.ingested"}
    assert ingested[by_name["README.md"].id]["ocr_pages"] == 0
    assert "# " in md
    if not HAS_TESSERACT:
        # No binary: the run completes (nothing readable, so the score is 0), the scanned files surface as
        # warnings naming the install step, nothing raises.
        assert all(any(n in w and "tesseract-ocr" in w for w in report.warnings) for n in scanned)
        assert all(ingested[by_name[n].id]["ocr_pages"] == 0 for n in scanned)
        return
    assert not report.warnings and 0 < report.overall_score <= 100
    assert ingested[by_name["backup_standard_scanned.pdf"].id]["ocr_pages"] == 2
    assert ingested[by_name["firewall_change_notice.png"].id]["ocr_pages"] == 1
    assert all(ingested[by_name[n].id]["chars"] > 0 for n in scanned)
    assert report.document_classes[by_name["backup_standard_scanned.pdf"].id] == "backup_dr"
    assert report.document_classes[by_name["firewall_change_notice.png"].id] != "irrelevant"
