from app.agents.eb.internal_systems import check_internal_system


def test_always_returns_pending_internal_check():
    assert check_internal_system("CIF") == "PENDING_INTERNAL_CHECK"
    assert check_internal_system("CIC") == "PENDING_INTERNAL_CHECK"
