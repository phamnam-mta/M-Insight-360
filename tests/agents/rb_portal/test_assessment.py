from app.agents.rb_portal.assessment import build_loan_inputs, run_case_assessment


def test_build_loan_inputs_from_business_income_case():
    # income_business_vnd is what the RM enters as monthly INCOME (it is also
    # written verbatim into MB01A's "Thu nhập từ kinh doanh" row) — feeding it
    # into avg_monthly_revenue_vnd would be wrong: the reused credit_engine.py
    # treats that field as gross REVENUE and applies its own ~8% eligibility
    # margin on top, so an already-net income figure would be undercounted by
    # roughly 12x. RB Portal never collects true revenue, so
    # avg_monthly_revenue_vnd stays None for every case; gross_monthly_income_vnd
    # carries whatever raw income figure the RM entered, business or salary.
    case = {
        "income": {"source_type": "business", "income_business_vnd": 30_000_000},
        "loan": {"amount_vnd": 200_000_000, "tenor_months": 24, "annual_rate": 0.12,
                  "existing_monthly_obligation_vnd": 2_000_000},
        "collateral": {"items": [{"estimated_value_vnd": 500_000_000}]},
    }
    inputs = build_loan_inputs(case)
    assert inputs.avg_monthly_revenue_vnd is None
    assert inputs.gross_monthly_income_vnd == 30_000_000
    assert inputs.loan_amount_vnd == 200_000_000
    assert inputs.tenor_months == 24
    assert inputs.annual_rate == 0.12
    assert inputs.existing_monthly_obligation_vnd == 2_000_000
    assert inputs.collateral_value_vnd == 500_000_000


def test_build_loan_inputs_from_salary_income_case_uses_gross_income():
    case = {
        "income": {"source_type": "salary", "income_salary_vnd": 25_000_000},
        "loan": {"amount_vnd": 100_000_000, "tenor_months": 12, "annual_rate": 0.1},
        "collateral": None,
    }
    inputs = build_loan_inputs(case)
    assert inputs.gross_monthly_income_vnd == 25_000_000
    assert inputs.avg_monthly_revenue_vnd is None
    assert inputs.collateral_value_vnd is None


def test_build_loan_inputs_missing_sections_yields_all_none():
    inputs = build_loan_inputs({"income": None, "loan": None, "collateral": None})
    assert inputs.loan_amount_vnd is None
    assert inputs.avg_monthly_revenue_vnd is None


def test_run_case_assessment_insufficient_data_when_mandatory_missing():
    case = {"customer": None, "legal": None, "income": None, "loan": None, "collateral": None}
    computed = run_case_assessment(case, documents=[])
    assert computed["credit_readiness"] == "INSUFFICIENT_DATA"
    assert computed["missing_data"]
    assert "credit_engine" in computed
    assert "risk_flags" in computed


def test_run_case_assessment_computes_dti_when_data_complete():
    case = {
        "customer": {"full_name": "A"}, "legal": {"id_type": "CCCD"},
        "income": {"source_type": "salary", "income_salary_vnd": 25_000_000},
        "loan": {"product": "vay_von", "purpose": "tieu dung", "amount_vnd": 100_000_000,
                  "tenor_months": 12, "annual_rate": 0.1, "existing_monthly_obligation_vnd": 1_000_000},
        "collateral": None,
    }
    computed = run_case_assessment(case, documents=[])
    # The reused (unmodified) credit_engine.py computes eligible_monthly_income
    # — and therefore dti — from avg_monthly_revenue_vnd only, a
    # business-revenue concept; a salary-only case never populates that
    # field, so dti is always NEED_MORE_DATA here regardless of how
    # complete the salary data is. dsr, by contrast, uses gross_monthly_income_vnd
    # directly and IS computable for a salary case — assert on that instead.
    assert computed["credit_engine"]["dsr"]["status"] == "OK"
    assert computed["credit_readiness"] in (
        "PRELIMINARY_READY", "PRELIMINARY_READY_WITH_CONDITIONS", "MANUAL_REVIEW_REQUIRED",
    )


def test_high_dsr_salary_case_is_not_preliminary_ready():
    # dti is never computable for RB Portal cases (no avg_monthly_revenue_vnd
    # collected), so compute_risk_flags's own HIGH_DTI check can never fire —
    # without an equivalent DSR check, a salary case with an unaffordable
    # debt burden had zero risk flags and came out READY. Reproduced: salary
    # 10M/month, existing obligation 5M/month, new loan 1B over 12 months at
    # 10% -> DSR ~967%.
    case = {
        "customer": {"full_name": "A"}, "legal": {"id_type": "CCCD"},
        "income": {"source_type": "salary", "income_salary_vnd": 10_000_000},
        "loan": {"product": "vay_von", "purpose": "tieu dung", "amount_vnd": 1_000_000_000,
                  "tenor_months": 12, "annual_rate": 0.1, "existing_monthly_obligation_vnd": 5_000_000},
        "collateral": None,
    }
    computed = run_case_assessment(case, documents=[])
    assert computed["credit_engine"]["dsr"]["value"] > 1.0
    assert computed["credit_readiness"] != "PRELIMINARY_READY"
    assert any(f["rule_id"] == "HIGH_DSR" for f in computed["risk_flags"])


def test_case_with_unquantified_income_is_not_preliminary_ready():
    # source_type set (passes mandatory_check) but no income amount entered ->
    # dsr and dti both stay NEED_MORE_DATA -> zero risk flags under the old
    # logic -> incorrectly READY despite affordability being entirely unknown.
    case = {
        "customer": {"full_name": "A"}, "legal": {"id_type": "CCCD"},
        "income": {"source_type": "salary"},
        "loan": {"product": "vay_von", "purpose": "tieu dung", "amount_vnd": 100_000_000,
                  "tenor_months": 12, "annual_rate": 0.1, "existing_monthly_obligation_vnd": 1_000_000},
        "collateral": None,
    }
    computed = run_case_assessment(case, documents=[])
    assert computed["credit_engine"]["dsr"]["status"] == "NEED_MORE_DATA"
    assert computed["credit_readiness"] != "PRELIMINARY_READY"
