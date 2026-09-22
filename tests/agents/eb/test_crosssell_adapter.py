from app.agents.eb.crosssell_adapter import adapt_to_opportunity_card, evaluate_crosssell_opportunities
from app.engine.core.types import RuleResult
from app.extraction.types import ExtractedDocument, ExtractedTable

HEADER = ["Ngay", "So but toan", "Ghi No", "Ghi Co", "Dien giai", "Doi tac", "TK doi tac", "NH doi tac", "Loai tien", "Nguon"]


def _statement_doc(rows, filename="sao_ke.xlsx"):
    doc = ExtractedDocument(
        filename=filename, doc_type="xlsx", text="", tables=[
            ExtractedTable(rows=rows, sheet_or_page="Sheet1")
        ], extraction_method="spreadsheet", confidence=1.0,
    )
    doc.file_id = filename
    return doc


def test_adapt_never_asserts_a_dollar_estimate():
    rr = RuleResult(
        rule_id="RULE2_SCF", rule_name="Tài trợ chuỗi / Thanh toán (EB)", status="KÍCH HOẠT",
        evidence=["Cong ty A: 5 GD, 1,000,000,000 VND"], observed_value=1_000_000_000,
        recommended_action="Tiếp cận đối tác hàng đầu.",
    )
    card = adapt_to_opportunity_card(rr)
    assert card["estimated_value"] is None
    assert card["product_suggestion"] == "Tài trợ chuỗi / Thanh toán (EB)"
    assert card["basis_documents"] == rr.evidence
    assert card["recommended_action"] == "Tiếp cận đối tác hàng đầu."


def test_no_statement_yields_empty_opportunity_list():
    doc = ExtractedDocument(
        filename="bctc.pdf", doc_type="pdf", text="khong lien quan", tables=[],
        extraction_method="text_layer", confidence=1.0,
    )
    assert evaluate_crosssell_opportunities([doc]) == []


def test_activated_rule_becomes_a_card():
    rows = [
        HEADER,
        ["01/01/2026", "1", "0", "600000000", "thanh toan hang", "Cong ty A", "", "", "VND", ""],
        ["02/01/2026", "2", "0", "600000000", "thanh toan hang", "Cong ty A", "", "", "VND", ""],
        ["03/01/2026", "3", "0", "600000000", "thanh toan hang", "Cong ty A", "", "", "VND", ""],
    ]
    cards = evaluate_crosssell_opportunities([_statement_doc(rows)])
    assert any(c["product_suggestion"] == "Tài trợ chuỗi / Thanh toán (EB)" for c in cards)
