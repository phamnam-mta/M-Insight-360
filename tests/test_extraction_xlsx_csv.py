from app.extraction.xlsx_csv_parser import extract_csv, extract_xlsx


def test_extract_xlsx_reads_all_sheets(fixtures_dir):
    doc = extract_xlsx(str(fixtures_dir / "sample.xlsx"), "sample.xlsx")
    assert doc.doc_type == "xlsx"
    assert doc.extraction_method == "spreadsheet"
    assert len(doc.tables) == 2
    sheet_names = {t.sheet_or_page for t in doc.tables}
    assert sheet_names == {"Thang01", "Thang02"}
    thang01 = next(t for t in doc.tables if t.sheet_or_page == "Thang01")
    assert thang01.rows[1] == ["01/01/2026", "1000000"]


def test_extract_csv_handles_utf8_bom(fixtures_dir):
    doc = extract_csv(str(fixtures_dir / "sample.csv"), "sample.csv")
    assert doc.doc_type == "csv"
    assert doc.tables[0].rows[0] == ["Ngay", "Dien giai", "So tien"]
    # BOM must not leak into the first header cell
    assert not doc.tables[0].rows[0][0].startswith("﻿")
    assert doc.tables[0].rows[1] == ["01/01/2026", "Chuyen khoan", "500000"]
