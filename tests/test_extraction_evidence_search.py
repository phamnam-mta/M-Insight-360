import re

from app.extraction.evidence_search import find_all_matches
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
    pattern = re.compile(r"von chu so huu\s*\|\s*([\d.,]+)")
    matches = find_all_matches([doc], pattern)
    assert len(matches) == 1
    ref, value = matches[0]
    assert "BCĐKT" in ref.location
    assert "dòng 2" in ref.location


def test_docx_falls_back_to_whole_document_location():
    doc = ExtractedDocument(
        filename="pakd.docx", doc_type="docx", text="Von chu so huu: 300.000.000",
        tables=[], extraction_method="docx", confidence=1.0,
    )
    doc.file_id = "f4"
    matches = find_all_matches([doc], PATTERN)
    assert len(matches) == 1
    assert matches[0][0].location == "Toàn văn bản"


def test_no_match_returns_empty_list():
    doc = _pdf_doc(["Khong co gi lien quan"])
    assert find_all_matches([doc], PATTERN) == []


def test_free_text_capture_preserves_vietnamese_diacritics():
    industry_pattern = re.compile(r"nganh nghe kinh doanh[:\s]*([^\n]+)")
    doc = _pdf_doc(["Nganh nghe kinh doanh: Bán lẻ hàng tiêu dùng"])
    matches = find_all_matches([doc], industry_pattern)
    assert matches[0][1] == "Bán lẻ hàng tiêu dùng"
