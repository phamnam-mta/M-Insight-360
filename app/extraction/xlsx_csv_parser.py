import csv

import openpyxl

from .types import ExtractedDocument, ExtractedTable


def extract_xlsx(file_path: str, filename: str) -> ExtractedDocument:
    wb = openpyxl.load_workbook(file_path, data_only=True)
    tables = []
    text_parts = []
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        rows = []
        for row in ws.iter_rows(values_only=True):
            str_row = ["" if cell is None else str(cell) for cell in row]
            rows.append(str_row)
            text_parts.append(" | ".join(str_row))
        tables.append(ExtractedTable(rows=rows, sheet_or_page=sheet_name))
    return ExtractedDocument(
        filename=filename,
        doc_type="xlsx",
        text="\n".join(text_parts),
        tables=tables,
        extraction_method="spreadsheet",
        confidence=1.0,
    )


# Tried in order. utf-8-sig handles both plain UTF-8 and UTF-8-with-BOM.
# utf-16 covers Excel's "Unicode Text" CSV export. cp1258 (Windows Vietnamese)
# and latin-1 cover legacy core-banking exports; latin-1 never raises, so it
# guarantees the chain terminates.
_CSV_ENCODINGS = ["utf-8-sig", "utf-16", "cp1258", "latin-1"]


def extract_csv(file_path: str, filename: str) -> ExtractedDocument:
    with open(file_path, "rb") as f:
        raw = f.read()

    rows: list[list[str]] = []
    used_encoding = None
    for encoding in _CSV_ENCODINGS:
        try:
            decoded = raw.decode(encoding)
        except UnicodeDecodeError:
            continue
        rows = list(csv.reader(decoded.splitlines()))
        used_encoding = encoding
        break

    warnings = []
    if used_encoding and used_encoding != "utf-8-sig":
        warnings.append(
            f"File CSV không phải UTF-8 — đã đọc bằng mã hóa {used_encoding}. "
            "Vui lòng kiểm tra lại nếu dữ liệu hiển thị sai."
        )

    text = "\n".join(" | ".join(row) for row in rows)
    return ExtractedDocument(
        filename=filename,
        doc_type="csv",
        text=text,
        tables=[ExtractedTable(rows=rows, sheet_or_page="csv")],
        extraction_method="spreadsheet",
        confidence=1.0,
        warnings=warnings,
    )
