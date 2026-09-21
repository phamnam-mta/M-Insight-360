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


def test_extract_xlsx_handles_a_completely_empty_sheet(fixtures_dir):
    doc = extract_xlsx(str(fixtures_dir / "sample_with_empty_sheet.xlsx"), "sample_with_empty_sheet.xlsx")
    assert doc.doc_type == "xlsx"
    sheet_names = {t.sheet_or_page for t in doc.tables}
    assert sheet_names == {"Empty", "HasData"}
    empty_table = next(t for t in doc.tables if t.sheet_or_page == "Empty")
    assert empty_table.rows == []


def test_extract_csv_handles_utf8_bom(fixtures_dir):
    doc = extract_csv(str(fixtures_dir / "sample.csv"), "sample.csv")
    assert doc.doc_type == "csv"
    assert doc.tables[0].rows[0] == ["Ngay", "Dien giai", "So tien"]
    # BOM must not leak into the first header cell
    assert not doc.tables[0].rows[0][0].startswith("﻿")
    assert doc.tables[0].rows[1] == ["01/01/2026", "Chuyen khoan", "500000"]


def test_extract_csv_handles_cp1258_legacy_vietnamese_encoding(fixtures_dir):
    doc = extract_csv(str(fixtures_dir / "sample_cp1258.csv"), "sample_cp1258.csv")
    assert doc.doc_type == "csv"
    assert doc.tables[0].rows[0] == ["Ngày", "Khách hàng", "Ghi chú"]
    assert doc.tables[0].rows[1] == ["01/01/2026", "Khách hàng A", "Ghi chú thanh toán"]
    assert any("cp1258" in w.lower() or "encoding" in w.lower() or "mã hóa" in w.lower() for w in doc.warnings)


def test_extract_csv_handles_utf16_encoding(fixtures_dir):
    doc = extract_csv(str(fixtures_dir / "sample_utf16.csv"), "sample_utf16.csv")
    assert doc.doc_type == "csv"
    assert doc.tables[0].rows[0] == ["Ngày", "Khách hàng", "Ghi chú"]
