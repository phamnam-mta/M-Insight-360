from app.engine.core.types import Metric

from .financial_inputs import EbFinancialInputs

_BALANCE_TOLERANCE_VND = 1


def _evidence_for(field_evidence: dict | None, *keys: str) -> dict:
    if not field_evidence:
        return {}
    return {k: field_evidence[k].evidence for k in keys if k in field_evidence}


def compute_liquidity_balance(inputs: EbFinancialInputs, field_evidence: dict | None = None) -> Metric:
    if inputs.current_assets_vnd is None or inputs.current_liabilities_vnd is None or not inputs.net_revenue_vnd:
        return Metric.need_more_data("liquidity_balance", "(tai_san_ngan_han - no_ngan_han) / doanh_thu_thuan")
    value = round((inputs.current_assets_vnd - inputs.current_liabilities_vnd) / inputs.net_revenue_vnd, 4)
    return Metric(
        metric="liquidity_balance", value=value,
        formula="(tai_san_ngan_han - no_ngan_han) / doanh_thu_thuan",
        input_values={
            "current_assets_vnd": inputs.current_assets_vnd,
            "current_liabilities_vnd": inputs.current_liabilities_vnd,
            "net_revenue_vnd": inputs.net_revenue_vnd,
        },
        input_sources={"current_assets_vnd": "bctc", "current_liabilities_vnd": "bctc", "net_revenue_vnd": "bctc"},
        evidence=_evidence_for(field_evidence, "current_assets_vnd", "current_liabilities_vnd", "net_revenue_vnd"),
    )


def compute_long_term_capital(inputs: EbFinancialInputs, field_evidence: dict | None = None) -> Metric:
    if inputs.equity_vnd is None or inputs.long_term_debt_vnd is None:
        return Metric.need_more_data("long_term_capital", "von_chu_so_huu + no_dai_han")
    value = inputs.equity_vnd + inputs.long_term_debt_vnd
    return Metric(
        metric="long_term_capital", value=value, formula="von_chu_so_huu + no_dai_han",
        input_values={"equity_vnd": inputs.equity_vnd, "long_term_debt_vnd": inputs.long_term_debt_vnd},
        input_sources={"equity_vnd": "bctc", "long_term_debt_vnd": "bctc"},
        evidence=_evidence_for(field_evidence, "equity_vnd", "long_term_debt_vnd"),
    )


def compute_total_borrowings(inputs: EbFinancialInputs, field_evidence: dict | None = None) -> Metric:
    if inputs.short_term_debt_vnd is None or inputs.long_term_debt_vnd is None:
        return Metric.need_more_data("total_borrowings", "vay_ngan_han + vay_dai_han + no_thue_tai_chinh")
    value = inputs.short_term_debt_vnd + inputs.long_term_debt_vnd + (inputs.finance_lease_debt_vnd or 0)
    return Metric(
        metric="total_borrowings", value=value,
        formula="vay_ngan_han + vay_dai_han + no_thue_tai_chinh",
        input_values={
            "short_term_debt_vnd": inputs.short_term_debt_vnd, "long_term_debt_vnd": inputs.long_term_debt_vnd,
            "finance_lease_debt_vnd": inputs.finance_lease_debt_vnd or 0,
        },
        input_sources={"short_term_debt_vnd": "bctc", "long_term_debt_vnd": "bctc"},
        evidence=_evidence_for(field_evidence, "short_term_debt_vnd", "long_term_debt_vnd", "finance_lease_debt_vnd"),
    )


def compute_capital_balance_check(inputs: EbFinancialInputs, nwc: Metric, long_term_capital: Metric) -> dict:
    if nwc.status == "NEED_MORE_DATA" or long_term_capital.status == "NEED_MORE_DATA" or inputs.non_current_assets_vnd is None:
        return {
            "trai": None, "phai": None, "trang_thai": "Chua xac dinh tu ho so tai len",
            "nhan_xet": "Thiếu tài sản ngắn/dài hạn, nợ ngắn/dài hạn hoặc vốn chủ sở hữu để đối chiếu cân đối tài chính.",
        }
    trai = nwc.value
    phai = long_term_capital.value - inputs.non_current_assets_vnd
    balanced = abs(trai - phai) <= _BALANCE_TOLERANCE_VND
    return {
        "trai": trai, "phai": phai,
        "trang_thai": "Can bang" if balanced else "Can ra soat phan loai nguon von",
        "nhan_xet": (
            "Tài sản dài hạn nên được tài trợ bằng nguồn vốn dài hạn; mất cân đối là tín hiệu rủi ro kỳ hạn."
        ),
    }
