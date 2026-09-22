from app.agents.eb.capital_structure import (
    compute_capital_balance_check, compute_liquidity_balance,
    compute_long_term_capital, compute_total_borrowings,
)
from app.agents.eb.financial_inputs import EbFinancialInputs
from app.agents.eb.liquidity import compute_nwc


def test_liquidity_balance_positive():
    inputs = EbFinancialInputs(current_assets_vnd=300_000_000, current_liabilities_vnd=100_000_000, net_revenue_vnd=1_000_000_000)
    metric = compute_liquidity_balance(inputs)
    assert metric.value == 0.2


def test_liquidity_balance_need_more_data_without_revenue():
    inputs = EbFinancialInputs(current_assets_vnd=300_000_000, current_liabilities_vnd=100_000_000)
    assert compute_liquidity_balance(inputs).status == "NEED_MORE_DATA"


def test_long_term_capital():
    inputs = EbFinancialInputs(equity_vnd=500_000_000, long_term_debt_vnd=200_000_000)
    metric = compute_long_term_capital(inputs)
    assert metric.value == 700_000_000


def test_total_borrowings_includes_finance_lease_when_present():
    inputs = EbFinancialInputs(short_term_debt_vnd=100_000_000, long_term_debt_vnd=200_000_000, finance_lease_debt_vnd=30_000_000)
    metric = compute_total_borrowings(inputs)
    assert metric.value == 330_000_000


def test_total_borrowings_without_finance_lease_defaults_to_zero_for_that_component():
    inputs = EbFinancialInputs(short_term_debt_vnd=100_000_000, long_term_debt_vnd=200_000_000)
    metric = compute_total_borrowings(inputs)
    assert metric.value == 300_000_000


def test_capital_balance_check_balanced():
    inputs = EbFinancialInputs(
        current_assets_vnd=300_000_000, current_liabilities_vnd=100_000_000,
        equity_vnd=500_000_000, long_term_debt_vnd=100_000_000, non_current_assets_vnd=400_000_000,
    )
    nwc = compute_nwc(inputs)
    long_term_capital = compute_long_term_capital(inputs)
    check = compute_capital_balance_check(inputs, nwc, long_term_capital)
    assert check["trai"] == 200_000_000
    assert check["phai"] == 200_000_000
    assert check["trang_thai"] == "Cân bằng"


def test_capital_balance_check_mismatched():
    inputs = EbFinancialInputs(
        current_assets_vnd=300_000_000, current_liabilities_vnd=100_000_000,
        equity_vnd=500_000_000, long_term_debt_vnd=100_000_000, non_current_assets_vnd=550_000_000,
    )
    nwc = compute_nwc(inputs)
    long_term_capital = compute_long_term_capital(inputs)
    check = compute_capital_balance_check(inputs, nwc, long_term_capital)
    assert check["trang_thai"] == "Cần rà soát phân loại nguồn vốn"


def test_capital_balance_check_need_more_data():
    check = compute_capital_balance_check(EbFinancialInputs(), compute_nwc(EbFinancialInputs()), compute_long_term_capital(EbFinancialInputs()))
    assert check["trang_thai"] == "Chưa xác định từ hồ sơ tải lên"
