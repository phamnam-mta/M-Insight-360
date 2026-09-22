from app.agents.eb.financial_inputs import extract_financial_inputs
from app.extraction.types import ExtractedDocument


def _doc(text: str, filename: str = "bctc.pdf") -> ExtractedDocument:
    doc = ExtractedDocument(
        filename=filename, doc_type="pdf", text=text, tables=[],
        extraction_method="text_layer", confidence=1.0,
    )
    doc.file_id = filename
    doc.pages = [text]
    return doc


def test_extracts_equity_and_current_assets_liabilities():
    text = (
        "Von chu so huu: 500,000,000\n"
        "Tai san ngan han: 2,000,000,000\n"
        "No ngan han: 2,500,000,000\n"
    )
    inputs, _ = extract_financial_inputs([_doc(text)])
    assert inputs.equity_vnd == 500_000_000
    assert inputs.current_assets_vnd == 2_000_000_000
    assert inputs.current_liabilities_vnd == 2_500_000_000


def test_extracts_cfo():
    text = "Luu chuyen tien thuan tu hoat dong kinh doanh: -1,188,000,000"
    inputs, _ = extract_financial_inputs([_doc(text)])
    assert inputs.cfo_vnd == -1_188_000_000


def test_extracts_short_term_debt_and_total_liabilities():
    text = "Vay ngan han: 39,000,000\nTong no phai tra: 3,000,000,000"
    inputs, _ = extract_financial_inputs([_doc(text)])
    assert inputs.short_term_debt_vnd == 39_000_000
    assert inputs.total_liabilities_vnd == 3_000_000_000


def test_extracts_ebit_and_interest_expense():
    text = "Loi nhuan truoc thue va lai vay (EBIT): 800,000,000\nChi phi lai vay: 200,000,000"
    inputs, _ = extract_financial_inputs([_doc(text)])
    assert inputs.ebit_vnd == 800_000_000
    assert inputs.interest_expense_vnd == 200_000_000


def test_missing_fields_are_none():
    inputs, _ = extract_financial_inputs([_doc("Tai lieu khong co so lieu tai chinh")])
    assert inputs.equity_vnd is None
    assert inputs.cfo_vnd is None


def test_extracts_vn_locale_figures_without_silent_truncation():
    # Regression: the capture groups were (-?[\d,]+), which stopped at the first
    # "." — "5.000.000.000" was captured as "5" and parsed as 5.0, corrupting
    # every downstream metric by a factor of ~10^6.
    text = (
        "Von chu so huu: 5.000.000.000\n"
        "Tai san ngan han: 3.500.000.000\n"
        "No ngan han: 2.000.000.000\n"
        "Luu chuyen tien thuan tu hoat dong kinh doanh: -1.188.000.000\n"
    )
    inputs, _ = extract_financial_inputs([_doc(text)])
    assert inputs.equity_vnd == 5_000_000_000
    assert inputs.current_assets_vnd == 3_500_000_000
    assert inputs.current_liabilities_vnd == 2_000_000_000
    assert inputs.cfo_vnd == -1_188_000_000


def test_vn_locale_balance_sheet_yields_correct_nwc_sign():
    # True NWC = 3.5bn - 2.0bn = +1.5bn; the truncation bug computed 3.5 - 2.0
    # in *units* and let RF01 fire on a company with healthy working capital.
    from app.agents.eb.liquidity import compute_nwc

    text = "Tai san ngan han: 3.500.000.000\nNo ngan han: 2.000.000.000\n"
    inputs, _ = extract_financial_inputs([_doc(text)])
    assert compute_nwc(inputs).value == 1_500_000_000


def test_returns_evidence_for_matched_field():
    text = "Von chu so huu: 500,000,000\n"
    inputs, evidence = extract_financial_inputs([_doc(text)])
    assert inputs.equity_vnd == 500_000_000
    ev = evidence["equity_vnd"]
    assert ev.status == "COMPUTED"
    assert len(ev.evidence) == 1
    assert ev.evidence[0].filename == "bctc.pdf"


def test_missing_field_has_missing_data_evidence_status():
    inputs, evidence = extract_financial_inputs([_doc("khong co gi")])
    assert inputs.equity_vnd is None
    assert evidence["equity_vnd"].status == "MISSING_DATA"
    assert evidence["equity_vnd"].evidence == []


def test_conflicting_values_across_files_yield_pending_review_and_none_value():
    doc1 = _doc("Von chu so huu: 500.000.000", filename="a.pdf")
    doc2 = _doc("Von chu so huu: 900.000.000", filename="b.pdf")
    inputs, evidence = extract_financial_inputs([doc1, doc2])
    assert inputs.equity_vnd is None  # never silently pick one
    ev = evidence["equity_vnd"]
    assert ev.status == "PENDING_REVIEW"
    assert len(ev.evidence) == 2
    assert {e.filename for e in ev.evidence} == {"a.pdf", "b.pdf"}


def test_same_value_confirmed_in_two_files_stays_computed():
    doc1 = _doc("Von chu so huu: 500.000.000", filename="a.pdf")
    doc2 = _doc("Von chu so huu: 500.000.000", filename="b.pdf")
    inputs, evidence = extract_financial_inputs([doc1, doc2])
    assert inputs.equity_vnd == 500_000_000
    assert evidence["equity_vnd"].status == "COMPUTED"
    assert len(evidence["equity_vnd"].evidence) == 2


def test_new_fields_exist_on_dataclass():
    from app.agents.eb.financial_inputs import EbFinancialInputs

    inputs = EbFinancialInputs()
    for f in (
        "net_revenue_vnd", "pbt_vnd", "pat_vnd", "depreciation_vnd",
        "non_current_assets_vnd", "long_term_debt_vnd", "finance_lease_debt_vnd",
        "receivables_vnd", "inventory_vnd", "payables_vnd", "cash_vnd",
        "total_principal_due_vnd",
    ):
        assert hasattr(inputs, f)
        assert getattr(inputs, f) is None


def test_new_field_patterns_match_expected_labels():
    from app.agents.eb.financial_inputs import _FIELD_PATTERNS

    cases = {
        "net_revenue_vnd": "doanh thu thuan: 100.000.000",
        "pbt_vnd": "loi nhuan truoc thue: 50.000.000",
        "pat_vnd": "loi nhuan sau thue: 40.000.000",
        "depreciation_vnd": "khau hao: 10.000.000",
        "non_current_assets_vnd": "tai san dai han: 200.000.000",
        "long_term_debt_vnd": "no dai han: 30.000.000",
        "finance_lease_debt_vnd": "no thue tai chinh: 5.000.000",
        "receivables_vnd": "phai thu khach hang: 20.000.000",
        "inventory_vnd": "hang ton kho: 15.000.000",
        "payables_vnd": "phai tra nguoi ban: 12.000.000",
        "cash_vnd": "tien va tuong duong tien: 8.000.000",
        "total_principal_due_vnd": "no goc den han: 25.000.000",
    }
    for field, text in cases.items():
        assert _FIELD_PATTERNS[field].search(text), f"{field} pattern did not match {text!r}"
