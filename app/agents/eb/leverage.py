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


RF06_THRESHOLD = 0.70
RF06_POLICY_VERSION = "policy_mode=DEMO_UAT (ngưỡng demo, chưa xác nhận chuẩn MSB chính thức)"


def evaluate_rf06_receivables_inventory_concentration(
    inputs: EbFinancialInputs, field_evidence: dict | None = None
) -> RuleResult:
    if inputs.receivables_vnd is None or inputs.inventory_vnd is None or not inputs.current_assets_vnd:
        return RuleResult(
            rule_id="RF06", rule_name="Phải thu/tồn kho chiếm tỷ trọng lớn", status="CHƯA ĐÁNH GIÁ",
            comment="Thiếu phải thu khách hàng, hàng tồn kho hoặc tài sản ngắn hạn để tính tỷ trọng.",
            verification_question="Hồ sơ có chi tiết phải thu khách hàng và hàng tồn kho không?",
            recommended_action="Bổ sung thuyết minh phải thu/tồn kho trước khi đánh giá cơ cấu tài sản ngắn hạn.",
            evidence_refs=_evidence_for(field_evidence, "receivables_vnd", "inventory_vnd", "current_assets_vnd"),
        )
    ratio = round((inputs.receivables_vnd + inputs.inventory_vnd) / inputs.current_assets_vnd, 4)
    if ratio > RF06_THRESHOLD:
        return RuleResult(
            rule_id="RF06", rule_name="Phải thu/tồn kho chiếm tỷ trọng lớn", status="KÍCH HOẠT", severity="MEDIUM",
            evidence=[f"Tỷ trọng = {ratio} (> {RF06_THRESHOLD})"],
            threshold=f"quy tắc demo: > {RF06_THRESHOLD * 100:.0f}% tài sản ngắn hạn",
            comment="Chất lượng tài sản ngắn hạn phụ thuộc lớn vào thu hồi công nợ/luân chuyển hàng tồn.",
            observed_value=ratio, policy_version=RF06_POLICY_VERSION,
            verification_question="Tuổi nợ phải thu và vòng quay hàng tồn kho thế nào?",
            recommended_action="Yêu cầu bảng tuổi nợ phải thu và đánh giá vòng quay hàng tồn kho.",
            evidence_refs=_evidence_for(field_evidence, "receivables_vnd", "inventory_vnd", "current_assets_vnd"),
        )
    return RuleResult(
        rule_id="RF06", rule_name="Phải thu/tồn kho chiếm tỷ trọng lớn", status="KHÔNG KÍCH HOẠT",
        observed_value=ratio, policy_version=RF06_POLICY_VERSION,
        evidence_refs=_evidence_for(field_evidence, "receivables_vnd", "inventory_vnd", "current_assets_vnd"),
    )


RF08_THRESHOLD = 2.0
RF08_POLICY_VERSION = "policy_mode=DEMO_UAT (ngưỡng demo, chưa xác nhận chuẩn MSB chính thức)"


def evaluate_rf08_leverage(
    total_borrowings: Metric, inputs: EbFinancialInputs, field_evidence: dict | None = None
) -> RuleResult:
    if total_borrowings.status == "NEED_MORE_DATA" or not inputs.equity_vnd or inputs.equity_vnd <= 0:
        return RuleResult(
            rule_id="RF08", rule_name="Tổng nợ vay / VCSH vượt ngưỡng", status="CHƯA ĐÁNH GIÁ",
            comment="Thiếu tổng nợ vay hoặc vốn chủ sở hữu (hoặc VCSH ≤ 0) để tính đòn bẩy.",
            verification_question="Hồ sơ có đủ số liệu nợ vay ngắn/dài hạn và vốn chủ sở hữu không?",
            recommended_action="Bổ sung Bảng cân đối kế toán chi tiết trước khi đánh giá đòn bẩy.",
            evidence_refs=_evidence_for(field_evidence, "equity_vnd"),
        )
    ratio = round(total_borrowings.value / inputs.equity_vnd, 4)
    if ratio > RF08_THRESHOLD:
        return RuleResult(
            rule_id="RF08", rule_name="Tổng nợ vay / VCSH vượt ngưỡng", status="KÍCH HOẠT", severity="HIGH",
            evidence=[f"Tổng nợ vay/VCSH = {ratio} (> {RF08_THRESHOLD})"],
            threshold=f"quy tắc demo: > {RF08_THRESHOLD:.1f}x",
            formula="tong_no_vay / von_chu_so_huu",
            comment="Đòn bẩy tài chính cao — cần đánh giá khả năng chịu đựng thêm nợ vay và nguồn trả nợ.",
            observed_value=ratio, policy_version=RF08_POLICY_VERSION,
            verification_question="Cơ cấu nợ vay hiện tại và kế hoạch tăng vốn chủ sở hữu (nếu có) là gì?",
            recommended_action="Yêu cầu phương án tăng vốn hoặc giảm đòn bẩy trước khi cấp thêm hạn mức.",
            evidence_refs=_evidence_for(field_evidence, "equity_vnd"),
        )
    return RuleResult(
        rule_id="RF08", rule_name="Tổng nợ vay / VCSH vượt ngưỡng", status="KHÔNG KÍCH HOẠT",
        observed_value=ratio, policy_version=RF08_POLICY_VERSION,
        evidence_refs=_evidence_for(field_evidence, "equity_vnd"),
    )
