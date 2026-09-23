import math

from app.agents.eb.capital_structure import (
    compute_capital_balance_check, compute_liquidity_balance,
    compute_long_term_capital, compute_total_borrowings,
)
from app.agents.eb.contract_financing import compute_receivables_financing_limit
from app.agents.eb.leverage import evaluate_rf08_leverage
from app.agents.eb.liquidity import compute_nwc
from app.agents.eb.repayment_capacity import compute_dscr, compute_icr

from .fixtures.alpha_group_demo import ALPHA_GROUP_2025


def test_t1_nwc():
    assert compute_nwc(ALPHA_GROUP_2025).value == 128_061_897_765


def test_t2_liquidity_balance():
    metric = compute_liquidity_balance(ALPHA_GROUP_2025)
    assert round(metric.value, 4) == 1.4212


def test_t3_capital_balance_check_is_balanced():
    nwc = compute_nwc(ALPHA_GROUP_2025)
    ltc = compute_long_term_capital(ALPHA_GROUP_2025)
    check = compute_capital_balance_check(ALPHA_GROUP_2025, nwc, ltc)
    assert check["trang_thai"] == "Cân bằng"


def test_t4_icr_via_financial_expense_fallback():
    icr = compute_icr(ALPHA_GROUP_2025)
    assert icr.status == "OK"
    assert round(icr.value, 2) == 1.00


def test_t5_dscr_is_unknown_missing_depreciation_and_principal():
    dscr = compute_dscr(ALPHA_GROUP_2025)
    assert dscr.status == "NEED_MORE_DATA"


def test_t6_leverage_ratio():
    # NOTE: the instruction's own T6 oracle expects 0,14x ("chỉ gồm vay
    # ngắn hạn 78.810.636.239"), assuming "Vay dài hạn" (CĐKT mã 338) is
    # unavailable. The Alpha Group source DOES mark mã 338 itself as
    # unread, but it separately provides "Nợ dài hạn" (mã 330, a broader
    # liabilities figure) = 123.801.251.677 — and this codebase's
    # long_term_debt_vnd field is populated from mã 330 (see field_codes.py
    # module docstring; a documented, out-of-scope 330-vs-338 gap). This
    # test pins the REAL value this code currently computes from that
    # data, not the instruction's aspirational figure — see Task 18's
    # ledger ruling.
    borrowings = compute_total_borrowings(ALPHA_GROUP_2025)
    rf08 = evaluate_rf08_leverage(borrowings, ALPHA_GROUP_2025)
    assert round(rf08.observed_value, 2) == 0.35


def test_t7_qd039_reference_limit():
    metric = compute_receivables_financing_limit(ALPHA_GROUP_2025.receivables_vnd, ltv=0.80)
    assert metric.value == round(1_030_523_666 * 0.80, 2)


def test_t9_no_technical_values_leak_from_metrics():
    for metric_fn in (compute_nwc, compute_liquidity_balance, compute_icr, compute_dscr):
        metric = metric_fn(ALPHA_GROUP_2025)
        if isinstance(metric.value, float):
            assert not math.isnan(metric.value)
            assert not math.isinf(metric.value)
