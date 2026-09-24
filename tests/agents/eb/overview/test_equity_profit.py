from app.agents.eb.canonical import build_canonical
from app.agents.eb.overview.equity_profit import (
    evaluate_equity, evaluate_gross_profit_less_interest, evaluate_lnst_pakd,
)
from app.extraction.types import ExtractedDocument


def _doc(text: str, filename="doc.pdf"):
    doc = ExtractedDocument(
        filename=filename, doc_type="pdf", text=text, tables=[],
        extraction_method="text_layer", confidence=1.0,
    )
    doc.file_id = filename
    doc.pages = [text]
    return doc


def _canonical_fields(docs):
    canonical = build_canonical(docs)
    if not canonical.fields_by_year:
        return {}
    return next(iter(canonical.fields_by_year.values()))


def test_equity_pass_when_positive():
    row = evaluate_equity(_canonical_fields([_doc("Von chu so huu: 500.000.000")]))
    assert row.result == "PASS"


def test_equity_fail_when_non_positive():
    row = evaluate_equity(_canonical_fields([_doc("Von chu so huu: 0")]))
    assert row.result == "FAIL"


def test_lnst_pakd_pass_when_positive():
    row = evaluate_lnst_pakd([_doc("LNST theo PAKD: 200.000.000")])
    assert row.result == "PASS"


def test_lnst_pakd_insufficient_without_match():
    row = evaluate_lnst_pakd([_doc("khong co gi")])
    assert row.result == "INSUFFICIENT_DATA"


def test_gross_profit_less_interest_computed_and_passes():
    doc = _doc("Loi nhuan gop: 1.000.000.000\nChi phi lai vay: 300.000.000")
    row = evaluate_gross_profit_less_interest(_canonical_fields([doc]))
    assert row.result == "PASS"
    assert row.observed.value == 700_000_000
    assert row.observed.formula == "loi_nhuan_gop - chi_phi_lai_vay"


def test_gross_profit_less_interest_fails_when_negative():
    doc = _doc("Loi nhuan gop: 100.000.000\nChi phi lai vay: 300.000.000")
    row = evaluate_gross_profit_less_interest(_canonical_fields([doc]))
    assert row.result == "FAIL"


def test_gross_profit_less_interest_insufficient_when_either_missing():
    row = evaluate_gross_profit_less_interest(_canonical_fields([_doc("Loi nhuan gop: 100.000.000")]))
    assert row.result == "INSUFFICIENT_DATA"
    assert "lãi vay" in row.reason_if_incomplete


def test_equity_condition_reads_same_canonical_value_as_financial_inputs_t32():
    from app.agents.eb.canonical import build_canonical
    from app.agents.eb.financial_inputs import financial_inputs_by_period
    from app.extraction.types import ExtractedDocument, ExtractedTable

    table = ExtractedTable(
        rows=[["Chi tieu", "31/12/2025"], ["Von chu so huu", "580965107518"]],
        sheet_or_page="10_BCTC_TOM_TAT",
    )
    doc = ExtractedDocument(filename="f.xlsx", doc_type="xlsx", text="", tables=[table], extraction_method="spreadsheet", confidence=1.0)
    canonical = build_canonical([doc])
    financial_inputs = financial_inputs_by_period(canonical)

    condition_row = evaluate_equity(canonical.fields_by_year["2025"])

    assert condition_row.observed.value == financial_inputs["2025"].inputs.equity_vnd == 580965107518.0


def test_gross_profit_less_interest_reads_canonical():
    from app.agents.eb.canonical import build_canonical
    from app.extraction.types import ExtractedDocument, ExtractedTable

    table = ExtractedTable(
        rows=[
            ["Chi tieu", "31/12/2025"],
            ["Loi nhuan gop", "20000000000"],
            ["Chi phi lai vay", "5000000000"],
        ],
        sheet_or_page="KQKD",
    )
    doc = ExtractedDocument(filename="f.xlsx", doc_type="xlsx", text="", tables=[table], extraction_method="spreadsheet", confidence=1.0)
    canonical = build_canonical([doc])
    row = evaluate_gross_profit_less_interest(canonical.fields_by_year["2025"])
    assert row.observed.value == 15_000_000_000.0
    assert row.result == "PASS"


def test_equity_condition_reports_pending_review_not_missing_when_conflicting():
    # Review finding I6: financial_inputs_by_period marks a conflicting
    # field PENDING_REVIEW; the condition block used to always say
    # MISSING_DATA ("khong tim thay du lieu") for the same underlying
    # CanonicalField, which is a wrong and contradictory message when the
    # data DID exist but disagreed across sheets.
    from app.agents.eb.canonical import CanonicalField
    from app.engine.core.types import EvidenceRef

    conflicting_field = CanonicalField(
        ma="BS_EQUITY", nhan="Vốn chủ sở hữu", gia_tri=None, don_vi="VND", nam="2025",
        nguon=None, sheet=None, loai="chua_co", co_gia_tri=False,
        evidence=[EvidenceRef(file_id="f", filename="f.xlsx", location="Sheet 'A', dòng 1", original_text="x")],
    )
    row = evaluate_equity({"BS_EQUITY": conflicting_field})
    assert row.result == "INSUFFICIENT_DATA"
    assert row.observed.status == "PENDING_REVIEW"
    assert "khác nhau" in row.reason_if_incomplete
