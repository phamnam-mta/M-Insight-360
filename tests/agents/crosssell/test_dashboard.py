from app.agents.crosssell.statement_parser import Transaction
from app.agents.crosssell.dashboard import build_monthly_dashboard


def _txn(date, credit=0.0, debit=0.0) -> Transaction:
    return Transaction(
        date=date, entry_no="1", debit=debit, credit=credit, description="",
        partner="X", partner_account="", partner_bank="MB", currency="VND", source="",
    )


def test_groups_by_month_ddmmyyyy():
    txns = [_txn("05/06/2025", credit=1000), _txn("20/06/2025", debit=400), _txn("01/07/2025", credit=200)]
    rows = build_monthly_dashboard(txns)
    assert rows[0]["month"] == "06/2025"
    assert rows[0]["transaction_count"] == 2
    assert rows[0]["total_in"] == 1000
    assert rows[0]["total_out"] == 400
    assert rows[0]["net"] == 600
    assert rows[1]["month"] == "07/2025"


def test_unparseable_date_grouped_as_unknown():
    rows = build_monthly_dashboard([_txn("not-a-date", credit=100)])
    assert rows[0]["month"] == "KHÔNG XÁC ĐỊNH"


def test_empty_input_returns_empty_list():
    assert build_monthly_dashboard([]) == []
