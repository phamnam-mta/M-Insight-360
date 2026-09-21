from app.agents.crosssell.statement_parser import Transaction
from app.agents.crosssell.flow_classification import classify_flows


def _txn(credit=0.0, debit=0.0, description="", partner="CONG TY A") -> Transaction:
    return Transaction(
        date="01/01/2026", entry_no="1", debit=debit, credit=credit, description=description,
        partner=partner, partner_account="", partner_bank="MB", currency="VND", source="",
    )


def test_direct_inflow_with_named_partner():
    result = classify_flows([_txn(credit=1_000_000, partner="CONG TY A", description="Thanh toan hop dong")])
    assert result["direct_inflow"] == 1_000_000
    assert result["cash_inflow"] == 0
    assert result["operating_in"] == 1_000_000


def test_cash_deposit_excluded_from_operating_in():
    result = classify_flows([_txn(credit=500_000, description="Nop tien mat")])
    assert result["cash_inflow"] == 500_000
    assert result["operating_in"] == 0


def test_internal_transfer_excluded_from_operating_in():
    result = classify_flows([_txn(credit=2_000_000, description="Chuyen khoan noi bo giua cac tai khoan")])
    assert result["interbank_inflow"] == 2_000_000
    assert result["operating_in"] == 0


def test_operating_in_pct_computed_against_total_in():
    txns = [
        _txn(credit=600_000, partner="CONG TY A", description="Thanh toan"),
        _txn(credit=400_000, description="Nop tien mat"),
    ]
    result = classify_flows(txns)
    assert result["operating_in_pct"] == 0.6


def test_empty_transactions_do_not_crash():
    result = classify_flows([])
    assert result["operating_in"] == 0
    assert result["operating_in_pct"] == 0
