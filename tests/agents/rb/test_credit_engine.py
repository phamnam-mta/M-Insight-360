from app.agents.rb.loan_inputs import RbLoanInputs
from app.agents.rb.credit_engine import run_credit_engine


def test_case01_tiktok_shop_matches_ground_truth():
    # Numbers copied from CASE_01_TIKTOK_SHOP/EXPECTED/ground_truth.json — do not "fix" these,
    # they are the hackathon's own UAT expected values.
    inputs = RbLoanInputs(
        avg_monthly_revenue_vnd=2_919_000_000,
        eligible_income_margin=0.08,
        loan_amount_vnd=450_000_000,
        tenor_months=48,
        annual_rate=0.225,
    )
    metrics = run_credit_engine(inputs, existing_monthly_obligation_vnd=35_000_000)

    assert metrics["eligible_monthly_income"].value == 233_520_000
    assert metrics["new_loan_first_month_payment"].value == 17_812_500
    assert metrics["total_monthly_obligation"].value == 52_812_500
    assert round(metrics["dti"].value, 4) == 0.2262


def test_missing_revenue_yields_need_more_data_not_zero():
    inputs = RbLoanInputs(avg_monthly_revenue_vnd=None, loan_amount_vnd=450_000_000, tenor_months=48, annual_rate=0.225)
    metrics = run_credit_engine(inputs, existing_monthly_obligation_vnd=35_000_000)
    assert metrics["eligible_monthly_income"].status == "NEED_MORE_DATA"
    assert metrics["dti"].status == "NEED_MORE_DATA"
    assert metrics["dti"].value is None


def test_missing_loan_terms_yields_need_more_data():
    inputs = RbLoanInputs(avg_monthly_revenue_vnd=2_919_000_000, loan_amount_vnd=None, tenor_months=None, annual_rate=None)
    metrics = run_credit_engine(inputs, existing_monthly_obligation_vnd=35_000_000)
    assert metrics["new_loan_first_month_payment"].status == "NEED_MORE_DATA"


def test_remaining_disposable_income_computed_when_gross_income_known():
    inputs = RbLoanInputs(
        avg_monthly_revenue_vnd=2_919_000_000, eligible_income_margin=0.08,
        gross_monthly_income_vnd=2_919_000_000, loan_amount_vnd=450_000_000,
        tenor_months=48, annual_rate=0.225,
    )
    metrics = run_credit_engine(inputs, existing_monthly_obligation_vnd=35_000_000)
    assert metrics["remaining_disposable_income"].value == 2_919_000_000 - 52_812_500
    assert metrics["dsr"].value == round(52_812_500 / 2_919_000_000, 4)


def test_missing_existing_obligation_yields_need_more_data_not_zero():
    # Existing debt not stated anywhere in the docs must not be silently treated as 0.
    inputs = RbLoanInputs(
        avg_monthly_revenue_vnd=2_919_000_000, eligible_income_margin=0.08,
        loan_amount_vnd=450_000_000, tenor_months=48, annual_rate=0.225,
    )
    metrics = run_credit_engine(inputs, existing_monthly_obligation_vnd=None)
    assert metrics["total_monthly_obligation"].status == "NEED_MORE_DATA"
    assert metrics["dti"].status == "NEED_MORE_DATA"
    assert metrics["dti"].value is None
