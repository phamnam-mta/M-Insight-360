from app.agents.crosssell.statement_parser import Transaction
from app.agents.crosssell.precheck import check_name_quality, run_precheck


def _txn(debit=0.0, credit=0.0, partner="CONG TY A") -> Transaction:
    return Transaction(
        date="01/01/2026", entry_no="1", debit=debit, credit=credit, description="",
        partner=partner, partner_account="", partner_bank="MB", currency="VND", source="",
    )


def test_precheck_pass_when_balances_reconcile():
    txns = [_txn(credit=1000), _txn(debit=400)]
    result = run_precheck(txns, opening_balance=0, closing_balance=600)
    assert result["verdict"] == "PASS"


def test_precheck_block_when_balances_do_not_reconcile():
    txns = [_txn(credit=1000), _txn(debit=400)]
    result = run_precheck(txns, opening_balance=0, closing_balance=999999)
    assert result["verdict"] == "BLOCK"
    forbidden = ["lỗi", "sai sót", "rm gửi thiếu", "rm gửi sai", "vi phạm"]
    reason_lower = result["reason"].lower()
    assert not any(word in reason_lower for word in forbidden)


def test_precheck_warn_when_no_balance_columns():
    txns = [_txn(credit=1000), _txn(debit=400)]
    result = run_precheck(txns, opening_balance=None, closing_balance=None)
    assert result["verdict"] == "WARN"


def test_name_quality_pass_on_clean_data():
    txns = [_txn(partner="CONG TY CO PHAN ALPHA")] * 10
    result = check_name_quality(txns)
    assert result["verdict"] == "PASS"


def test_name_quality_warn_on_high_empty_ratio():
    txns = [_txn(partner="")] * 3 + [_txn(partner="CONG TY CO PHAN ALPHA")] * 7
    result = check_name_quality(txns)
    assert result["verdict"] == "WARN"
    assert result["empty_pct"] == 0.3


def test_block_message_says_outflow_rows_when_debits_are_missing():
    # opening 0 + credit 1000 - debit 400 = 600 computed vs 100 reported:
    # the statement is missing 500 of *outflow* (ghi nợ) rows.
    txns = [_txn(credit=1000), _txn(debit=400)]
    result = run_precheck(txns, opening_balance=0, closing_balance=100)
    assert result["verdict"] == "BLOCK"
    assert result["est_missing_debit"] == 500
    assert "chi ra" in result["reason"]
    assert "thu vào" not in result["reason"]


def test_block_message_says_inflow_rows_when_credits_are_missing():
    # opening 0 + credit 1000 - debit 400 = 600 computed vs 1100 reported: the
    # statement is missing 500 of *inflow* (ghi có) rows, but the message always
    # asked the customer for the missing outflow rows — the wrong document.
    txns = [_txn(credit=1000), _txn(debit=400)]
    result = run_precheck(txns, opening_balance=0, closing_balance=1100)
    assert result["verdict"] == "BLOCK"
    assert result["est_missing_debit"] == 0
    assert result["est_missing_credit"] == 500
    assert "thu vào" in result["reason"]
    assert "chi ra" not in result["reason"]
