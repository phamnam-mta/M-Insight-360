from dataclasses import replace

from .financial_inputs import EbFinancialInputs
from .liquidity import compute_nwc
from .profitability import resolve_ebit_vnd
from .repayment_capacity import compute_dscr, compute_icr
from .stress_conclusions import generate_conclusions, generate_recommended_actions

DISCLAIMER = "Mô phỏng theo giả định — không thay thế thẩm định tín dụng và phê duyệt MSB."


def _metric_dict(metric) -> dict:
    from dataclasses import asdict
    return asdict(metric)


def run_stress_test(
    inputs: EbFinancialInputs,
    revenue_pct: float = 0.0,
    ebit_pct: float = 0.0,
    interest_pct: float = 0.0,
    receivable_days_add: float = 0.0,
    inventory_pct: float = 0.0,
    principal_due_pct: float = 0.0,
    comprehensive: bool = False,
) -> dict:
    ebit_before = resolve_ebit_vnd(inputs)
    dscr_before = compute_dscr(inputs, comprehensive=comprehensive)
    icr_before = compute_icr(inputs)

    stressed = replace(inputs)
    if stressed.net_revenue_vnd is not None:
        stressed.net_revenue_vnd = round(stressed.net_revenue_vnd * (1 + revenue_pct / 100), 2)
    if stressed.pat_vnd is not None:
        stressed.pat_vnd = round(stressed.pat_vnd * (1 + ebit_pct / 100), 2)
    if stressed.interest_expense_vnd is not None:
        stressed.interest_expense_vnd = round(stressed.interest_expense_vnd * (1 + interest_pct / 100), 2)
    if stressed.interest_due_vnd is not None:
        stressed.interest_due_vnd = round(stressed.interest_due_vnd * (1 + interest_pct / 100), 2)
    if comprehensive and stressed.total_principal_due_vnd is not None:
        stressed.total_principal_due_vnd = round(stressed.total_principal_due_vnd * (1 + principal_due_pct / 100), 2)
    elif stressed.principal_due_vnd is not None:
        stressed.principal_due_vnd = round(stressed.principal_due_vnd * (1 + principal_due_pct / 100), 2)

    # EBIT is operating profit, before interest — an interest-rate stress must
    # not move it. Scale ebit_before directly by ebit_pct, then back-solve
    # pbt_vnd against the (possibly already interest_pct-stressed)
    # interest_expense_vnd so resolve_ebit_vnd(stressed) lands exactly on
    # that target regardless of what interest_pct did to interest_expense_vnd.
    if ebit_before is not None and stressed.interest_expense_vnd is not None:
        ebit_after_target = ebit_before * (1 + ebit_pct / 100)
        stressed.pbt_vnd = round(ebit_after_target - stressed.interest_expense_vnd, 2)

    ebit_after = resolve_ebit_vnd(stressed)
    if ebit_after is not None and ebit_after <= 0:
        stressed.pbt_vnd = None  # forces ICR/DSCR's EBIT-dependent paths to NEED_MORE_DATA below

    dscr_after = compute_dscr(stressed, comprehensive=comprehensive)
    icr_after = compute_icr(stressed)

    nwc_impact_quantifiable = all(
        v is not None for v in (inputs.receivables_vnd, inputs.inventory_vnd, inputs.net_revenue_vnd)
    )
    nwc_before = compute_nwc(inputs)
    if nwc_impact_quantifiable:
        daily_revenue = inputs.net_revenue_vnd / 365
        receivable_delta = daily_revenue * receivable_days_add
        inventory_delta = inputs.inventory_vnd * (inventory_pct / 100)
        stressed_assets = (
            inputs.current_assets_vnd + receivable_delta + inventory_delta
            if inputs.current_assets_vnd is not None else None
        )
        nwc_after = compute_nwc(replace(inputs, current_assets_vnd=stressed_assets)) if stressed_assets is not None else nwc_before
    else:
        nwc_after = nwc_before

    debt_service_label = "Tổng nghĩa vụ nợ" if comprehensive else "Nghĩa vụ nợ dài hạn đến hạn"
    principal_before = inputs.total_principal_due_vnd if comprehensive else inputs.principal_due_vnd
    interest_before = inputs.interest_expense_vnd if comprehensive else inputs.interest_due_vnd
    principal_after = stressed.total_principal_due_vnd if comprehensive else stressed.principal_due_vnd
    interest_after = stressed.interest_expense_vnd if comprehensive else stressed.interest_due_vnd

    before = {
        "revenue": inputs.net_revenue_vnd, "ebit": ebit_before,
        "interest_expense": inputs.interest_expense_vnd,
        "nwc": nwc_before, "dscr": dscr_before, "icr": icr_before,
        "debt_service_label": debt_service_label,
        "principal_due": principal_before, "debt_service_total": (
            (principal_before or 0) + (interest_before or 0) if principal_before is not None and interest_before is not None else None
        ),
    }
    after = {
        "revenue": stressed.net_revenue_vnd, "ebit": ebit_after,
        "interest_expense": stressed.interest_expense_vnd,
        "nwc": nwc_after, "dscr": dscr_after, "icr": icr_after,
        "debt_service_label": debt_service_label,
        "principal_due": principal_after, "debt_service_total": (
            (principal_after or 0) + (interest_after or 0) if principal_after is not None and interest_after is not None else None
        ),
    }

    buffers = {}
    if dscr_after.status == "OK":
        buffers["dscr_buffer"] = round(dscr_after.value - 1.0, 4)
    if icr_after.status == "OK":
        buffers["icr_buffer"] = round(icr_after.value - 1.5, 4)

    conclusions = generate_conclusions({"dscr": dscr_before, "icr": icr_before}, {"dscr": dscr_after, "icr": icr_after}, comprehensive)
    recommended_actions = generate_recommended_actions({"dscr": dscr_before, "icr": icr_before}, {"dscr": dscr_after, "icr": icr_after})

    return {
        "assumptions": {
            "human_readable": (
                f"Doanh thu thay đổi {revenue_pct:g}%, EBIT thay đổi {ebit_pct:g}%, "
                f"chi phí lãi vay thay đổi {interest_pct:g}%."
            ),
            "deltas": {
                "revenue_pct": revenue_pct, "ebit_pct": ebit_pct, "interest_pct": interest_pct,
                "receivable_days_add": receivable_days_add, "inventory_pct": inventory_pct,
                "principal_due_pct": principal_due_pct,
            },
            "comprehensive_mode": comprehensive,
        },
        "before": {**before, "nwc": _metric_dict(before["nwc"]), "dscr": _metric_dict(before["dscr"]), "icr": _metric_dict(before["icr"])},
        "after": {**after, "nwc": _metric_dict(after["nwc"]), "dscr": _metric_dict(after["dscr"]), "icr": _metric_dict(after["icr"])},
        "nwc_impact_quantifiable": nwc_impact_quantifiable,
        "buffers": buffers,
        "conclusions": conclusions,
        "recommended_actions": recommended_actions,
        "disclaimer": DISCLAIMER,
    }
