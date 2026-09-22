from dataclasses import asdict, replace

from .financial_inputs import EbFinancialInputs
from .liquidity import compute_nwc
from .repayment_capacity import compute_dscr, compute_icr


def run_stress_test(
    inputs: EbFinancialInputs,
    revenue_pct: float = 0.0,
    margin_pct: float = 0.0,
    interest_rate_pct: float = 0.0,
    collection_speed_pct: float = 0.0,
) -> dict:
    before = {"nwc": compute_nwc(inputs), "dscr": compute_dscr(inputs), "icr": compute_icr(inputs)}

    stressed = replace(inputs)
    if stressed.ebit_vnd is not None:
        stressed.ebit_vnd = round(stressed.ebit_vnd * (1 + revenue_pct / 100) * (1 + margin_pct / 100), 2)
    if stressed.interest_expense_vnd is not None:
        stressed.interest_expense_vnd = round(stressed.interest_expense_vnd * (1 + interest_rate_pct / 100), 2)
    if stressed.interest_due_vnd is not None:
        stressed.interest_due_vnd = round(stressed.interest_due_vnd * (1 + interest_rate_pct / 100), 2)
    if stressed.cfads_vnd is not None:
        stressed.cfads_vnd = round(stressed.cfads_vnd * (1 + collection_speed_pct / 100), 2)
    # NWC is a balance-sheet snapshot (current assets/liabilities), not driven
    # by revenue/margin/rate/collection-speed deltas — deliberately untouched.

    after = {"nwc": compute_nwc(stressed), "dscr": compute_dscr(stressed), "icr": compute_icr(stressed)}

    return {
        "assumptions": {
            "revenue_pct": revenue_pct, "margin_pct": margin_pct,
            "interest_rate_pct": interest_rate_pct, "collection_speed_pct": collection_speed_pct,
            "note": "Đây là kịch bản giả định do cán bộ nhập, không phải dự báo tài chính chắc chắn.",
        },
        "before": {k: asdict(v) for k, v in before.items()},
        "after": {k: asdict(v) for k, v in after.items()},
    }
