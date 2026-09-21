from app.engine.core.types import RuleResult


def run_policy_check() -> list[RuleResult]:
    return [
        RuleResult(
            rule_id="POLICY_039",
            rule_name="Đối chiếu chính sách QĐ.EB.039 và các quy định nội bộ MSB",
            status="NEED_MORE_DATA",
            comment=(
                "CHƯA CÓ CĂN CỨ CHÍNH SÁCH — chưa có kho văn bản chính sách được nạp có kiểm soát "
                "phiên bản trong bản demo này. Chuyển người thẩm định kiểm tra thủ công; không "
                "khẳng định hồ sơ đạt chuẩn MSB."
            ),
            policy_version="policy_mode=DEMO_UAT (chưa nạp kho chính sách có version)",
            verification_question="Hồ sơ có được đối chiếu với văn bản chính sách tín dụng hiện hành của MSB không?",
            recommended_action="Chuyển RM/CBTĐ đối chiếu thủ công với chính sách nội bộ MSB trước khi kết luận đạt chuẩn.",
        )
    ]
