from app.agents.eb.financial_inputs import EbFinancialInputs
from app.agents.eb.sanity_checks import run_sanity_checks


def test_flags_value_equal_to_report_year_as_suspect():
    inputs = EbFinancialInputs(net_revenue_vnd=2025.0)
    result = run_sanity_checks(inputs, year="2025")
    assert "net_revenue_vnd" in result.suspect_fields
    assert "2025" in result.suspect_fields["net_revenue_vnd"] or "năm" in result.suspect_fields["net_revenue_vnd"]


def test_does_not_flag_a_normal_large_value():
    # Multiple income-statement fields present (not just revenue) so this
    # case doesn't also trip check #3 (single-field-in-group) — isolates
    # checks #1/#2 against a realistic, non-suspicious revenue figure.
    inputs = EbFinancialInputs(
        net_revenue_vnd=128_061_897_765.0, pbt_vnd=12_160_680_287.0, pat_vnd=9_000_000_000.0,
    )
    result = run_sanity_checks(inputs, year="2025")
    assert "net_revenue_vnd" not in result.suspect_fields


def test_flags_undersized_big_field_when_company_is_billion_scale():
    # total assets confirmed billion-scale (10 tỷ), but revenue reads < 1
    # triệu — inconsistent, likely a truncated/mis-parsed cell.
    inputs = EbFinancialInputs(
        current_assets_vnd=6_000_000_000.0, non_current_assets_vnd=4_000_000_000.0,
        net_revenue_vnd=500_000.0,
    )
    result = run_sanity_checks(inputs, year="2025")
    assert "net_revenue_vnd" in result.suspect_fields


def test_flags_single_field_extracted_in_income_statement_group():
    inputs = EbFinancialInputs(net_revenue_vnd=1_000_000_000.0)
    result = run_sanity_checks(inputs, year="2025")
    assert "net_revenue_vnd" in result.suspect_fields
    assert "lệch cột" in result.suspect_fields["net_revenue_vnd"] or "duy nhất" in result.suspect_fields["net_revenue_vnd"]


def test_balance_mismatch_detected():
    # Realistic VND magnitudes — the balance tolerance (1,000 VND) is sized
    # for real BCTC figures, not toy unit values.
    inputs = EbFinancialInputs(
        current_assets_vnd=100_000_000_000.0, non_current_assets_vnd=50_000_000_000.0,
        equity_vnd=40_000_000_000.0, total_liabilities_vnd=50_000_000_000.0,
    )  # tong tai san 150bn != no phai tra 50bn + VCSH 40bn = 90bn
    result = run_sanity_checks(inputs, year="2025")
    assert result.balance_mismatch is True
    assert result.balance_mismatch_detail is not None


def test_balance_ok_when_within_tolerance():
    inputs = EbFinancialInputs(
        current_assets_vnd=100_000_000_000.0, non_current_assets_vnd=50_000_000_000.0,
        equity_vnd=100_000_000_000.0, total_liabilities_vnd=50_000_000_000.0,
    )
    result = run_sanity_checks(inputs, year="2025")
    assert result.balance_mismatch is False


def test_no_year_given_skips_year_collision_check_without_crashing():
    # Multiple IS fields present so this case doesn't also trip check #3
    # (single-field-in-group) — isolates check #1's year=None handling.
    inputs = EbFinancialInputs(net_revenue_vnd=2025.0, pbt_vnd=500_000_000.0)
    result = run_sanity_checks(inputs, year=None)
    assert "net_revenue_vnd" not in result.suspect_fields
