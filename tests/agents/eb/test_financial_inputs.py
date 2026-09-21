from app.extraction.types import ExtractedDocument
from app.agents.eb.financial_inputs import extract_financial_inputs


def _doc(text: str) -> ExtractedDocument:
    return ExtractedDocument(
        filename="bctc.pdf", doc_type="pdf", text=text, tables=[],
        extraction_method="text_layer", confidence=1.0,
    )


def test_extracts_equity_and_current_assets_liabilities():
    text = (
        "Von chu so huu: 500,000,000\n"
        "Tai san ngan han: 2,000,000,000\n"
        "No ngan han: 2,500,000,000\n"
    )
    inputs = extract_financial_inputs([_doc(text)])
    assert inputs.equity_vnd == 500_000_000
    assert inputs.current_assets_vnd == 2_000_000_000
    assert inputs.current_liabilities_vnd == 2_500_000_000


def test_extracts_cfo():
    text = "Luu chuyen tien thuan tu hoat dong kinh doanh: -1,188,000,000"
    inputs = extract_financial_inputs([_doc(text)])
    assert inputs.cfo_vnd == -1_188_000_000


def test_extracts_short_term_debt_and_total_liabilities():
    text = "Vay ngan han: 39,000,000\nTong no phai tra: 3,000,000,000"
    inputs = extract_financial_inputs([_doc(text)])
    assert inputs.short_term_debt_vnd == 39_000_000
    assert inputs.total_liabilities_vnd == 3_000_000_000


def test_extracts_ebit_and_interest_expense():
    text = "Loi nhuan truoc thue va lai vay (EBIT): 800,000,000\nChi phi lai vay: 200,000,000"
    inputs = extract_financial_inputs([_doc(text)])
    assert inputs.ebit_vnd == 800_000_000
    assert inputs.interest_expense_vnd == 200_000_000


def test_missing_fields_are_none():
    inputs = extract_financial_inputs([_doc("Tai lieu khong co so lieu tai chinh")])
    assert inputs.equity_vnd is None
    assert inputs.cfo_vnd is None
