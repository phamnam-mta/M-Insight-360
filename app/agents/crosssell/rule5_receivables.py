from app.engine.core.types import RuleResult

_DEAL_SIZE_RATES = {
    "in_hạn_default": 0.80,
    "lc_or_bltt": 0.90,
    "perfect_bct_lc": 0.98,
}


def deal_size_receivables_financing(receivables_131_current_vnd: float, method: str = "in_hạn_default") -> float:
    rate = _DEAL_SIZE_RATES.get(method, _DEAL_SIZE_RATES["in_hạn_default"])
    return round(receivables_131_current_vnd * rate)


def scf_limit_from_payables(payables_331_vnd: float) -> float:
    # 5B: SCF/bảo lãnh thanh toán limit dựa trên dư có 331 cuối kỳ — pass-through, decision is human's.
    return payables_331_vnd


def compute_dso_dpo(
    receivables_131_vnd: float, revenue_period_vnd: float,
    payables_331_vnd: float, cogs_period_vnd: float, period_days: int = 365,
) -> dict:
    dso_days = (receivables_131_vnd / revenue_period_vnd) * period_days if revenue_period_vnd else None
    dpo_days = (payables_331_vnd / cogs_period_vnd) * period_days if cogs_period_vnd else None
    return {"dso_days": dso_days, "dpo_days": dpo_days}


def leak_ratio_msb_share(operating_in_msb_vnd: float, total_receivable_credit_131_vnd: float) -> float | None:
    if not total_receivable_credit_131_vnd:
        return None
    return round(operating_in_msb_vnd / total_receivable_credit_131_vnd, 4)


LEAK_WARNING = (
    "Đây là chỉ số nghi vấn ở mức tổng thể, chưa phải kết luận. Chênh lệch có thể đến từ: "
    "dư công nợ đầu kỳ, bù trừ, hàng đổi hàng, thu tiền mặt, hoặc KH có TK khác tại MSB. "
    "Đề nghị RM xác minh với khách hàng trước khi sử dụng."
)


def evaluate_rule5(
    receivables_131_current_vnd: float | None,
    payables_331_vnd: float | None,
    leak_ratio: float | None = None,
) -> RuleResult:
    if receivables_131_current_vnd is None and payables_331_vnd is None:
        return RuleResult(
            rule_id="RULE5_RECEIVABLES", rule_name="Công nợ 131/331", status="CHƯA ĐÁNH GIÁ",
            comment="Không có bảng công nợ 131/331 — bỏ qua, ghi Notes. KHÔNG kết luận KH không có công nợ.",
            policy_version="DEMO_UAT",
        )

    evidence = []
    deal_size = None
    if receivables_131_current_vnd is not None:
        deal_size = deal_size_receivables_financing(receivables_131_current_vnd)
        evidence.append(f"Deal size tài trợ phải thu (80% mặc định) = {deal_size:,.0f} VND")
    if payables_331_vnd is not None:
        evidence.append(f"Hạn mức SCF/bảo lãnh tham chiếu dư có 331 = {payables_331_vnd:,.0f} VND")

    verification_question = None
    if leak_ratio is not None and leak_ratio < 0.5:
        evidence.append(f"Tỷ lệ về MSB = {leak_ratio} (< 50%, tín hiệu mạnh). {LEAK_WARNING}")
        verification_question = LEAK_WARNING

    return RuleResult(
        rule_id="RULE5_RECEIVABLES", rule_name="Công nợ 131/331", status="KÍCH HOẠT",
        evidence=evidence,
        comment="Xem 5A-5D trong spec để biết công thức chi tiết từng đề xuất.",
        observed_value=deal_size if deal_size is not None else payables_331_vnd,
        policy_version="DEMO_UAT",
        verification_question=verification_question,
        recommended_action="RM xác minh số liệu 131/331 rồi tiếp cận tài trợ phải thu / hạn mức SCF, bảo lãnh phù hợp.",
    )
