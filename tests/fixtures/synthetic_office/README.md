# SYNTHETIC test data (Office formats)

Everything in this folder is invented for tests. It describes the same fictional company as
`../synthetic_acme/` ("Acme Widgets") and contains no real names, addresses, credentials or
infrastructure. The files exercise the `office` extra of `readiness.ingestion.extract`:

| File | Format | Built with |
|---|---|---|
| `segmentation_roadmap.pptx` | PowerPoint 2007+ | python-pptx: two slides, a table and speaker notes |
| `asset_inventory.xls` | Excel 97-2003 (BIFF8) | openpyxl workbook converted headless by LibreOffice |
| `backup_standard.doc` | Word 97-2003 binary | python-docx document converted headless by LibreOffice |

The `.doc` carries a real FIB and piece table (8-bit cp1252 text), so `tests/test_extract_office.py`
covers the piece-table reader with this file and the UTF-16 / fallback branches with in-memory bytes.
Keep every file far below 1 MB.
