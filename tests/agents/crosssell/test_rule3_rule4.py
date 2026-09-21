from app.agents.crosssell.statement_parser import Transaction
from app.agents.crosssell.rule3_rule4 import evaluate_rule3_idle_balance, evaluate_rule4_fx


def test_rule3_never_evaluated_without_real_balance_data():
    # No real opening/closing balance column exists in our statement schema (spec §7's own
    # documented trap): a cumulative Credit-Debit running total must NEVER be used here.
    result = evaluate_rule3_idle_balance(None)
    assert result.status == "CHƯA ĐÁNH GIÁ"
    assert "số dư" in result.comment.lower()


def test_rule3_activates_with_real_balances_above_threshold_for_enough_days():
    balances = {f"day{i}": 6_000_000_000 for i in range(12)}
    result = evaluate_rule3_idle_balance(balances)
    assert result.status == "KÍCH HOẠT"


def test_rule3_uses_lowest_balance_in_period_as_deal_size():
    balances = {"d1": 6_000_000_000, "d2": 5_500_000_000, "d3": 7_000_000_000}
    balances.update({f"d{i}": 6_000_000_000 for i in range(4, 14)})
    result = evaluate_rule3_idle_balance(balances)
    assert "5,500,000,000" in result.evidence[0].replace(".", ",") or "5500000000" in result.evidence[0].replace(",", "")


def _fx_txn(currency: str) -> Transaction:
    return Transaction(
        date="01/01/2026", entry_no="1", debit=0.0, credit=1_000_000, description="",
        partner="X", partner_account="", partner_bank="MB", currency=currency, source="",
    )


def test_rule4_activates_on_foreign_currency_transaction():
    result = evaluate_rule4_fx([_fx_txn("USD")])
    assert result.status == "KÍCH HOẠT"


def test_rule4_absence_of_signal_is_never_activated():
    result = evaluate_rule4_fx([_fx_txn("VND")])
    assert result.status == "CHƯA ĐÁNH GIÁ"
