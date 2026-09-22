from app.extraction.period_columns import detect_document_primary_year, detect_year_columns
from app.extraction.types import ExtractedDocument


def _doc(text: str) -> ExtractedDocument:
    return ExtractedDocument(filename="f.pdf", doc_type="pdf", text=text, tables=[], extraction_method="text_layer", confidence=1.0)


def test_detects_primary_year_from_reporting_date():
    doc = _doc("BANG CAN DOI KE TOAN\nTai ngay 31/12/2025\n...")
    assert detect_document_primary_year(doc) == 2025


def test_detects_primary_year_picks_newest_when_multiple_years_present():
    doc = _doc("Nam tai chinh ket thuc ngay 31/12/2025, so sanh voi 2024")
    assert detect_document_primary_year(doc) == 2025


def test_no_year_found_returns_none():
    doc = _doc("Khong co thong tin nam nao trong van ban nay")
    assert detect_document_primary_year(doc) is None


def test_year_columns_explicit_year_in_header():
    mapping = detect_year_columns(["Chi tieu", "31/12/2025", "31/12/2024"], primary_year=2025)
    assert mapping == {1: "2025", 2: "2024"}


def test_year_columns_relative_labels_resolved_against_primary_year():
    mapping = detect_year_columns(["Chi tieu", "So cuoi nam", "So dau nam"], primary_year=2025)
    assert mapping == {1: "2025", 2: "2024"}


def test_year_columns_no_signal_column_omitted():
    mapping = detect_year_columns(["Chi tieu", "Ghi chu"], primary_year=2025)
    assert mapping == {}


def test_year_columns_without_primary_year_relative_labels_unresolved():
    mapping = detect_year_columns(["Chi tieu", "So cuoi nam"], primary_year=None)
    assert mapping == {}
