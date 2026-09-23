from app.extraction.period_columns import (
    detect_document_primary_year, detect_table_primary_year, detect_year_columns,
)
from app.extraction.types import ExtractedDocument, ExtractedTable


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


def test_table_primary_year_ignores_dates_in_other_tables():
    # Real-world bug: a single upload bundles a BCTC summary sheet (fiscal
    # year 2025, reported via "Tai ngay 31/12/2025" in its own text — no
    # explicit year in its header row) together with an unrelated bank
    # statement ("sao ke") sheet whose hundreds of transaction rows carry
    # dates into 2026. detect_document_primary_year scans the whole
    # document's text and would wrongly return 2026 (the max year found
    # ANYWHERE in the upload). Each table's own primary year must be
    # derived only from that table's own rows.
    bctc_table = ExtractedTable(
        sheet_or_page="10_BCTC_TOM_TAT",
        rows=[
            ["BANG CAN DOI KE TOAN"],
            ["Tai ngay 31/12/2025"],
            ["Chi tieu", "So cuoi nam", "So dau nam"],
            ["Von chu so huu", "580965107518", "500000000000"],
        ],
    )
    saoke_table = ExtractedTable(
        sheet_or_page="SAO KE",
        rows=[
            ["Ngay", "Dien giai", "So tien"],
            ["31/01/2026", "Giao dich 1", "1000000"],
            ["28/02/2026", "Giao dich 2", "2000000"],
        ],
    )
    assert detect_table_primary_year(bctc_table) == 2025
    assert detect_table_primary_year(saoke_table) == 2026
