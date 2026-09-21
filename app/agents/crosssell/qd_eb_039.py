QD_EB_039_RATES: dict[str, float] = {
    "perfect_bct_lc": 0.98,             # Sau giao hàng BCT hoàn hảo theo L/C
    "lc_or_bltt": 0.90,                 # Theo L/C hoặc BLTT đầu ra
    "export_bct": 0.90,                 # Sau giao hàng BCT xuất khẩu (D/A, D/P, T/T, CAD)
    "contract_or_award_notice": 0.80,   # Theo HĐDR / thông báo trúng thầu / dự kiến
    "domestic_receivable": 0.80,        # Sau giao hàng theo khoản phải thu trong nước
}


def compute_qd_eb_039_deal_size(method: str, contract_value_vnd: float) -> float:
    if method not in QD_EB_039_RATES:
        raise ValueError(f"Phương thức tài trợ không hợp lệ: {method}")
    return round(contract_value_vnd * QD_EB_039_RATES[method])
