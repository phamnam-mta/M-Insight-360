from app.engine.core.types import Metric

from .loan_inputs import RbLoanInputs


def run_credit_engine(
    inputs: RbLoanInputs, existing_monthly_obligation_vnd: float | None
) -> dict[str, Metric]:
    metrics: dict[str, Metric] = {}

    # 1. Eligible monthly income = avg monthly revenue x eligibility margin.
    if inputs.avg_monthly_revenue_vnd is None:
        metrics["eligible_monthly_income"] = Metric.need_more_data(
            "eligible_monthly_income",
            "avg_monthly_revenue_vnd * eligible_income_margin",
            {"avg_monthly_revenue_vnd": inputs.avg_monthly_revenue_vnd},
        )
    else:
        value = round(inputs.avg_monthly_revenue_vnd * inputs.eligible_income_margin)
        metrics["eligible_monthly_income"] = Metric(
            metric="eligible_monthly_income",
            value=value,
            formula="avg_monthly_revenue_vnd * eligible_income_margin",
            input_values={
                "avg_monthly_revenue_vnd": inputs.avg_monthly_revenue_vnd,
                "eligible_income_margin": inputs.eligible_income_margin,
            },
            input_sources={"avg_monthly_revenue_vnd": "document_extraction"},
        )

    # 2. New loan first-month payment: equal principal + declining interest, first month.
    loan_terms_known = (
        inputs.loan_amount_vnd is not None
        and inputs.tenor_months is not None
        and inputs.annual_rate is not None
    )
    if not loan_terms_known:
        metrics["new_loan_first_month_payment"] = Metric.need_more_data(
            "new_loan_first_month_payment",
            "loan_amount/tenor_months + loan_amount*(annual_rate/12)",
            {
                "loan_amount_vnd": inputs.loan_amount_vnd,
                "tenor_months": inputs.tenor_months,
                "annual_rate": inputs.annual_rate,
            },
        )
    else:
        principal_per_month = inputs.loan_amount_vnd / inputs.tenor_months
        first_month_interest = inputs.loan_amount_vnd * (inputs.annual_rate / 12)
        value = round(principal_per_month + first_month_interest)
        metrics["new_loan_first_month_payment"] = Metric(
            metric="new_loan_first_month_payment",
            value=value,
            formula="loan_amount/tenor_months + loan_amount*(annual_rate/12)",
            input_values={
                "loan_amount_vnd": inputs.loan_amount_vnd,
                "tenor_months": inputs.tenor_months,
                "annual_rate": inputs.annual_rate,
            },
            input_sources={"loan_amount_vnd": "document_extraction"},
        )

    # 3. Total monthly obligation = existing + new loan payment.
    new_payment = metrics["new_loan_first_month_payment"]
    if existing_monthly_obligation_vnd is None or new_payment.status == "NEED_MORE_DATA":
        metrics["total_monthly_obligation"] = Metric.need_more_data(
            "total_monthly_obligation",
            "existing_monthly_obligation + new_loan_first_month_payment",
            {"existing_monthly_obligation_vnd": existing_monthly_obligation_vnd},
        )
    else:
        value = round(existing_monthly_obligation_vnd + new_payment.value)
        metrics["total_monthly_obligation"] = Metric(
            metric="total_monthly_obligation",
            value=value,
            formula="existing_monthly_obligation + new_loan_first_month_payment",
            input_values={
                "existing_monthly_obligation_vnd": existing_monthly_obligation_vnd,
                "new_loan_first_month_payment": new_payment.value,
            },
            input_sources={"existing_monthly_obligation_vnd": "loan_request_document"},
        )

    # 4. DTI = total_monthly_obligation / eligible_monthly_income.
    eligible_income = metrics["eligible_monthly_income"]
    total_obligation = metrics["total_monthly_obligation"]
    if eligible_income.status == "NEED_MORE_DATA" or total_obligation.status == "NEED_MORE_DATA":
        metrics["dti"] = Metric.need_more_data(
            "dti", "total_monthly_obligation / eligible_monthly_income"
        )
    else:
        value = round(total_obligation.value / eligible_income.value, 4)
        metrics["dti"] = Metric(
            metric="dti",
            value=value,
            formula="total_monthly_obligation / eligible_monthly_income",
            input_values={"total_monthly_obligation": total_obligation.value, "eligible_monthly_income": eligible_income.value},
            input_sources={"total_monthly_obligation": "credit_engine", "eligible_monthly_income": "credit_engine"},
        )

    # 5. DSR = total_monthly_obligation / gross_monthly_income (raw income, not eligibility-adjusted).
    if inputs.gross_monthly_income_vnd is None or total_obligation.status == "NEED_MORE_DATA":
        metrics["dsr"] = Metric.need_more_data(
            "dsr", "total_monthly_obligation / gross_monthly_income"
        )
    else:
        value = round(total_obligation.value / inputs.gross_monthly_income_vnd, 4)
        metrics["dsr"] = Metric(
            metric="dsr",
            value=value,
            formula="total_monthly_obligation / gross_monthly_income",
            input_values={"total_monthly_obligation": total_obligation.value, "gross_monthly_income_vnd": inputs.gross_monthly_income_vnd},
            input_sources={"gross_monthly_income_vnd": "document_extraction"},
        )

    # 6. Remaining disposable income = gross_monthly_income - total_monthly_obligation.
    if inputs.gross_monthly_income_vnd is None or total_obligation.status == "NEED_MORE_DATA":
        metrics["remaining_disposable_income"] = Metric.need_more_data(
            "remaining_disposable_income", "gross_monthly_income - total_monthly_obligation"
        )
    else:
        value = round(inputs.gross_monthly_income_vnd - total_obligation.value)
        metrics["remaining_disposable_income"] = Metric(
            metric="remaining_disposable_income",
            value=value,
            formula="gross_monthly_income - total_monthly_obligation",
            input_values={"gross_monthly_income_vnd": inputs.gross_monthly_income_vnd, "total_monthly_obligation": total_obligation.value},
            input_sources={"gross_monthly_income_vnd": "document_extraction"},
        )

    # 7. LTV — only meaningful for secured loans; omitted entirely (not NEED_MORE_DATA) when
    # no collateral value is present, since it is genuinely not applicable rather than missing.
    if inputs.collateral_value_vnd and loan_terms_known:
        value = round(inputs.loan_amount_vnd / inputs.collateral_value_vnd, 4)
        metrics["ltv"] = Metric(
            metric="ltv",
            value=value,
            formula="loan_amount / collateral_value",
            input_values={"loan_amount_vnd": inputs.loan_amount_vnd, "collateral_value_vnd": inputs.collateral_value_vnd},
            input_sources={"collateral_value_vnd": "collateral_document"},
        )

    return metrics
