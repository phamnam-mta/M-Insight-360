from dataclasses import asdict

from app.agents.rb.credit_engine import run_credit_engine
from app.agents.rb.loan_inputs import RbLoanInputs
from app.agents.rb.readiness import determine_readiness
from app.agents.rb.risk_flags import compute_risk_flags
from app.engine.core.types import RuleResult

from .mandatory_check import check_mandatory

# Same demo value the old one-shot RB flow used (app/agents/rb/loan_inputs.py
# default) — kept identical so eligible-income math doesn't silently drift
# between the two flows during the cutover.
_ELIGIBLE_INCOME_MARGIN = 0.08


def build_loan_inputs(case: dict) -> RbLoanInputs:
    income = case.get("income") or {}
    loan = case.get("loan") or {}
    collateral = case.get("collateral") or {}

    # avg_monthly_revenue_vnd is never populated here: the reused
    # credit_engine.py treats it as gross REVENUE and applies its own ~8%
    # eligibility margin to derive eligible income, but RB Portal only ever
    # collects the RM's entered monthly INCOME figure (income_salary_vnd /
    # income_business_vnd — the latter is also what gets written verbatim
    # into MB01A's own "Thu nhập từ kinh doanh" row). Feeding an income
    # figure through the revenue margin previously undercounted eligible
    # income by roughly 12x for business-income cases. gross_monthly_income_vnd
    # carries whatever raw income figure the RM entered, for both source
    # types, so dsr (which uses it directly, no margin) is computable
    # whenever an amount was entered.
    source_type = income.get("source_type")
    avg_monthly_revenue_vnd = None
    if source_type == "salary":
        gross_monthly_income_vnd = income.get("income_salary_vnd")
    elif source_type in ("business", "self_employed", "household_business"):
        gross_monthly_income_vnd = income.get("income_business_vnd")
    else:
        gross_monthly_income_vnd = None

    collateral_items = collateral.get("items") or []
    collateral_value_vnd = (
        sum(item.get("estimated_value_vnd") or 0 for item in collateral_items)
        if collateral_items else None
    )

    return RbLoanInputs(
        avg_monthly_revenue_vnd=avg_monthly_revenue_vnd,
        eligible_income_margin=_ELIGIBLE_INCOME_MARGIN,
        gross_monthly_income_vnd=gross_monthly_income_vnd,
        existing_monthly_obligation_vnd=loan.get("existing_monthly_obligation_vnd"),
        loan_amount_vnd=loan.get("amount_vnd"),
        tenor_months=loan.get("tenor_months"),
        annual_rate=loan.get("annual_rate"),
        collateral_value_vnd=collateral_value_vnd,
    )


# dti (the reused engine's own affordability metric) can never be computed
# for an RB Portal case — it requires avg_monthly_revenue_vnd, which this
# bridge never populates (see build_loan_inputs) — so compute_risk_flags's
# built-in HIGH_DTI check can never fire here. Without an equivalent check on
# dsr (the metric RB Portal cases actually compute), a case with an
# unaffordable debt burden, or one where affordability could not be computed
# at all, had zero risk flags and came out READY. Mirrors HIGH_DTI_THRESHOLD.
_HIGH_DSR_THRESHOLD = 0.5


def _affordability_flags(dsr_metric) -> list[RuleResult]:
    if dsr_metric.status == "NEED_MORE_DATA":
        return [
            RuleResult(
                rule_id="AFFORDABILITY_NOT_QUANTIFIED",
                rule_name="Chưa xác định được khả năng trả nợ",
                status="KÍCH HOẠT",
                severity="HIGH",
                comment="Chưa đủ dữ liệu thu nhập để tính DSR — không thể kết luận khả năng trả nợ.",
                recommended_action="Nhập số liệu thu nhập ở tab Nguồn thu trước khi kết luận thẩm định.",
            )
        ]
    if isinstance(dsr_metric.value, (int, float)) and dsr_metric.value > _HIGH_DSR_THRESHOLD:
        return [
            RuleResult(
                rule_id="HIGH_DSR",
                rule_name="Tỷ lệ trả nợ trên thu nhập cao",
                status="KÍCH HOẠT",
                severity="HIGH",
                evidence=[f"DSR = {dsr_metric.value} (ngưỡng demo {_HIGH_DSR_THRESHOLD})"],
                threshold=f"quy tắc demo: DSR > {_HIGH_DSR_THRESHOLD}",
                comment="DSR vượt ngưỡng demo — cần Credit Officer xem xét kỹ khả năng trả nợ.",
                recommended_action="Chuyển Credit Officer đánh giá thêm khả năng trả nợ trước khi ra quyết định.",
            )
        ]
    return []


def run_case_assessment(case: dict, documents: list[dict]) -> dict:
    mandatory = check_mandatory(
        case.get("customer"), case.get("legal"), case.get("income"), case.get("loan"), documents,
    )
    inputs = build_loan_inputs(case)
    engine_metrics = run_credit_engine(inputs, inputs.existing_monthly_obligation_vnd)

    # RB Portal has no document-classification-confidence signal of its own
    # (documents are RM-categorized on upload, not AI-classified) and no
    # separate tax-id-mismatch check yet — pass a clean placeholder RuleResult
    # so compute_risk_flags's required positional arg is satisfied without
    # fabricating a finding.
    tax_id_result = RuleResult(rule_id="TAX_ID_MISMATCH", rule_name="Đối chiếu mã số thuế", status="CHƯA ĐÁNH GIÁ")
    risk_flags = compute_risk_flags(mandatory, tax_id_result, engine_metrics["dti"])
    risk_flags.extend(_affordability_flags(engine_metrics["dsr"]))

    if mandatory["missing"]:
        credit_readiness, recommendation = "INSUFFICIENT_DATA", "ADDITIONAL_DATA_REQUIRED"
    else:
        readiness, _old_recommendation = determine_readiness(mandatory, risk_flags)
        # Map the existing RB readiness vocabulary onto the RB Portal's own
        # (spec §"Nguyên tắc nghiệp vụ" forbids APPROVE/REJECT, and the brief's
        # exact vocabulary differs from the older one-shot flow's).
        credit_readiness = {
            "READY": "PRELIMINARY_READY",
            "READY_WITH_CONDITIONS": "PRELIMINARY_READY_WITH_CONDITIONS",
            "MANUAL_REVIEW_REQUIRED": "MANUAL_REVIEW_REQUIRED",
        }[readiness]
        recommendation = {
            "PRELIMINARY_READY": "PROCEED_FOR_HUMAN_REVIEW",
            "PRELIMINARY_READY_WITH_CONDITIONS": "PROCEED_WITH_CONDITIONS",
            "MANUAL_REVIEW_REQUIRED": "REQUIRES_CREDIT_OFFICER_REVIEW",
        }[credit_readiness]

    return {
        "credit_engine": {name: asdict(metric) for name, metric in engine_metrics.items()},
        "risk_flags": [
            {**asdict(flag), "impact": flag.comment} for flag in risk_flags
        ],
        "mandatory_check": mandatory,
        "missing_data": mandatory["missing"],
        "credit_readiness": credit_readiness,
        "recommendation": recommendation,
    }
