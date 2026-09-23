from app.agents.eb.canonical import build_canonical
from app.agents.eb.financial_inputs import financial_inputs_by_period
from app.extraction.types import ExtractedDocument


def _doc(text: str, filename: str = "bctc.pdf") -> ExtractedDocument:
    doc = ExtractedDocument(
        filename=filename, doc_type="pdf", text=text, tables=[],
        extraction_method="text_layer", confidence=1.0,
    )
    doc.file_id = filename
    doc.pages = [text]
    return doc


def _only_period(docs):
    """Text-only fixtures carry no explicit year, so every match lands in
    a single "khong_xac_dinh" bucket — return that one period's inputs."""
    by_year = financial_inputs_by_period(build_canonical(docs))
    year = next(iter(by_year))
    return by_year[year].inputs, by_year[year].field_evidence


def test_extracts_equity_and_current_assets_liabilities():
    text = (
        "Von chu so huu: 500,000,000\n"
        "Tai san ngan han: 2,000,000,000\n"
        "No ngan han: 2,500,000,000\n"
    )
    inputs, _ = _only_period([_doc(text)])
    assert inputs.equity_vnd == 500_000_000
    assert inputs.current_assets_vnd == 2_000_000_000
    assert inputs.current_liabilities_vnd == 2_500_000_000


def test_extracts_cfo():
    text = "Luu chuyen tien thuan tu hoat dong kinh doanh: -1,188,000,000"
    inputs, _ = _only_period([_doc(text)])
    assert inputs.cfo_vnd == -1_188_000_000


def test_extracts_short_term_debt_and_total_liabilities():
    text = "Vay ngan han: 39,000,000\nTong no phai tra: 3,000,000,000"
    inputs, _ = _only_period([_doc(text)])
    assert inputs.short_term_debt_vnd == 39_000_000
    assert inputs.total_liabilities_vnd == 3_000_000_000


def test_extracts_ebit_and_interest_expense():
    text = "Loi nhuan truoc thue va lai vay (EBIT): 800,000,000\nChi phi lai vay: 200,000,000"
    inputs, _ = _only_period([_doc(text)])
    assert inputs.ebit_vnd == 800_000_000
    assert inputs.interest_expense_vnd == 200_000_000


def test_missing_fields_yield_no_periods():
    by_year = financial_inputs_by_period(build_canonical([_doc("Tai lieu khong co so lieu tai chinh")]))
    assert by_year == {}


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
    inputs, _ = _only_period([_doc(text)])
    assert inputs.equity_vnd == 5_000_000_000
    assert inputs.current_assets_vnd == 3_500_000_000
    assert inputs.current_liabilities_vnd == 2_000_000_000
    assert inputs.cfo_vnd == -1_188_000_000


def test_vn_locale_balance_sheet_yields_correct_nwc_sign():
    # True NWC = 3.5bn - 2.0bn = +1.5bn; the truncation bug computed 3.5 - 2.0
    # in *units* and let RF01 fire on a company with healthy working capital.
    from app.agents.eb.liquidity import compute_nwc

    text = "Tai san ngan han: 3.500.000.000\nNo ngan han: 2.000.000.000\n"
    inputs, _ = _only_period([_doc(text)])
    assert compute_nwc(inputs).value == 1_500_000_000


def test_returns_evidence_for_matched_field():
    text = "Von chu so huu: 500,000,000\n"
    inputs, evidence = _only_period([_doc(text)])
    assert inputs.equity_vnd == 500_000_000
    ev = evidence["equity_vnd"]
    assert ev.status == "COMPUTED"
    assert len(ev.evidence) == 1
    assert ev.evidence[0].filename == "bctc.pdf"


def test_missing_field_has_missing_data_evidence_status():
    inputs, evidence = _only_period([_doc("Tai san ngan han: 100.000.000")])
    assert inputs.equity_vnd is None
    assert evidence["equity_vnd"].status == "MISSING_DATA"
    assert evidence["equity_vnd"].evidence == []


def test_conflicting_values_across_files_yield_pending_review_and_none_value():
    doc1 = _doc("Von chu so huu: 500.000.000", filename="a.pdf")
    doc2 = _doc("Von chu so huu: 900.000.000", filename="b.pdf")
    inputs, evidence = _only_period([doc1, doc2])
    assert inputs.equity_vnd is None  # never silently pick one
    ev = evidence["equity_vnd"]
    assert ev.status == "PENDING_REVIEW"
    assert len(ev.evidence) == 2
    assert {e.filename for e in ev.evidence} == {"a.pdf", "b.pdf"}


def test_same_value_confirmed_in_two_files_stays_computed():
    doc1 = _doc("Von chu so huu: 500.000.000", filename="a.pdf")
    doc2 = _doc("Von chu so huu: 500.000.000", filename="b.pdf")
    inputs, evidence = _only_period([doc1, doc2])
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


def test_financial_inputs_by_period_splits_two_years():
    from app.extraction.types import ExtractedTable

    table = ExtractedTable(
        rows=[
            ["Chi tieu", "31/12/2025", "31/12/2024"],
            ["Von chu so huu", "500.000.000", "400.000.000"],
        ],
        sheet_or_page="BCDKT",
    )
    doc = ExtractedDocument(filename="bctc.xlsx", doc_type="xlsx", text="", tables=[table], extraction_method="spreadsheet", confidence=1.0)
    canonical = build_canonical([doc])
    by_year = financial_inputs_by_period(canonical)
    assert by_year["2025"].inputs.equity_vnd == 500_000_000
    assert by_year["2024"].inputs.equity_vnd == 400_000_000


def test_financial_inputs_by_period_conflicting_field_is_pending_review():
    # Sheet names must clear classify_sheet's own bar (a bare "S1"/"S2" with
    # only one BCTC-field hit falls below the content threshold and gets
    # excluded from the scan entirely) — name them like real BCTC sheets.
    from app.extraction.types import ExtractedTable

    t1 = ExtractedTable(rows=[["Chi tieu", "31/12/2025"], ["Von chu so huu", "500.000.000"]], sheet_or_page="CDKT S1")
    t2 = ExtractedTable(rows=[["Chi tieu", "31/12/2025"], ["Von chu so huu", "600.000.000"]], sheet_or_page="CDKT S2")
    doc = ExtractedDocument(filename="bctc.xlsx", doc_type="xlsx", text="", tables=[t1, t2], extraction_method="spreadsheet", confidence=1.0)
    canonical = build_canonical([doc])
    by_year = financial_inputs_by_period(canonical)
    assert by_year["2025"].field_evidence["equity_vnd"].status == "PENDING_REVIEW"
    assert by_year["2025"].inputs.equity_vnd is None


def test_financial_inputs_by_period_populates_internal_non_h4_fields():
    # Ruling (Task 3): FIELD_CODE_MAP was missing revenue_bctc_vnd,
    # revenue_dsp_vnd, interest_due_vnd, ebit_vnd, finance_lease_debt_vnd,
    # total_principal_due_vnd — all real fields repayment_capacity.py,
    # profitability.py, stress_test.py, dsp_reconciliation.py and
    # capital_structure.py depend on. Pins that the canonical pipeline still
    # populates them, so this migration can't silently zero them out.
    from app.extraction.types import ExtractedTable

    table = ExtractedTable(
        rows=[["Chi tieu", "31/12/2025"], ["No thue tai chinh", "5.000.000"]],
        sheet_or_page="BCDKT",
    )
    doc = ExtractedDocument(filename="bctc.xlsx", doc_type="xlsx", text="", tables=[table], extraction_method="spreadsheet", confidence=1.0)
    canonical = build_canonical([doc])
    by_year = financial_inputs_by_period(canonical)
    assert by_year["2025"].inputs.finance_lease_debt_vnd == 5_000_000


def test_select_richest_period_prefers_populated_over_newest_sparse_year():
    # Production bug: a spurious/near-empty period bucket for a LATER year
    # (e.g. noise picked up from an unrelated bank-statement sheet bundled
    # in the same upload) must never win over a real, richly-populated
    # BCTC period just because its year number sorts higher.
    from app.agents.eb.financial_inputs import EbFinancialInputs, PeriodExtraction, select_richest_period

    period_extractions = {
        "2026": PeriodExtraction(year="2026", inputs=EbFinancialInputs(cash_vnd=1_000_000.0), field_evidence={}),
        "2025": PeriodExtraction(
            year="2025",
            inputs=EbFinancialInputs(equity_vnd=580_965_107_518.0, net_revenue_vnd=90_105_893_754.0, pat_vnd=1.0),
            field_evidence={},
        ),
    }
    assert select_richest_period(period_extractions) == "2025"


def test_select_richest_period_ties_broken_by_newest_year():
    from app.agents.eb.financial_inputs import EbFinancialInputs, PeriodExtraction, select_richest_period

    period_extractions = {
        "2024": PeriodExtraction(year="2024", inputs=EbFinancialInputs(equity_vnd=1.0), field_evidence={}),
        "2025": PeriodExtraction(year="2025", inputs=EbFinancialInputs(equity_vnd=1.0), field_evidence={}),
    }
    assert select_richest_period(period_extractions) == "2025"


def test_select_richest_period_empty_returns_none():
    from app.agents.eb.financial_inputs import select_richest_period

    assert select_richest_period({}) is None


def test_field_patterns_match_expected_labels():
    from app.agents.eb.canonical import _FIELD_PATTERNS, FIELD_CODE_MAP

    cases = {
        "IS_REVENUE": "doanh thu thuan: 100.000.000",
        "IS_PBT": "loi nhuan truoc thue: 50.000.000",
        "IS_PAT": "loi nhuan sau thue: 40.000.000",
        "IS_DEPRECIATION": "khau hao: 10.000.000",
        "BS_NON_CURRENT_ASSETS": "tai san dai han: 200.000.000",
        "BS_LT_BORROWINGS": "no dai han: 30.000.000",
        "_FINANCE_LEASE_DEBT": "no thue tai chinh: 5.000.000",
        "BS_AR_CUSTOMER": "phai thu khach hang: 20.000.000",
        "BS_INVENTORY": "hang ton kho: 15.000.000",
        "BS_AP_SUPPLIER": "phai tra nguoi ban: 12.000.000",
        "BS_CASH": "tien va tuong duong tien: 8.000.000",
        "_TOTAL_PRINCIPAL_DUE": "no goc den han: 25.000.000",
    }
    for code, text in cases.items():
        assert code in FIELD_CODE_MAP
        assert _FIELD_PATTERNS[code].search(text), f"{code} pattern did not match {text!r}"


def test_extracts_cogs_and_charter_capital():
    inputs, evidence = _only_period([_doc("Gia von hang ban: 50.000.000\nVon dieu le: 10.000.000.000\n")])
    assert inputs.cogs_vnd == 50_000_000
    assert inputs.charter_capital_vnd == 10_000_000_000
    assert evidence["cogs_vnd"].status == "COMPUTED"
    assert evidence["charter_capital_vnd"].status == "COMPUTED"
