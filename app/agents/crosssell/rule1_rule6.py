import re
import unicodedata

from app.engine.core.types import RuleResult

from .statement_parser import Transaction

_PAYROLL_KEYWORDS = ["luong", "salary", "payroll", "ct luong"]
_LOAN_KEYWORDS = ["khe uoc", "giai ngan", "thu goc", "thu lai", "tra no vay"]
_LOAN_CODE_RE = re.compile(r"\bld\d+\b", re.IGNORECASE)


def _strip_accents_lower(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(c for c in normalized if not unicodedata.combining(c))
    return ascii_text.lower()


def is_loan_transaction(txn: Transaction) -> bool:
    """Rule 6's loan/repayment keyword test, shared with Rule 2's exclusions."""
    description = _strip_accents_lower(txn.description)
    return any(kw in description for kw in _LOAN_KEYWORDS) or bool(
        _LOAN_CODE_RE.search(txn.description)
    )


def evaluate_rule1_payroll(transactions: list[Transaction]) -> RuleResult:
    matches = [
        t for t in transactions
        if t.debit > 0 and any(kw in _strip_accents_lower(t.description) for kw in _PAYROLL_KEYWORDS)
    ]
    if not matches:
        return RuleResult(
            rule_id="RULE1_PAYROLL", rule_name="Tín hiệu trả lương", status="CHƯA ĐÁNH GIÁ",
            comment="Chưa có giao dịch ghi nợ nào khớp từ khoá lương — không kết luận 'không có lương'.",
            policy_version="DEMO_UAT",
        )
    total = sum(t.debit for t in matches)
    return RuleResult(
        rule_id="RULE1_PAYROLL", rule_name="Tín hiệu trả lương", status="KÍCH HOẠT",
        evidence=[f"{len(matches)} giao dịch, tổng {total:,.0f} VND"],
        comment="Cơ hội: Tài khoản trả lương Payroll + Thẻ tín dụng CBNV.",
        observed_value=total,
        policy_version="DEMO_UAT",
        recommended_action="Giới thiệu gói Tài khoản trả lương Payroll + Thẻ tín dụng CBNV.",
    )


def evaluate_rule6_loan_elsewhere(transactions: list[Transaction]) -> RuleResult:
    matches = [t for t in transactions if is_loan_transaction(t)]
    if not matches:
        return RuleResult(
            rule_id="RULE6_LOAN_ELSEWHERE", rule_name="Tín hiệu vay vốn ở ngân hàng khác", status="CHƯA ĐÁNH GIÁ",
            policy_version="DEMO_UAT",
        )
    total_debit = sum(t.debit for t in matches)
    return RuleResult(
        rule_id="RULE6_LOAN_ELSEWHERE", rule_name="Tín hiệu vay vốn ở ngân hàng khác", status="KÍCH HOẠT",
        evidence=[f"{len(matches)} giao dịch khớp từ khoá khế ước/giải ngân/thu gốc-lãi/trả nợ vay, tổng {total_debit:,.0f} VND"],
        comment="Đề xuất chia sẻ hạn mức/tái tài trợ tại MSB. Không suy ra dư nợ hiện tại — cần RM lấy CIC.",
        observed_value=total_debit,
        policy_version="DEMO_UAT",
        verification_question="RM cần lấy báo cáo CIC để xác minh dư nợ hiện tại của khách hàng trước khi đề xuất.",
        recommended_action="Đề xuất chia sẻ hạn mức/tái tài trợ tại MSB sau khi có kết quả CIC.",
    )
