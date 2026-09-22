from app.engine.core.types import Metric, RuleResult

from .financial_inputs import EbFinancialInputs

RF03_THRESHOLD = 0.5
RF03_POLICY_VERSION = "policy_mode=DEMO_UAT (ngưỡng demo, chưa xác nhận chuẩn MSB chính thức)"


def _evidence_for(field_evidence: dict | None, *keys: str) -> dict:
    if not field_evidence:
        return {}
    return {k: field_evidence[k].evidence for k in keys if k in field_evidence}


def compute_short_term_debt_ratio(inputs: EbFinancialInputs, field_evidence: dict | None = None) -> Metric:
    if (
        inputs.short_term_debt_vnd is None
        or inputs.total_liabilities_vnd is None
        or inputs.total_liabilities_vnd <= 0
    ):
        return Metric.need_more_data("short_term_debt_ratio", "vay_ngan_han / tong_no_phai_tra")
    value = round(inputs.short_term_debt_vnd / inputs.total_liabilities_vnd, 4)
    return Metric(
        metric="short_term_debt_ratio",
        value=value,
        formula="vay_ngan_han / tong_no_phai_tra",
        input_values={"short_term_debt_vnd": inputs.short_term_debt_vnd, "total_liabilities_vnd": inputs.total_liabilities_vnd},
        input_sources={"short_term_debt_vnd": "bctc", "total_liabilities_vnd": "bctc"},
        evidence=_evidence_for(field_evidence, "short_term_debt_vnd", "total_liabilities_vnd"),
    )


def evaluate_rf03_short_term_debt_ratio(ratio: Metric, field_evidence: dict | None = None) -> RuleResult:
    if ratio.status == "NEED_MORE_DATA":
        return RuleResult(
            rule_id="RF03", rule_name="Tỷ trọng nợ vay ngắn hạn cao", status="CHƯA ĐÁNH GIÁ",
            comment="Thiếu dư nợ vay ngắn hạn hoặc tổng nợ phải trả để tính tỷ trọng.",
            verification_question="Hồ sơ có thuyết minh chi tiết vay ngắn hạn và tổng nợ phải trả không?",
            recommended_action="Bổ sung thuyết minh nợ vay để tính tỷ trọng nợ vay ngắn hạn.",
            evidence_refs=ratio.evidence,
        )
    if ratio.value > RF03_THRESHOLD:
        return RuleResult(
            rule_id="RF03", rule_name="Tỷ trọng nợ vay ngắn hạn cao", status="KÍCH HOẠT", severity="MEDIUM",
            evidence=[f"Tỷ trọng = {ratio.value} (> {RF03_THRESHOLD})"],
            threshold=f"quy tắc demo: > {RF03_THRESHOLD * 100:.0f}%, chưa xác nhận là chuẩn MSB",
            formula=ratio.formula,
            comment="Đánh giá lịch đáo hạn, khả năng tái cấp vốn và áp lực dòng tiền.",
            observed_value=ratio.value,
            policy_version=RF03_POLICY_VERSION,
            verification_question="Cơ cấu đáo hạn nợ vay ngắn hạn thế nào? Khách hàng có kế hoạch tái cấp vốn/đảo nợ không?",
            recommended_action="Yêu cầu lịch đáo hạn chi tiết và đánh giá khả năng tái cấp vốn trước khi phê duyệt.",
            evidence_refs=ratio.evidence,
        )
    return RuleResult(
        rule_id="RF03", rule_name="Tỷ trọng nợ vay ngắn hạn cao", status="KHÔNG KÍCH HOẠT",
        observed_value=ratio.value, policy_version=RF03_POLICY_VERSION,
        evidence_refs=ratio.evidence,
    )
