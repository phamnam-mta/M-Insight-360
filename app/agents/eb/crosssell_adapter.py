from app.agents.crosssell.rule1_rule6 import evaluate_rule1_payroll, evaluate_rule6_loan_elsewhere
from app.agents.crosssell.rule2_partners import evaluate_rule2_top_partners
from app.agents.crosssell.rule3_rule4 import evaluate_rule4_fx
from app.agents.crosssell.statement_parser import parse_statement_documents
from app.engine.core.types import RuleResult
from app.extraction.types import ExtractedDocument

ACTIVATED_STATUS = "KÍCH HOẠT"


def adapt_to_opportunity_card(rule_result: RuleResult) -> dict:
    return {
        "product_suggestion": rule_result.rule_name,
        "basis_documents": rule_result.evidence,
        # Statement-derived signals are never contract/invoice-grounded, so
        # this adapter never asserts a dollar "deal size" — only a
        # qualitative opportunity (spec §E: "chưa có chứng từ thì chỉ nêu
        # cơ hội định tính, không hiện số tiền").
        "estimated_value": None,
        "formula_note": rule_result.comment,
        "unverified_conditions": rule_result.verification_question,
        "priority": rule_result.severity or "MEDIUM",
        "reviewer": "RM/Credit Officer",
        "recommended_action": rule_result.recommended_action,
        "status": rule_result.status,
    }


def evaluate_crosssell_opportunities(documents: list[ExtractedDocument]) -> list[dict]:
    transactions = []
    for doc in documents:
        transactions.extend(parse_statement_documents([doc]))
    if not transactions:
        return []
    results = [
        evaluate_rule1_payroll(transactions),
        evaluate_rule2_top_partners(transactions),
        evaluate_rule4_fx(transactions),
        evaluate_rule6_loan_elsewhere(transactions),
    ]
    activated = [r for r in results if r.status == ACTIVATED_STATUS]
    return [adapt_to_opportunity_card(r) for r in activated]
