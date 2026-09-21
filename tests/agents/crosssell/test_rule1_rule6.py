from app.agents.crosssell.statement_parser import Transaction
from app.agents.crosssell.rule1_rule6 import evaluate_rule1_payroll, evaluate_rule6_loan_elsewhere


def _txn(debit=0.0, description="") -> Transaction:
    return Transaction(
        date="01/01/2026", entry_no="1", debit=debit, credit=0.0, description=description,
        partner="", partner_account="", partner_bank="MB", currency="VND", source="",
    )


def test_rule1_activates_on_payroll_keyword():
    txns = [_txn(debit=20_000_000, description="Chi phi uy thac tra CT LUONG thang 01")]
    result = evaluate_rule1_payroll(txns)
    assert result.status == "KÍCH HOẠT"
    assert "20" in " ".join(result.evidence) or "20000000" in " ".join(result.evidence).replace(",", "")
    # RuleResult's spec-mandated fields (observed_value/policy_version/recommended_action)
    # must actually be populated, not left at their defaults.
    assert result.observed_value == 20_000_000.0
    assert result.policy_version == "DEMO_UAT"
    assert result.recommended_action


def test_rule1_not_evaluated_without_debit_data():
    result = evaluate_rule1_payroll([])
    assert result.status == "CHƯA ĐÁNH GIÁ"


def test_rule6_activates_on_loan_repayment_keywords():
    txns = [_txn(debit=5_000_000, description="Thu goc lai khe uoc LD2026001")]
    result = evaluate_rule6_loan_elsewhere(txns)
    assert result.status == "KÍCH HOẠT"
    assert "CIC" in result.comment.upper()
    assert result.observed_value == 5_000_000.0
    assert result.policy_version == "DEMO_UAT"
    # Spec §7 Rule 6: "Không suy ra dư nợ hiện tại (cần RM lấy CIC)" — this must be a
    # verification question the RM is prompted to answer, not just buried in the comment.
    assert result.verification_question and "CIC" in result.verification_question.upper()
    assert result.recommended_action


def test_rule6_not_evaluated_without_matches():
    result = evaluate_rule6_loan_elsewhere([_txn(debit=100, description="Thanh toan hoa don dien")])
    assert result.status == "CHƯA ĐÁNH GIÁ"
