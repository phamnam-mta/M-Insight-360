import re

from app.extraction.evidence_search import find_all_matches, find_all_matches_by_period
from app.extraction.types import ExtractedDocument, ExtractedTable

PATTERN = re.compile(r"von chu so huu[:\s]*(-?[\d.,]+)")


def _pdf_doc(pages: list[str], file_id="f1", filename="bctc.pdf"):
    doc = ExtractedDocument(
        filename=filename, doc_type="pdf", text="\n".join(pages), tables=[],
        extraction_method="text_layer", confidence=1.0,
    )
    doc.file_id = file_id
    doc.pages = pages
    return doc


def test_finds_match_on_specific_page_not_whole_doc():
    doc = _pdf_doc(["Trang mo dau khong co gi", "Von chu so huu: 500.000.000"])
    matches = find_all_matches([doc], PATTERN)
    assert len(matches) == 1
    ref, value = matches[0]
    assert ref.location == "Trang 2"
    assert ref.file_id == "f1"
    assert "500.000.000" in value


def test_finds_matches_across_multiple_documents():
    doc1 = _pdf_doc(["Von chu so huu: 500.000.000"], file_id="f1", filename="a.pdf")
    doc2 = _pdf_doc(["Von chu so huu: 900.000.000"], file_id="f2", filename="b.pdf")
    matches = find_all_matches([doc1, doc2], PATTERN)
    assert len(matches) == 2
    assert {m[0].filename for m in matches} == {"a.pdf", "b.pdf"}


def test_xlsx_table_cites_sheet_and_row():
    doc = ExtractedDocument(
        filename="bctc.xlsx", doc_type="xlsx", text="", tables=[
            ExtractedTable(rows=[["Chi tieu", "Gia tri"], ["Von chu so huu", "700.000.000"]], sheet_or_page="BCĐKT")
        ], extraction_method="spreadsheet", confidence=1.0,
    )
    doc.file_id = "f3"
    matches = find_all_matches([doc], PATTERN)
    assert len(matches) == 1
    ref, value = matches[0]
    assert "BCĐKT" in ref.location
    assert "dòng 2" in ref.location
    assert "700.000.000" in value


def test_docx_falls_back_to_whole_document_location():
    doc = ExtractedDocument(
        filename="pakd.docx", doc_type="docx", text="Von chu so huu: 300.000.000",
        tables=[], extraction_method="docx", confidence=1.0,
    )
    doc.file_id = "f4"
    matches = find_all_matches([doc], PATTERN)
    assert len(matches) == 1
    assert matches[0][0].location == "Toàn văn bản"


def test_docx_paragraph_text_still_searched_when_doc_also_has_tables():
    # Real BCTC docx uploads almost always have both narrative paragraphs and
    # tables. docx_parser.py extracts these into disjoint doc.text/doc.tables
    # (unlike xlsx/csv, where they're the same content) — a field written only
    # as plain paragraph text must still be found even when the document also
    # contains an unrelated table.
    doc = ExtractedDocument(
        filename="pakd.docx", doc_type="docx", text="Von chu so huu: 300.000.000",
        tables=[ExtractedTable(rows=[["Von dieu le", "500.000.000"]], sheet_or_page="table 1")],
        extraction_method="docx", confidence=1.0,
    )
    doc.file_id = "f5"
    matches = find_all_matches([doc], PATTERN)
    assert len(matches) == 1
    assert matches[0][0].location == "Toàn văn bản"
    assert "300.000.000" in matches[0][1]


def test_xlsx_with_tables_does_not_duplicate_matches_from_text():
    # xlsx/csv build doc.text from the exact same rows as doc.tables (see
    # xlsx_csv_parser.py) — re-scanning doc.text there would double-count
    # every match, so xlsx/csv must still stop after searching tables.
    doc = ExtractedDocument(
        filename="bctc.xlsx", doc_type="xlsx",
        text="Chi tieu | Gia tri\nVon chu so huu | 700.000.000",
        tables=[
            ExtractedTable(rows=[["Chi tieu", "Gia tri"], ["Von chu so huu", "700.000.000"]], sheet_or_page="BCĐKT")
        ],
        extraction_method="spreadsheet", confidence=1.0,
    )
    doc.file_id = "f6"
    matches = find_all_matches([doc], PATTERN)
    assert len(matches) == 1


def test_xlsx_two_column_label_value_row_matches_colon_style_pattern():
    # The standard spreadsheet layout is label and value in separate cells
    # (e.g. "Von chu so huu" | "9.000.000.000"), which find_all_matches joins
    # with " | " for display. Every EB field pattern (financial_inputs.py,
    # overview/*.py) is written colon-style ("...[:\s]*(-?[\d.,]+)") to match
    # prose like "Von chu so huu: 9.000.000.000" — a bare pipe satisfies
    # neither ":" nor "\s", so this extremely common layout must still match
    # via the same colon-style pattern the rest of the codebase already uses.
    doc = ExtractedDocument(
        filename="bctc.xlsx", doc_type="xlsx", text="", tables=[
            ExtractedTable(rows=[["Von chu so huu", "9.000.000.000"]], sheet_or_page="BCĐKT")
        ], extraction_method="spreadsheet", confidence=1.0,
    )
    doc.file_id = "f7"
    matches = find_all_matches([doc], PATTERN)
    assert len(matches) == 1
    assert "9.000.000.000" in matches[0][1]


def test_no_match_returns_empty_list():
    doc = _pdf_doc(["Khong co gi lien quan"])
    assert find_all_matches([doc], PATTERN) == []


def test_free_text_capture_preserves_vietnamese_diacritics():
    industry_pattern = re.compile(r"nganh nghe kinh doanh[:\s]*([^\n]+)")
    doc = _pdf_doc(["Nganh nghe kinh doanh: Bán lẻ hàng tiêu dùng"])
    matches = find_all_matches([doc], industry_pattern)
    assert matches[0][1] == "Bán lẻ hàng tiêu dùng"


_TSNH_PATTERN = re.compile(r"tai san ngan han[:\s]*(-?[\d.,]+)")


def test_find_all_matches_by_period_splits_current_and_prior_year_columns():
    table = ExtractedTable(
        rows=[
            ["Chi tieu", "31/12/2025", "31/12/2024"],
            ["Tai san ngan han", "100.000.000", "90.000.000"],
        ],
        sheet_or_page="BCDKT",
    )
    doc = ExtractedDocument(filename="bctc.xlsx", doc_type="xlsx", text="", tables=[table], extraction_method="spreadsheet", confidence=1.0)
    results = find_all_matches_by_period([doc], _TSNH_PATTERN)
    by_year = {year: raw for _, raw, year, _ in results}
    assert by_year["2025"] == "100.000.000"
    assert by_year["2024"] == "90.000.000"
    assert all(conf == "explicit" for *_, conf in results)


def test_find_all_matches_by_period_single_column_falls_back_to_primary_year_guessed():
    table = ExtractedTable(rows=[["Chi tieu", "Gia tri"], ["Tai san ngan han", "50.000.000"]], sheet_or_page="S1")
    doc = ExtractedDocument(
        filename="bctc.xlsx", doc_type="xlsx", text="Tai ngay 31/12/2025",
        tables=[table], extraction_method="spreadsheet", confidence=1.0,
    )
    results = find_all_matches_by_period([doc], _TSNH_PATTERN)
    assert len(results) == 1
    _, raw, year, confidence = results[0]
    assert raw == "50.000.000"
    assert year == "2025"
    assert confidence == "suy_doan"


def test_find_all_matches_by_period_no_primary_year_found_yields_khong_xac_dinh():
    table = ExtractedTable(rows=[["Chi tieu", "Gia tri"], ["Tai san ngan han", "50.000.000"]], sheet_or_page="S1")
    doc = ExtractedDocument(filename="bctc.xlsx", doc_type="xlsx", text="", tables=[table], extraction_method="spreadsheet", confidence=1.0)
    results = find_all_matches_by_period([doc], _TSNH_PATTERN)
    assert results[0][2] == "khong_xac_dinh"
