"""Turn bytes into text. Pure functions; no network. Unknown types are skipped, never guessed.

Core formats (PDF, DOCX, XLSX, text, structured) are always available. PPTX slides and the legacy
Office binaries (.xls, .doc) need the `office` extra (`uv sync --extra office` / `pip install
readiness[office]`); without it those files are reported with an error instead of raising."""

from __future__ import annotations

import io
import json
import re
import struct
from pathlib import PurePosixPath

TEXT_EXT = {
    ".txt",
    ".md",
    ".markdown",
    ".rst",
    ".csv",
    ".tsv",
    ".log",
    ".cfg",
    ".conf",
    ".ini",
    ".tf",
    ".hcl",
}
STRUCTURED_EXT = {".json", ".yaml", ".yml", ".toml"}
# Formats whose parser ships in the optional `office` extra (python-pptx, xlrd, olefile).
OFFICE_EXT = {".pptx", ".xls", ".doc"}
OFFICE_EXTRA_HINT = "install the office extra (uv sync --extra office / pip install readiness[office])"


def extract_text(name: str, data: bytes, max_chars: int = 400_000) -> tuple[str, bool, str | None]:
    """Returns (text, truncated, error)."""
    ext = PurePosixPath(name.lower()).suffix
    try:
        if ext in TEXT_EXT or ext in STRUCTURED_EXT:
            text = data.decode("utf-8", errors="replace")
            if ext == ".json":
                try:
                    text = json.dumps(json.loads(text), indent=1)
                except ValueError:
                    pass
        elif ext == ".pdf":
            text = _pdf(data)
        elif ext == ".docx":
            text = _docx(data)
        elif ext in {".xlsx", ".xlsm"}:
            text = _xlsx(data)
        elif ext == ".pptx":
            text = _pptx(data)
        elif ext == ".xls":
            text = _xls(data)
        elif ext == ".doc":
            text = _doc(data)
        else:
            return "", False, f"unsupported type {ext or '(none)'}"
    except ImportError as exc:
        if ext in OFFICE_EXT:
            return "", False, f"{ext} needs {OFFICE_EXTRA_HINT}: {exc}"[:200]
        return "", False, f"{type(exc).__name__}: {exc}"[:200]
    except Exception as exc:  # noqa: BLE001 - extraction failures are reported, not fatal
        return "", False, f"{type(exc).__name__}: {exc}"[:200]
    truncated = len(text) > max_chars
    return text[:max_chars], truncated, None


def _pdf(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def _docx(data: bytes) -> str:
    import docx

    d = docx.Document(io.BytesIO(data))
    parts = [p.text for p in d.paragraphs]
    for table in d.tables:
        for row in table.rows:
            parts.append(" | ".join(c.text for c in row.cells))
    return "\n".join(parts)


def _xlsx(data: bytes) -> str:
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    parts = []
    for ws in wb.worksheets:
        parts.append(f"## sheet: {ws.title}")
        for row in ws.iter_rows(values_only=True):
            cells = [str(c) for c in row if c is not None]
            if cells:
                parts.append(" | ".join(cells))
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Optional `office` extra: PPTX (python-pptx), legacy XLS (xlrd), legacy DOC (olefile + a small
# Word 97-2003 piece-table reader with a printable-run fallback).
# ---------------------------------------------------------------------------


def _pptx(data: bytes) -> str:
    """Every slide: text frames (groups included), table cells, then the speaker notes."""
    from pptx import Presentation

    prs = Presentation(io.BytesIO(data))
    parts: list[str] = []
    for index, slide in enumerate(prs.slides, 1):
        parts.append(f"## slide {index}")
        parts.extend(_pptx_shapes(slide.shapes))
        if slide.has_notes_slide:
            notes = slide.notes_slide.notes_text_frame
            if notes is not None and notes.text.strip():
                parts.append("notes: " + notes.text.strip())
    return "\n".join(parts)


def _pptx_shapes(shapes) -> list[str]:  # python-pptx shape tree; untyped because the SDK is imported lazily
    parts: list[str] = []
    for shape in shapes:
        if getattr(shape, "has_text_frame", False) and shape.text_frame.text.strip():
            parts.append(shape.text_frame.text.strip())
        if getattr(shape, "has_table", False):
            for row in shape.table.rows:
                cells = [c.text.strip() for c in row.cells]
                if any(cells):
                    parts.append(" | ".join(cells))
        inner = getattr(shape, "shapes", None)  # group shapes
        if inner is not None:
            parts.extend(_pptx_shapes(inner))
    return parts


def _xls(data: bytes) -> str:
    """Legacy BIFF workbook: same sheet/row layout as the .xlsx path."""
    import xlrd

    wb = xlrd.open_workbook(file_contents=data, logfile=io.StringIO(), on_demand=True)
    parts = []
    for sheet in wb.sheets():
        parts.append(f"## sheet: {sheet.name}")
        for r in range(sheet.nrows):
            cells = [_xls_cell(v) for v in sheet.row_values(r) if v not in ("", None)]
            if cells:
                parts.append(" | ".join(cells))
    return "\n".join(parts)


def _xls_cell(value: object) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


_DOC_ENCRYPTED = 0x0100  # FibBase.fEncrypted
_DOC_WHICH_TABLE = 0x0200  # FibBase.fWhichTblStm: 1 -> "1Table", 0 -> "0Table"
_DOC_FC_CLX = 0x1A2  # offset of fcClx/lcbClx in FibRgFcLcb97 (nFib >= 0x00C1)
_DOC_PIECE_COMPRESSED = 0x40000000  # Pcd.fc bit 30: 8-bit cp1252 text at fc/2
# Word stores control characters inside the text: \r paragraph, \x07 cell/row mark, \x0b line break,
# \x0c page/section break, \x13 \x14 \x15 field codes, \x01 \x08 embedded objects.
_DOC_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
_DOC_PRINTABLE_RUN = re.compile(r"[\x20-\x7e\xa0-ɏ\t\n]{4,}")
_DOC_WORD = re.compile(r"[A-Za-z]{2,}")


def _doc(data: bytes) -> str:
    """Word 97-2003 binary. Reads the piece table (CLX in the table stream) and falls back to a
    printable-run scan of the WordDocument stream when the FIB cannot be trusted."""
    import olefile

    if not olefile.isOleFile(data=data):
        raise ValueError("not an OLE compound file (a .doc that is really RTF or DOCX is not supported)")
    ole = olefile.OleFileIO(io.BytesIO(data))
    try:
        if not ole.exists("WordDocument"):
            raise ValueError("no WordDocument stream (not a Word binary file)")
        word = ole.openstream("WordDocument").read()
        if len(word) >= 12 and struct.unpack_from("<H", word, 10)[0] & _DOC_ENCRYPTED:
            raise ValueError("encrypted .doc files are not supported")
        text = ""
        try:
            text = _doc_piece_table(word, ole)
        except (ValueError, struct.error, IndexError, OSError):
            text = ""
        if not text.strip():
            text = _doc_fallback(word)
    finally:
        ole.close()
    return text


def _doc_piece_table(word: bytes, ole) -> str:  # ole: olefile.OleFileIO, untyped because imported lazily
    if word[:2] != b"\xec\xa5":
        raise ValueError("bad FIB signature")
    flags = struct.unpack_from("<H", word, 10)[0]
    table_name = "1Table" if flags & _DOC_WHICH_TABLE else "0Table"
    if not ole.exists(table_name):
        raise ValueError(f"missing {table_name} stream")
    table = ole.openstream(table_name).read()
    fc_clx, lcb_clx = struct.unpack_from("<II", word, _DOC_FC_CLX)
    clx = table[fc_clx : fc_clx + lcb_clx]
    pos = 0
    while pos < len(clx) and clx[pos] == 0x01:  # Prc (property modifiers) precede the Pcdt
        pos += 3 + struct.unpack_from("<H", clx, pos + 1)[0]
    if pos >= len(clx) or clx[pos] != 0x02:
        raise ValueError("no Pcdt in CLX")
    lcb = struct.unpack_from("<I", clx, pos + 1)[0]
    plc = clx[pos + 5 : pos + 5 + lcb]
    n = (lcb - 4) // 12
    if n <= 0 or len(plc) < lcb:
        raise ValueError("empty piece table")
    cps = struct.unpack_from(f"<{n + 1}I", plc, 0)
    pieces: list[str] = []
    for i in range(n):
        fc = struct.unpack_from("<I", plc, 4 * (n + 1) + 8 * i + 2)[0]
        count = cps[i + 1] - cps[i]
        if fc & _DOC_PIECE_COMPRESSED:
            start = (fc & ~_DOC_PIECE_COMPRESSED) // 2
            pieces.append(word[start : start + count].decode("cp1252", errors="replace"))
        else:
            pieces.append(word[fc : fc + 2 * count].decode("utf-16-le", errors="replace"))
    return _doc_clean("".join(pieces))


def _doc_clean(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x07", " | ").replace("\x0b", "\n")
    return _DOC_CONTROL.sub("", text).strip()


def _doc_fallback(word: bytes) -> str:
    """Keep runs of printable Latin text, trying both encodings Word uses and keeping the one that
    reads most like prose (the most word-like tokens); binary junk decodes to few words either way."""
    best, best_words = "", -1
    for encoding in ("cp1252", "utf-16-le"):
        decoded = word.decode(encoding, errors="replace").replace("\r", "\n")
        runs = [
            m.group(0).strip()
            for m in _DOC_PRINTABLE_RUN.finditer(decoded)
            if sum(ch.isascii() and ch.isalpha() for ch in m.group(0)) >= 2
        ]
        candidate = "\n".join(r for r in runs if r)
        words = len(_DOC_WORD.findall(candidate))
        if words > best_words:
            best, best_words = candidate, words
    return best
