from app.engine.core.types import RuleResult

from .statement_parser import Transaction

RULE3_BALANCE_THRESHOLD_VND = 5_000_000_000
RULE3_MIN_DAYS = 10


def evaluate_rule3_idle_balance(daily_closing_balances: dict[str, float] | None) -> RuleResult:
    if not daily_closing_balances:
        return RuleResult(
            rule_id="RULE3_IDLE_BALANCE", rule_name="Nguồn vốn nhàn rỗi → CCTG/FD", status="CHƯA ĐÁNH GIÁ",
            comment=(
                "Không có cột số dư thực trong sao kê. TUYỆT ĐỐI không dùng số dư luỹ kế suy ra "
                "từ Thu − Chi bắt đầu từ 0 cho rule này — số liệu đó không phải số dư thật."
            ),
            policy_version="DEMO_UAT",
        )

    days_above = [day for day, bal in daily_closing_balances.items() if bal > RULE3_BALANCE_THRESHOLD_VND]
    if len(days_above) < RULE3_MIN_DAYS:
        return RuleResult(
            rule_id="RULE3_IDLE_BALANCE", rule_name="Nguồn vốn nhàn rỗi → CCTG/FD", status="KHÔNG KÍCH HOẠT",
            policy_version="DEMO_UAT",
        )

    deal_size = min(daily_closing_balances.values())
    return RuleResult(
        rule_id="RULE3_IDLE_BALANCE", rule_name="Nguồn vốn nhàn rỗi → CCTG/FD", status="KÍCH HOẠT",
        evidence=[f"Deal size (số dư thấp nhất kỳ) = {deal_size:,.0f} VND, {len(days_above)} ngày > ngưỡng"],
        threshold=f"quy tắc demo: > {RULE3_BALANCE_THRESHOLD_VND:,.0f} VND trong ≥ {RULE3_MIN_DAYS} ngày",
        comment="Đề xuất CCTG (nền cao ổn định) hoặc FD ngắn hạn 1-3 tháng (biến động). Tính riêng từng ngân hàng.",
        observed_value=deal_size,
        policy_version="DEMO_UAT",
        recommended_action="Đề xuất CCTG (nền cao ổn định) hoặc FD ngắn hạn 1-3 tháng (biến động), tính riêng từng ngân hàng.",
    )


def evaluate_rule4_fx(transactions: list[Transaction]) -> RuleResult:
    fx_transactions = [t for t in transactions if t.currency and t.currency.upper() not in ("VND", "VN")]
    if fx_transactions:
        total = sum(t.credit + t.debit for t in fx_transactions)
        return RuleResult(
            rule_id="RULE4_FX", rule_name="Ngoại hối (FX)", status="KÍCH HOẠT",
            evidence=[f"{len(fx_transactions)} giao dịch ngoại tệ, tổng quy đổi thô {total:,.0f}"],
            comment="Cơ hội hạn mức FX + Trade Finance. Cần xác minh cột Loại tiền thực tế.",
            observed_value=total,
            policy_version="DEMO_UAT",
            verification_question="RM cần xác minh cột Loại tiền trên sao kê là dữ liệu thực tế, không chỉ bắt từ từ khoá mô tả.",
            recommended_action="Chào hạn mức FX + Trade Finance sau khi xác minh cột Loại tiền thực tế.",
        )
    return RuleResult(
        rule_id="RULE4_FX", rule_name="Ngoại hối (FX)", status="CHƯA ĐÁNH GIÁ",
        comment="Không phát hiện giao dịch ngoại tệ — KHÔNG có nghĩa khách hàng không có nhu cầu FX.",
        policy_version="DEMO_UAT",
    )
