from app.agents.eb.overview.credit_history import evaluate_credit_history


def test_credit_history_always_pending_internal_check():
    row = evaluate_credit_history()
    assert row.result == "PENDING_INTERNAL_CHECK"
    assert row.observed.value is None
    assert "CIC" in row.reason_if_incomplete
