from app.agents.eb.financial_inputs import EbFinancialInputs
from app.agents.eb.profitability import compute_ebitda, resolve_ebit_vnd


def test_resolve_ebit_prefers_directly_extracted_value():
    inputs = EbFinancialInputs(ebit_vnd=999_000_000, pbt_vnd=100_000_000, interest_expense_vnd=50_000_000)
    assert resolve_ebit_vnd(inputs) == 999_000_000


def test_resolve_ebit_computed_from_pbt_plus_interest_when_not_extracted():
    inputs = EbFinancialInputs(pbt_vnd=100_000_000, interest_expense_vnd=50_000_000)
    assert resolve_ebit_vnd(inputs) == 150_000_000


def test_resolve_ebit_none_when_neither_available():
    assert resolve_ebit_vnd(EbFinancialInputs(pbt_vnd=100_000_000)) is None


def test_ebitda_computed():
    inputs = EbFinancialInputs(pbt_vnd=100_000_000, interest_expense_vnd=50_000_000, depreciation_vnd=20_000_000)
    metric = compute_ebitda(inputs)
    assert metric.value == 170_000_000
    assert metric.status == "OK"


def test_ebitda_need_more_data_when_depreciation_missing():
    inputs = EbFinancialInputs(pbt_vnd=100_000_000, interest_expense_vnd=50_000_000)
    metric = compute_ebitda(inputs)
    assert metric.status == "NEED_MORE_DATA"
