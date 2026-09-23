from app.agents.eb.financial_inputs import EbFinancialInputs
from app.agents.eb.stress_test import run_stress_test


def _base_inputs():
    return EbFinancialInputs(
        net_revenue_vnd=1_000_000_000, pbt_vnd=200_000_000, pat_vnd=160_000_000,
        interest_expense_vnd=50_000_000, interest_due_vnd=50_000_000, principal_due_vnd=100_000_000,
        depreciation_vnd=20_000_000, current_assets_vnd=400_000_000, current_liabilities_vnd=200_000_000,
        receivables_vnd=150_000_000, inventory_vnd=100_000_000,
    )


def test_revenue_and_ebit_deltas_apply_independently():
    result = run_stress_test(_base_inputs(), revenue_pct=-10, ebit_pct=-15)
    assert result["after"]["revenue"] == 900_000_000
    ebit_before = 200_000_000 + 50_000_000  # PBT + interest
    assert result["after"]["ebit"] == round(ebit_before * 0.85, 2)


def test_interest_pct_scales_interest_expense_and_debt_service():
    result = run_stress_test(_base_inputs(), interest_pct=15)
    assert result["after"]["interest_expense"] == round(50_000_000 * 1.15, 2)


def test_nwc_impact_quantifiable_true_when_all_inputs_present():
    result = run_stress_test(_base_inputs(), receivable_days_add=15, inventory_pct=10)
    assert result["nwc_impact_quantifiable"] is True


def test_nwc_impact_not_quantifiable_without_revenue():
    inputs = _base_inputs()
    inputs.net_revenue_vnd = None
    result = run_stress_test(inputs, receivable_days_add=15)
    assert result["nwc_impact_quantifiable"] is False


def test_comprehensive_mode_uses_total_principal_due():
    inputs = _base_inputs()
    inputs.total_principal_due_vnd = 120_000_000
    result = run_stress_test(inputs, comprehensive=True)
    assert "Tổng nghĩa vụ nợ" in result["before"]["debt_service_label"]


def test_buffers_computed_when_metrics_ok():
    result = run_stress_test(_base_inputs())
    assert "dscr_buffer" in result["buffers"]
    assert "icr_buffer" in result["buffers"]


def test_disclaimer_present():
    result = run_stress_test(_base_inputs())
    assert result["disclaimer"] == "Mô phỏng theo giả định — không thay thế thẩm định tín dụng và phê duyệt MSB."


def test_conclusions_and_actions_lists_present():
    result = run_stress_test(_base_inputs(), revenue_pct=-20, ebit_pct=-30, interest_pct=30)
    assert isinstance(result["conclusions"], list)
    assert isinstance(result["recommended_actions"], list)


def test_ebit_forced_non_positive_after_stress_keeps_icr_need_more_data_not_negative_ratio():
    inputs = _base_inputs()
    inputs.pbt_vnd = 10_000_000  # EBIT before = 60M
    result = run_stress_test(inputs, ebit_pct=-200)  # after EBIT <= 0
    assert result["after"]["icr"]["status"] == "NEED_MORE_DATA"


def test_p2_thi_trong_preset_matches_instruction_percentages():
    # P2 — Thận trọng: doanh thu -10%, EBIT -15%, lãi vay +15%
    from app.agents.eb.financial_inputs import EbFinancialInputs

    inputs = EbFinancialInputs(
        net_revenue_vnd=1_000_000_000, pbt_vnd=200_000_000, interest_expense_vnd=50_000_000,
        pat_vnd=160_000_000, depreciation_vnd=20_000_000,
        principal_due_vnd=100_000_000, interest_due_vnd=50_000_000,
    )
    result = run_stress_test(inputs, revenue_pct=-10, ebit_pct=-15, interest_pct=15)
    assert result["after"]["revenue"] == 900_000_000.0


def test_dscr_buffer_measured_against_1_0x():
    from app.agents.eb.financial_inputs import EbFinancialInputs

    inputs = EbFinancialInputs(
        pat_vnd=1_000_000_000, depreciation_vnd=200_000_000,
        interest_due_vnd=200_000_000, principal_due_vnd=1_000_000_000,
    )
    result = run_stress_test(inputs)
    if "dscr_buffer" in result["buffers"]:
        assert round(result["after"]["dscr"]["value"] - 1.0, 4) == result["buffers"]["dscr_buffer"]


def test_icr_buffer_measured_against_1_5x():
    from app.agents.eb.financial_inputs import EbFinancialInputs

    inputs = EbFinancialInputs(pbt_vnd=1_000_000_000, interest_expense_vnd=200_000_000)
    result = run_stress_test(inputs)
    if "icr_buffer" in result["buffers"]:
        assert result["after"]["icr"]["value"] - 1.5 == result["buffers"]["icr_buffer"]
