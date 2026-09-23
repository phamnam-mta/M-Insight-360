from app.agents.eb.canonical import build_canonical
from app.agents.eb.overview.revenue import evaluate_revenue_12m, evaluate_revenue_6m_statement
from app.extraction.types import ExtractedDocument, ExtractedTable


def _pdf(text: str):
    doc = ExtractedDocument(
        filename="bctc.pdf", doc_type="pdf", text=text, tables=[],
        extraction_method="text_layer", confidence=1.0,
    )
    doc.file_id = "bctc.pdf"
    doc.pages = [text]
    return doc


def _canonical_fields(docs):
    canonical = build_canonical(docs)
    if not canonical.fields_by_year:
        return {}
    return next(iter(canonical.fields_by_year.values()))


def test_revenue_12m_pass_within_range():
    row = evaluate_revenue_12m(_canonical_fields([_pdf("Doanh thu thuan: 50.000.000.000")]))
    assert row.result == "PASS"
    assert row.observed.value == 50_000_000_000


def test_revenue_12m_fail_below_minimum():
    row = evaluate_revenue_12m(_canonical_fields([_pdf("Doanh thu thuan: 5.000.000.000")]))
    assert row.result == "FAIL"


def test_revenue_12m_fail_at_or_above_maximum():
    row = evaluate_revenue_12m(_canonical_fields([_pdf("Doanh thu thuan: 1.000.000.000.000")]))
    assert row.result == "FAIL"


def test_revenue_12m_insufficient_data_without_match():
    row = evaluate_revenue_12m(_canonical_fields([_pdf("khong co gi")]))
    assert row.result == "INSUFFICIENT_DATA"


def _statement_doc(rows, filename="sao_ke.xlsx"):
    doc = ExtractedDocument(
        filename=filename, doc_type="xlsx", text="", tables=[
            ExtractedTable(rows=rows, sheet_or_page="Sheet1")
        ], extraction_method="spreadsheet", confidence=1.0,
    )
    doc.file_id = filename
    return doc


def test_revenue_6m_statement_insufficient_data_without_statement():
    row = evaluate_revenue_6m_statement([_pdf("khong lien quan")])
    assert row.result == "INSUFFICIENT_DATA"
    assert row.observed.value is None


def test_revenue_6m_statement_insufficient_data_even_with_statement():
    header = ["Ngay", "So but toan", "Ghi No", "Ghi Co", "Dien giai", "Doi tac", "TK doi tac", "NH doi tac", "Loai tien", "Nguon"]
    row1 = ["01/01/2026", "1", "0", "100000000", "thu tien hang", "Cong ty A", "", "", "VND", ""]
    doc = _statement_doc([header, row1])
    row = evaluate_revenue_6m_statement([doc])
    assert row.result == "INSUFFICIENT_DATA"
    assert row.observed.value == 100_000_000
    assert row.observed.status == "COMPUTED"
    assert row.reason_if_incomplete is not None
