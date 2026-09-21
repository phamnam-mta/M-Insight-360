from app.agents.crosssell.statement_parser import Transaction
from app.agents.crosssell.rule2_partners import evaluate_rule2_top_partners, rank_top_partners


def _txn(partner, credit=0.0, debit=0.0) -> Transaction:
    return Transaction(
        date="01/01/2026", entry_no="1", debit=debit, credit=credit, description="Thanh toan",
        partner=partner, partner_account="", partner_bank="MB", currency="VND", source="",
    )


def test_partner_qualifies_above_threshold():
    txns = [_txn("CONG TY A", credit=200_000_000) for _ in range(3)]
    ranked = rank_top_partners(txns)
    assert ranked[0]["partner"] == "CONG TY A"
    assert ranked[0]["transaction_count"] == 3
    assert ranked[0]["total_value"] == 600_000_000
    assert ranked[0]["qualifies"] is True


def test_partner_below_frequency_threshold_does_not_qualify():
    txns = [_txn("CONG TY B", credit=600_000_000)]
    ranked = rank_top_partners(txns)
    assert ranked[0]["qualifies"] is False


def test_partner_below_value_threshold_does_not_qualify():
    # 5 * 90,000,000 = 450,000,000 VND, genuinely below the >=500,000,000 threshold
    # (spec: "≥500tr/đối tác" is inclusive, so a value exactly at the threshold qualifies).
    txns = [_txn("CONG TY C", credit=90_000_000) for _ in range(5)]
    ranked = rank_top_partners(txns)
    assert ranked[0]["qualifies"] is False


def test_ranking_is_stable_on_tie():
    txns = [_txn("CONG TY X", credit=500_000_000) for _ in range(3)] + [_txn("CONG TY Y", credit=500_000_000) for _ in range(3)]
    ranked1 = rank_top_partners(txns)
    ranked2 = rank_top_partners(txns)
    assert [r["partner"] for r in ranked1] == [r["partner"] for r in ranked2]


def test_rule2_activates_when_a_partner_qualifies():
    txns = [_txn("CONG TY A", credit=200_000_000) for _ in range(3)]
    result = evaluate_rule2_top_partners(txns)
    assert result.status == "KÍCH HOẠT"
    assert result.observed_value == 600_000_000
    assert result.policy_version == "DEMO_UAT"
    assert result.recommended_action


def test_rule2_not_activated_with_no_qualifying_partner():
    txns = [_txn("CONG TY A", credit=1_000_000)]
    result = evaluate_rule2_top_partners(txns)
    assert result.status == "KHÔNG KÍCH HOẠT"


def _txn_desc(partner, description, credit=0.0, debit=0.0) -> Transaction:
    return Transaction(
        date="01/01/2026", entry_no="1", debit=debit, credit=credit, description=description,
        partner=partner, partner_account="", partner_bank="MB", currency="VND", source="",
    )


def test_loan_repayment_transactions_are_excluded_from_partner_ranking():
    # Spec §7 Rule 6: "Loại các GD vay/trả nợ khỏi danh sách đối tác tiềm năng".
    # Without this the customer's own lender ranked as a top partner and Rule 2
    # recommended pitching SCF financing to the bank lending them money.
    lender = [
        _txn_desc("NGAN HANG XYZ", "Thu goc khe uoc LD2401", debit=400_000_000)
        for _ in range(4)
    ]
    supplier = [_txn_desc("CONG TY A", "Thanh toan hop dong", credit=200_000_000) for _ in range(3)]
    ranked = rank_top_partners(lender + supplier)
    assert [p["partner"] for p in ranked] == ["CONG TY A"]

    result = evaluate_rule2_top_partners(lender + supplier)
    assert "NGAN HANG XYZ" not in str(result.evidence) + (result.recommended_action or "")


def test_cash_transactions_are_excluded_from_partner_ranking():
    # Spec §8 dashboard: "top đối tác đã loại GD vay/tiền mặt".
    cash = [_txn_desc("NOP TIEN MAT", "Nop tien mat vao tai khoan", credit=900_000_000) for _ in range(3)]
    supplier = [_txn_desc("CONG TY A", "Thanh toan hop dong", credit=200_000_000) for _ in range(3)]
    ranked = rank_top_partners(cash + supplier)
    assert [p["partner"] for p in ranked] == ["CONG TY A"]


def test_ordinary_transactions_are_still_ranked():
    txns = [_txn_desc("CONG TY A", "Thanh toan hop dong mua ban", credit=200_000_000) for _ in range(3)]
    assert rank_top_partners(txns)[0]["qualifies"] is True
