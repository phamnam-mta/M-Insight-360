from app.engine.core.types import RuleResult

from .financial_inputs import EbFinancialInputs

RF04_THRESHOLD = 0.05
RF04_POLICY_VERSION = "policy_mode=DEMO_UAT (ngưỡng demo, chưa xác nhận chuẩn MSB chính thức)"


def _evidence_refs(field_evidence: dict | None) -> dict:
    if not field_evidence:
        return {}
    return {
        k: field_evidence[k].evidence for k in ("revenue_bctc_vnd", "revenue_dsp_vnd")
        if k in field_evidence
    }


def evaluate_rf04_dsp_mismatch(inputs: EbFinancialInputs, field_evidence: dict | None = None) -> RuleResult:
    evidence_refs = _evidence_refs(field_evidence)
    # RF04 must NEVER silently default to KHÔNG KÍCH HOẠT ("đạt") when DSP data
    # is absent — spec §6 explicit warning. Missing evidence must read as
    # "not evaluated", not "no risk".
    if inputs.revenue_bctc_vnd is None or inputs.revenue_dsp_vnd is None:
        return RuleResult(
            rule_id="RF04", rule_name="Sai lệch dữ liệu Digisale/DSP so với BCTC", status="CHƯA ĐÁNH GIÁ",
            comment="Không có dữ liệu DSP tương ứng để đối chiếu — không được coi là 'đạt'.",
            verification_question="Khách hàng có dữ liệu doanh thu Digisale/DSP kỳ tương ứng để đối chiếu với BCTC không?",
            recommended_action="Yêu cầu bổ sung báo cáo doanh thu Digisale/DSP kỳ tương ứng trước khi đối chiếu.",
            evidence_refs=evidence_refs,
        )

    if inputs.revenue_bctc_vnd == 0:
        return RuleResult(
            rule_id="RF04", rule_name="Sai lệch dữ liệu Digisale/DSP so với BCTC", status="CHƯA ĐÁNH GIÁ",
            comment="Doanh thu BCTC bằng 0 — không thể tính tỷ lệ sai lệch.",
            verification_question="Vì sao doanh thu thuần trên BCTC bằng 0? Có sai sót trích xuất hay không?",
            recommended_action="Xác minh lại số liệu doanh thu thuần trên BCTC trước khi đối chiếu DSP.",
            evidence_refs=evidence_refs,
        )

    deviation = abs(inputs.revenue_bctc_vnd - inputs.revenue_dsp_vnd) / abs(inputs.revenue_bctc_vnd)
    deviation = round(deviation, 4)

    if deviation > RF04_THRESHOLD:
        return RuleResult(
            rule_id="RF04", rule_name="Sai lệch dữ liệu Digisale/DSP so với BCTC", status="KÍCH HOẠT",
            severity="HIGH", evidence=[f"Sai lệch = {deviation} (> {RF04_THRESHOLD})"],
            threshold=f"quy tắc demo: > {RF04_THRESHOLD * 100:.0f}%",
            formula="|BCTC - DSP| / |BCTC|",
            comment="Cần xác minh nguyên nhân: khác kỳ, khác phạm vi hợp nhất, hoặc sai nguồn nhập.",
            observed_value=deviation,
            policy_version=RF04_POLICY_VERSION,
            verification_question="Nguyên nhân sai lệch giữa doanh thu BCTC và DSP là gì (khác kỳ, khác phạm vi hợp nhất, sai nguồn nhập)?",
            recommended_action="Đối chiếu trực tiếp với khách hàng/nguồn DSP và yêu cầu giải trình văn bản trước khi thẩm định tiếp.",
            evidence_refs=evidence_refs,
        )
    return RuleResult(
        rule_id="RF04", rule_name="Sai lệch dữ liệu Digisale/DSP so với BCTC", status="KHÔNG KÍCH HOẠT",
        observed_value=deviation, policy_version=RF04_POLICY_VERSION,
        evidence_refs=evidence_refs,
    )
