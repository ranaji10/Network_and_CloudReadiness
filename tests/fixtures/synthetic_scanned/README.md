# SYNTHETIC test data (scanned documents)

Everything in this folder is invented for tests. It describes the same fictional company as
`../synthetic_acme/` ("Acme Widgets") and contains no real names, addresses, credentials or
infrastructure. The files exercise the `ocr` extra of `readiness.ingestion.extract` (ING-08):

| File | Format | Built with |
|---|---|---|
| `backup_standard_scanned.pdf` | image-only PDF, two A4 pages at 150 dpi | Pillow: short paragraphs drawn in DejaVu Sans 48 px on a bilevel canvas, saved with `Image.save(..., save_all=True)` |
| `firewall_change_notice.png` | bilevel PNG | Pillow: the same rendering, one short notice |

The PDF carries no text layer, so `pypdf` extracts nothing from it and the only way to read it is the
OCR path (pypdfium2 render, Tesseract). The large plain font keeps Tesseract's output exact, which lets
`tests/test_extract_ocr.py` assert whole phrases. Keep every file far below 200 KB.
