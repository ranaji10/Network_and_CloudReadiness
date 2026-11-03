"""ING-09: PPTX and legacy DOC/XLS extraction behind the `office` extra.

The committed fixtures in tests/fixtures/synthetic_office/ are SYNTHETIC (see its README). The .doc there
was produced by LibreOffice, so it has a genuine FIB and an 8-bit (cp1252) piece table; the UTF-16 piece
branch and the printable-run fallback are exercised with in-memory byte strings because Word is the only
tool that writes those shapes reliably."""

from __future__ import annotations

import struct
import sys
from pathlib import Path

import pytest

from readiness.ingestion import extract
from readiness.ingestion.extract import extract_text
from readiness.pipeline import run_assessment

OFFICE = Path(__file__).parent / "fixtures" / "synthetic_office"


def _read(name: str) -> bytes:
    return (OFFICE / name).read_bytes()


# --- the three formats, through the public contract --------------------------------------------------


def test_pptx_yields_slides_tables_and_notes():
    text, truncated, err = extract_text("segmentation_roadmap.pptx", _read("segmentation_roadmap.pptx"))
    assert err is None and not truncated
    assert "## slide 1" in text and "## slide 2" in text
    assert "Acme Widgets network segmentation roadmap" in text
    assert "Firewall rules reviewed quarterly" in text
    assert "notes: Speaker notes: DMZ hosts the public web tier." in text
    assert "Corporate LAN | 10.20.0.0/16 | NetOps" in text  # table cells joined like the docx path


def test_xls_yields_every_sheet_like_xlsx():
    text, truncated, err = extract_text("asset_inventory.xls", _read("asset_inventory.xls"))
    assert err is None and not truncated
    assert text.startswith("## sheet: Servers\nHostname | Role | vCPU | RAM GB | OS\n")
    assert "acme-db-01 | postgres database | 8 | 64 | RHEL 9" in text  # integral floats print as ints
    assert "## sheet: Backups\nSystem | RPO hours | RTO hours\npostgres database | 1 | 4" in text


def test_doc_yields_paragraphs_via_piece_table():
    text, truncated, err = extract_text("backup_standard.doc", _read("backup_standard.doc"))
    assert err is None and not truncated
    assert text.splitlines()[0] == "Acme Widgets backup and disaster recovery standard"
    assert "RPO is 1 hour and RTO is 4 hours" in text
    assert "\r" not in text and "\x07" not in text


def test_doc_extension_on_non_ole_bytes_is_an_error_not_an_exception():
    text, truncated, err = extract_text("note.doc", b"{\\rtf1\\ansi Hello}")
    assert text == "" and not truncated and err is not None
    assert "OLE" in err


def test_office_text_respects_max_chars():
    text, truncated, err = extract_text("segmentation_roadmap.pptx", _read("segmentation_roadmap.pptx"), max_chars=40)
    assert err is None and truncated and len(text) == 40


# --- the .doc reader internals: UTF-16 pieces and the fallback scan ------------------------------------


class _FakeOle:
    """Just enough of olefile.OleFileIO for _doc_piece_table."""

    def __init__(self, streams: dict[str, bytes]):
        self._streams = streams

    def exists(self, name: str) -> bool:
        return name in self._streams

    def openstream(self, name: str):
        import io

        return io.BytesIO(self._streams[name])


def _word_and_table(text: str, compressed: bool) -> tuple[bytes, bytes]:
    """Build a WordDocument stream (FIB + text) and a 1Table stream (one Prc then the Pcdt)."""
    header = bytearray(0x400)
    header[0:2] = b"\xec\xa5"
    struct.pack_into("<H", header, 10, extract._DOC_WHICH_TABLE)
    text_off = len(header)
    body = text.encode("cp1252") if compressed else text.encode("utf-16-le")
    fc = (text_off * 2) | extract._DOC_PIECE_COMPRESSED if compressed else text_off
    plc = struct.pack("<II", 0, len(text)) + struct.pack("<HIH", 0, fc, 0)
    clx = b"\x01" + struct.pack("<H", 2) + b"\xaa\xbb" + b"\x02" + struct.pack("<I", len(plc)) + plc
    clx_off = 16
    struct.pack_into("<II", header, extract._DOC_FC_CLX, clx_off, len(clx))
    return bytes(header) + body, b"\x00" * clx_off + clx


@pytest.mark.parametrize("compressed", [True, False], ids=["cp1252", "utf-16le"])
def test_piece_table_decodes_both_encodings(compressed):
    word, table = _word_and_table("Backup policy\rRPO 1h\x07RTO 4h\x07", compressed)
    out = extract._doc_piece_table(word, _FakeOle({"WordDocument": word, "1Table": table}))
    assert out == "Backup policy\nRPO 1h | RTO 4h |"


def test_fallback_scan_recovers_text_without_a_valid_fib():
    # Binary-looking padding: small little-endian integers, 0xff fills and a few stray printable bytes.
    noise = (b"\x05\x00\x00\x00" + b"\xff" * 6 + b"@\x00" + bytes(range(0, 32))) * 8
    for encoding in ("cp1252", "utf-16-le"):
        stream = noise + "Disaster recovery plan is tested yearly.".encode(encoding) + noise
        out = extract._doc_fallback(stream)
        assert "Disaster recovery plan is tested yearly." in out
        assert "\x00" not in out


def test_doc_falls_back_when_piece_table_is_broken(monkeypatch):
    """The real fixture, but with the CLX pointer zeroed so the piece-table path raises."""
    import olefile

    original_open = olefile.OleFileIO.openstream

    def broken_openstream(self, name):
        stream = original_open(self, name)
        if name == "WordDocument":
            buf = bytearray(stream.read())
            struct.pack_into("<II", buf, extract._DOC_FC_CLX, 0xFFFFFFF0, 0xFFFF)
            import io

            return io.BytesIO(bytes(buf))
        return stream

    monkeypatch.setattr(olefile.OleFileIO, "openstream", broken_openstream)
    text, _, err = extract_text("backup_standard.doc", _read("backup_standard.doc"))
    assert err is None and "RPO is 1 hour and RTO is 4 hours" in text


# --- missing extra: an error string, never an exception ----------------------------------------------


@pytest.mark.parametrize(
    ("module", "name"),
    [("pptx", "segmentation_roadmap.pptx"), ("xlrd", "asset_inventory.xls"), ("olefile", "backup_standard.doc")],
)
def test_missing_office_extra_reports_error(monkeypatch, module, name):
    monkeypatch.setitem(sys.modules, module, None)  # makes `import <module>` raise ImportError
    text, truncated, err = extract_text(name, _read(name))
    assert text == "" and not truncated
    assert err is not None and "readiness[office]" in err and name.rsplit(".", 1)[1] in err


# --- end to end, offline ----------------------------------------------------------------------------


def test_pipeline_reads_office_folder_offline(settings, fixtures_dir):
    import json

    report, md = run_assessment(f"file://{fixtures_dir / 'synthetic_office'}", settings, "default")
    assert report.llm_provider == "none"
    by_name = {d.name: d for d in report.documents}
    office = ("segmentation_roadmap.pptx", "asset_inventory.xls", "backup_standard.doc")
    assert set(by_name) == {"README.md", *office}
    assert not report.warnings  # extraction errors would surface here
    assert all(report.document_classes[by_name[n].id] != "irrelevant" for n in office)
    assert report.document_classes[by_name["backup_standard.doc"].id] == "backup_dr"
    audit = [
        json.loads(line)
        for line in (settings.workspace_dir / "test" / report.id / "audit.jsonl").read_text().splitlines()
    ]
    ingested = {e["doc"]: e for e in audit if e["event"] == "doc.ingested"}
    assert all(ingested[by_name[n].id]["chars"] > 0 and ingested[by_name[n].id]["error"] == "" for n in office)
    assert 0 < report.overall_score <= 100 and "# " in md
