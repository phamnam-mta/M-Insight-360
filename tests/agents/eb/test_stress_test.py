from app.agents.eb.financial_inputs import EbFinancialInputs
from app.agents.eb.stress_test import run_stress_test


def test_stress_test_returns_before_and_after():
    inputs = EbFinancialInputs(
        current_assets_vnd=2_000_000_000, current_liabilities_vnd=1_500_000_000,
        ebit_vnd=800_000_000, interest_expense_vnd=200_000_000,
    )
    result = run_stress_test(inputs, margin_pct=-50)
    assert result["before"]["icr"]["value"] == 4.0
    assert result["after"]["icr"]["value"] == 2.0
    assert "kịch bản giả định" in result["assumptions"]["note"].lower()


def test_stress_test_never_touches_nwc_with_revenue_delta():
    inputs = EbFinancialInputs(current_assets_vnd=2_000_000_000, current_liabilities_vnd=1_500_000_000)
    result = run_stress_test(inputs, revenue_pct=20)
    assert result["before"]["nwc"]["value"] == result["after"]["nwc"]["value"]


def test_stress_test_handles_missing_inputs_gracefully():
    result = run_stress_test(EbFinancialInputs(), interest_rate_pct=10)
    assert result["after"]["dscr"]["status"] == "NEED_MORE_DATA"
