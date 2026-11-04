"""Turn bytes into text. Pure functions; no network. Unknown types are skipped, never guessed.

Core formats (PDF, DOCX, XLSX, text, structured) are always available. PPTX slides and the legacy
Office binaries (.xls, .doc) need the `office` extra (`uv sync --extra office` / `pip install
readiness[office]`); without it those files are reported with an error instead of raising.

Scanned PDFs and images (`.png`, `.jpg`, `.jpeg`, `.tif`, `.tiff`) need the `ocr` extra plus the
`tesseract-ocr` binary (ING-08). OCR runs inside this process: pypdfium2 renders a page to a bitmap in
memory and pytesseract hands it to the local Tesseract binary; no page or text leaves the machine. A PDF
page is OCR'd only when pypdf finds fewer than `OcrOptions.min_chars_per_page` characters on it, so text
PDFs never touch OCR. Without the extra or the binary a scanned page yields an error string naming the
extra, never an exception, and whatever text pypdf found is still returned."""

from __future__ import annotations

import io
import json
import re
import struct
from dataclasses import dataclass
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
# Raster images go straight to OCR (optional `ocr` extra: pytesseract, pypdfium2, pillow + the tesseract binary).
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}
OCR_EXTRA_HINT = "install the ocr extra (uv sync --extra ocr / pip install readiness[ocr]) and the tesseract-ocr binary"
OCR_DISABLED_HINT = "OCR is disabled (READINESS_OCR_ENABLED=false)"


@dataclass(frozen=True)
class OcrOptions:
    """How scanned pages are handled; mirrors the `READINESS_OCR_*` settings (see config.py)."""

    enabled: bool = True
    min_chars_per_page: int = 20  # a PDF page with fewer extractable characters is treated as scanned
    max_pages: int = 50  # OCR budget per document; pages beyond it are skipped and the result is `truncated`
    dpi: int = 200  # render resolution for PDF pages (Tesseract is happiest around 200-300 dpi)
    languages: str = "eng"  # Tesseract language codes, `+`-joined, each needing its traineddata installed


DEFAULT_OCR = OcrOptions()


@dataclass(frozen=True)
class Extraction:
    """Result of `extract_document`: the text plus metadata only (never logged with content)."""

    text: str
    truncated: bool = False
    error: str | None = None
    ocr_pages: int = 0  # pages (or image frames) whose text came from OCR


class OcrUnavailableError(RuntimeError):
    """The `ocr` extra or the tesseract binary is missing, or OCR is disabled; the message says which."""


def extract_text(
    name: str, data: bytes, max_chars: int = 400_000, ocr: OcrOptions = DEFAULT_OCR
) -> tuple[str, bool, str | None]:
    """Returns (text, truncated, error). Thin wrapper over `extract_document` for callers that do not need
    the OCR metadata."""
    result = extract_document(name, data, max_chars, ocr)
    return result.text, result.truncated, result.error


def extract_document(name: str, data: bytes, max_chars: int = 400_000, ocr: OcrOptions = DEFAULT_OCR) -> Extraction:
    """Dispatch by extension. Failures become `Extraction.error`, never exceptions."""
    ext = PurePosixPath(name.lower()).suffix
    ocr_pages, truncated, note = 0, False, None
    try:
        if ext in TEXT_EXT or ext in STRUCTURED_EXT:
            text = data.decode("utf-8", errors="replace")
            if ext == ".json":
                try:
                    text = json.dumps(json.loads(text), indent=1)
                except ValueError:
                    pass
        elif ext == ".pdf":
            text, ocr_pages, truncated, note = _pdf(data, ocr)
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
        elif ext in IMAGE_EXT:
            text, ocr_pages, truncated = _image(data, ocr)
        else:
            return Extraction("", error=f"unsupported type {ext or '(none)'}")
    except OcrUnavailableError as exc:
        return Extraction("", error=f"{ext} needs {exc}"[:200])
    except ImportError as exc:
        if ext in OFFICE_EXT:
            return Extraction("", error=f"{ext} needs {OFFICE_EXTRA_HINT}: {exc}"[:200])
        return Extraction("", error=f"{type(exc).__name__}: {exc}"[:200])
    except Exception as exc:  # noqa: BLE001 - extraction failures are reported, not fatal
        return Extraction("", error=f"{type(exc).__name__}: {exc}"[:200])
    truncated = truncated or len(text) > max_chars
    return Extraction(text[:max_chars], truncated, note, ocr_pages)


def _pdf(data: bytes, ocr: OcrOptions) -> tuple[str, int, bool, str | None]:
    """Returns (text, ocr_pages, truncated, note). Pages with too little extractable text are treated as
    scanned and OCR'd in place (up to `ocr.max_pages`; the rest are skipped and `truncated` is set). When
    OCR is needed but unavailable the pypdf text is kept and `note` carries the install hint."""
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    pages = [(page.extract_text() or "") for page in reader.pages]
    sparse = [i for i, text in enumerate(pages) if len(text.strip()) < ocr.min_chars_per_page]
    if not ocr.enabled or not sparse:
        return "\n".join(pages), 0, False, None
    budget, skipped = sparse[: ocr.max_pages], len(sparse[ocr.max_pages :])
    try:
        for index, text in zip(budget, _ocr_pdf_pages(data, budget, ocr), strict=True):
            pages[index] = text
    except OcrUnavailableError as exc:
        note = f"{len(sparse)} scanned page(s) not read: needs {exc}"
        return "\n".join(pages), 0, False, note[:200]
    return "\n".join(pages), len(budget), skipped > 0, None


# ---------------------------------------------------------------------------
# Optional `ocr` extra (ING-08): pypdfium2 renders, Pillow decodes images, pytesseract drives the local
# `tesseract` binary. Everything stays in this process; pytesseract's temporary files are its own and short-lived.
# ---------------------------------------------------------------------------


def _image(data: bytes, ocr: OcrOptions) -> tuple[str, int, bool]:
    """Raster image (one frame, or every frame of a multi-page TIFF up to `ocr.max_pages`): OCR only."""
    if not ocr.enabled:
        raise OcrUnavailableError(f"OCR, but {OCR_DISABLED_HINT}")
    try:
        from PIL import Image, ImageSequence
    except ImportError as exc:
        raise OcrUnavailableError(f"{OCR_EXTRA_HINT}: {exc}") from exc
    texts: list[str] = []
    truncated = False
    with Image.open(io.BytesIO(data)) as image:
        for index, frame in enumerate(ImageSequence.Iterator(image)):
            if index >= ocr.max_pages:
                truncated = True
                break
            texts.append(_ocr_image(frame, ocr))
    return "\n".join(texts), len(texts), truncated


def _ocr_pdf_pages(data: bytes, indices: list[int], ocr: OcrOptions) -> list[str]:
    """Render the given pages with pypdfium2 (no poppler, no temp files) and OCR each bitmap."""
    try:
        import pypdfium2
    except ImportError as exc:
        raise OcrUnavailableError(f"{OCR_EXTRA_HINT}: {exc}") from exc
    texts: list[str] = []
    pdf = pypdfium2.PdfDocument(data)
    try:
        for index in indices:
            page = pdf[index]
            try:
                texts.append(_ocr_image(page.render(scale=ocr.dpi / 72).to_pil(), ocr))
            finally:
                page.close()
    finally:
        pdf.close()
    return texts


def _ocr_image(image, ocr: OcrOptions) -> str:  # image: PIL.Image.Image, untyped because imported lazily
    """One bitmap through the local Tesseract binary. A missing binary is reported like a missing extra."""
    try:
        import pytesseract
    except ImportError as exc:
        raise OcrUnavailableError(f"{OCR_EXTRA_HINT}: {exc}") from exc
    if image.mode not in ("L", "RGB"):
        image = image.convert("RGB")
    try:
        text = pytesseract.image_to_string(image, lang=ocr.languages)
    except pytesseract.TesseractNotFoundError as exc:
        raise OcrUnavailableError(f"{OCR_EXTRA_HINT}: {exc}") from exc
    return _ocr_clean(text)


_OCR_BLANK_LINES = re.compile(r"\n{3,}")


def _ocr_clean(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\x0c", "\n")
    return _OCR_BLANK_LINES.sub("\n\n", text).strip()


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
