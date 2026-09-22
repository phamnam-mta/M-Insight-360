from app.agents.crosssell.qd_eb_039 import QD_EB_039_RATES
from app.engine.core.types import Metric


def compute_output_contract_financing_ratio(
    proposed_limit_vnd: float | None,
    eligible_contract_value_vnd: float | None,
    method: str | None = None,
) -> Metric:
    if (
        proposed_limit_vnd is None
        or eligible_contract_value_vnd is None
        or eligible_contract_value_vnd <= 0
    ):
        return Metric.need_more_data(
            "output_contract_financing_ratio",
            "han_muc_de_xuat / gia_tri_hop_dong_du_dieu_kien * 100%",
        )

    value = round(proposed_limit_vnd / eligible_contract_value_vnd * 100, 2)
    policy_version = None
    if method in QD_EB_039_RATES:
        max_rate = QD_EB_039_RATES[method] * 100
        policy_version = (
            f"QĐ.EB.039 (tỷ lệ tối đa demo theo phương thức '{method}': {max_rate:.0f}%, "
            "chưa xác nhận phạm vi áp dụng chính thức)"
        )
    return Metric(
        metric="output_contract_financing_ratio", value=value,
        formula="han_muc_de_xuat / gia_tri_hop_dong_du_dieu_kien * 100%",
        input_values={
            "proposed_limit_vnd": proposed_limit_vnd,
            "eligible_contract_value_vnd": eligible_contract_value_vnd,
        },
        input_sources={
            "proposed_limit_vnd": "manual_rm_input",
            "eligible_contract_value_vnd": "manual_rm_input",
        },
        policy_version=policy_version,
    )


_VALID_LTV = (0.80, 0.85)


def compute_receivables_financing_limit(receivables_vnd: float | None, ltv: float) -> Metric:
    if ltv not in _VALID_LTV:
        raise ValueError(f"ltv phải là 0.80 hoặc 0.85, nhận {ltv}")
    if receivables_vnd is None:
        return Metric.need_more_data("receivables_financing_limit", "phai_thu_khach_hang * ltv")
    value = round(receivables_vnd * ltv, 2)
    policy_version = (
        "Điều kiện ưu tiên — cần xác minh bên mua thuộc VNR500/FDI và phê duyệt theo quy định"
        if ltv == 0.85 else None
    )
    return Metric(
        metric="receivables_financing_limit", value=value,
        formula="phai_thu_khach_hang * ltv",
        input_values={"receivables_vnd": receivables_vnd, "ltv": ltv},
        input_sources={"receivables_vnd": "bctc"},
        policy_version=policy_version,
    )
