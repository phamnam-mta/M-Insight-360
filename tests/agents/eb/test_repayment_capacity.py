from app.agents.eb.financial_inputs import EbFinancialInputs
from app.agents.eb.repayment_capacity import compute_dscr, compute_icr, evaluate_rf05_weak_repayment_capacity


def test_dscr_computed():
    inputs = EbFinancialInputs(cfads_vnd=1_500_000_000, principal_due_vnd=1_000_000_000, interest_due_vnd=200_000_000)
    metric = compute_dscr(inputs)
    assert round(metric.value, 4) == round(1_500_000_000 / 1_200_000_000, 4)


def test_dscr_missing_data_is_not_zero():
    metric = compute_dscr(EbFinancialInputs())
    assert metric.status == "NEED_MORE_DATA"
    assert metric.value is None


def test_icr_computed():
    inputs = EbFinancialInputs(ebit_vnd=800_000_000, interest_expense_vnd=200_000_000)
    metric = compute_icr(inputs)
    assert metric.value == 4.0


def test_icr_zero_interest_expense_is_need_more_data_not_infinity():
    inputs = EbFinancialInputs(ebit_vnd=800_000_000, interest_expense_vnd=0)
    metric = compute_icr(inputs)
    assert metric.status == "NEED_MORE_DATA"


def test_rf05_activates_when_dscr_below_1():
    dscr = compute_dscr(EbFinancialInputs(cfads_vnd=900_000_000, principal_due_vnd=1_000_000_000, interest_due_vnd=0))
    icr = compute_icr(EbFinancialInputs(ebit_vnd=800_000_000, interest_expense_vnd=200_000_000))
    result = evaluate_rf05_weak_repayment_capacity(dscr, icr)
    assert result.status == "KÍCH HOẠT"
    assert result.severity == "CRITICAL"


def test_rf05_not_evaluated_when_both_metrics_missing():
    dscr = compute_dscr(EbFinancialInputs())
    icr = compute_icr(EbFinancialInputs())
    result = evaluate_rf05_weak_repayment_capacity(dscr, icr)
    assert result.status == "CHƯA ĐÁNH GIÁ"


def test_rf05_not_activated_when_both_metrics_healthy():
    dscr = compute_dscr(EbFinancialInputs(cfads_vnd=1_500_000_000, principal_due_vnd=1_000_000_000, interest_due_vnd=0))
    icr = compute_icr(EbFinancialInputs(ebit_vnd=800_000_000, interest_expense_vnd=200_000_000))
    result = evaluate_rf05_weak_repayment_capacity(dscr, icr)
    assert result.status == "KHÔNG KÍCH HOẠT"


def test_rf05_activates_when_one_metric_missing_and_other_weak():
    # Spec: thiếu CFO/CFADS/gốc/lãi -> KHÔNG ĐỦ DỮ LIỆU for that metric, never 0 —
    # but if the OTHER metric (ICR) is present and weak, RF05 must still activate
    # rather than being swallowed by the missing DSCR.
    dscr = compute_dscr(EbFinancialInputs())
    icr = compute_icr(EbFinancialInputs(ebit_vnd=100_000_000, interest_expense_vnd=200_000_000))
    result = evaluate_rf05_weak_repayment_capacity(dscr, icr)
    assert result.status == "KÍCH HOẠT"
    assert result.severity == "CRITICAL"
