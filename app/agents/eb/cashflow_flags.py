from app.engine.core.types import RuleResult

from .financial_inputs import EbFinancialInputs

RF02_POLICY_VERSION = "policy_mode=DEMO_UAT (ngưỡng demo, chưa xác nhận chuẩn MSB chính thức)"


def evaluate_rf02_negative_cfo(inputs: EbFinancialInputs) -> RuleResult:
    if inputs.cfo_vnd is None:
        return RuleResult(
            rule_id="RF02", rule_name="Dòng tiền hoạt động kinh doanh âm", status="CHƯA ĐÁNH GIÁ",
            comment="Không tìm thấy chỉ tiêu lưu chuyển tiền thuần từ HĐKD trong hồ sơ.",
            verification_question="Hồ sơ có Báo cáo lưu chuyển tiền tệ kỳ gần nhất không?",
            recommended_action="Bổ sung Báo cáo lưu chuyển tiền tệ trước khi kết luận về dòng tiền HĐKD.",
        )
    if inputs.cfo_vnd < 0:
        return RuleResult(
            rule_id="RF02", rule_name="Dòng tiền hoạt động kinh doanh âm", status="KÍCH HOẠT",
            severity="HIGH", evidence=[f"CFO = {inputs.cfo_vnd} (< 0)"],
            threshold="quy tắc demo: CFO < 0 trong kỳ đánh giá",
            formula="luu_chuyen_tien_thuan_tu_hoat_dong_kinh_doanh",
            comment=(
                "CFO âm trong kỳ đánh giá — cần xác minh nguồn trả nợ, không kết luận mất khả năng "
                "trả nợ chỉ từ một kỳ CFO âm."
            ),
            observed_value=inputs.cfo_vnd,
            policy_version=RF02_POLICY_VERSION,
            verification_question="Nguyên nhân CFO âm là gì (mở rộng hàng tồn kho, phải thu tăng, thời vụ...)? Nguồn trả nợ thay thế là gì?",
            recommended_action="Yêu cầu giải trình nguyên nhân CFO âm và bằng chứng nguồn trả nợ thay thế (CFI/CFF, hạn mức dự phòng).",
        )
    return RuleResult(
        rule_id="RF02", rule_name="Dòng tiền hoạt động kinh doanh âm", status="KHÔNG KÍCH HOẠT",
        observed_value=inputs.cfo_vnd, policy_version=RF02_POLICY_VERSION,
    )
