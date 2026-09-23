from app.engine.core.types import Metric, RuleResult

from .financial_inputs import EbFinancialInputs
from .profitability import resolve_ebit_vnd

DSCR_THRESHOLD = 1.0
ICR_THRESHOLD = 1.5
RF05_POLICY_VERSION = "policy_mode=DEMO_UAT (ngưỡng demo, chưa xác nhận chuẩn MSB chính thức)"


def _evidence_for(field_evidence: dict | None, *keys: str) -> dict:
    if not field_evidence:
        return {}
    return {k: field_evidence[k].evidence for k in keys if k in field_evidence}


def compute_dscr(
    inputs: EbFinancialInputs, field_evidence: dict | None = None, comprehensive: bool = False
) -> Metric:
    if comprehensive:
        numerator_fields = ("pat_vnd", "depreciation_vnd", "interest_expense_vnd")
        principal_field, interest_field = "total_principal_due_vnd", "interest_expense_vnd"
        principal = inputs.total_principal_due_vnd
        interest = inputs.interest_expense_vnd
        formula = "(LNST + khau_hao + tong_chi_phi_lai_vay) / (tong_no_goc_den_han + tong_chi_phi_lai_vay)"
    else:
        numerator_fields = ("pat_vnd", "depreciation_vnd", "interest_due_vnd")
        principal_field, interest_field = "principal_due_vnd", "interest_due_vnd"
        principal = inputs.principal_due_vnd
        interest = inputs.interest_due_vnd
        formula = "(LNST + khau_hao + lai_vay_dai_han) / (no_goc_dai_han_den_han + lai_vay_dai_han)"

    if inputs.pat_vnd is None or inputs.depreciation_vnd is None or interest is None or principal is None:
        return Metric.need_more_data("dscr", formula)
    debt_service = principal + interest
    if debt_service <= 0:
        return Metric.need_more_data("dscr", formula)

    numerator = inputs.pat_vnd + inputs.depreciation_vnd + interest
    value = round(numerator / debt_service, 4)
    return Metric(
        metric="dscr", value=value, formula=formula,
        # Keys here must be real EbFinancialInputs field names (not generic
        # labels) — the Stress Test drawer re-posts this dict verbatim as
        # stress-test inputs, and the router silently drops any key that
        # isn't a real dataclass field.
        input_values={
            "pat_vnd": inputs.pat_vnd, "depreciation_vnd": inputs.depreciation_vnd,
            interest_field: interest, principal_field: principal,
        },
        input_sources={"pat_vnd": "bctc", "depreciation_vnd": "bctc", interest_field: "bctc", principal_field: "bctc"},
        evidence=_evidence_for(field_evidence, *numerator_fields, "principal_due_vnd", "total_principal_due_vnd"),
    )


def compute_icr(inputs: EbFinancialInputs, field_evidence: dict | None = None) -> Metric:
    ebit = resolve_ebit_vnd(inputs)
    if ebit is None or not inputs.interest_expense_vnd:
        return Metric.need_more_data("icr", "EBIT / chi_phi_lai_vay")
    value = round(ebit / inputs.interest_expense_vnd, 4)
    return Metric(
        metric="icr", value=value, formula="EBIT / chi_phi_lai_vay",
        input_values={"ebit_vnd": ebit, "interest_expense_vnd": inputs.interest_expense_vnd},
        input_sources={"ebit_vnd": "bctc", "interest_expense_vnd": "bctc"},
        evidence=_evidence_for(field_evidence, "ebit_vnd", "pbt_vnd", "interest_expense_vnd"),
    )


RF09_POLICY_VERSION = RF05_POLICY_VERSION


def evaluate_rf05_dscr_weak(dscr: Metric, field_evidence: dict | None = None) -> RuleResult:
    if dscr.status == "NEED_MORE_DATA":
        return RuleResult(
            rule_id="RF05", rule_name="Khả năng trả nợ yếu (DSCR)", status="CHƯA ĐÁNH GIÁ",
            comment="Thiếu CFADS, gốc/lãi đến hạn — không gán 0, không kết luận 'không có cảnh báo'.",
            verification_question="Hồ sơ có lịch trả nợ (gốc/lãi đến hạn) và số liệu CFADS để tính DSCR không?",
            recommended_action="Bổ sung lịch trả nợ và báo cáo tài chính chi tiết trước khi đánh giá khả năng trả nợ.",
            evidence_refs=dscr.evidence,
        )
    if dscr.value < DSCR_THRESHOLD:
        return RuleResult(
            rule_id="RF05", rule_name="Khả năng trả nợ yếu (DSCR)", status="KÍCH HOẠT", severity="CRITICAL",
            evidence=[f"DSCR = {dscr.value} (< {DSCR_THRESHOLD})"],
            threshold=f"quy tắc demo: DSCR {DSCR_THRESHOLD} lần",
            comment="Chưa xác nhận là chuẩn MSB chính thức — cần người thẩm định xác nhận trước khi dùng chính thức.",
            observed_value=dscr.value, policy_version=RF05_POLICY_VERSION,
            verification_question="Nguồn trả nợ/CFADS có ổn định không? Khách hàng có phương án bổ sung tài sản đảm bảo hoặc nguồn thu thay thế không?",
            recommended_action="Yêu cầu phương án tăng cường nguồn trả nợ hoặc tài sản đảm bảo bổ sung; chuyển Credit Officer thẩm định kỹ.",
            evidence_refs=dscr.evidence,
        )
    return RuleResult(
        rule_id="RF05", rule_name="Khả năng trả nợ yếu (DSCR)", status="KHÔNG KÍCH HOẠT",
        observed_value=dscr.value, policy_version=RF05_POLICY_VERSION, evidence_refs=dscr.evidence,
    )


def evaluate_rf09_icr_weak(icr: Metric, field_evidence: dict | None = None) -> RuleResult:
    if icr.status == "NEED_MORE_DATA":
        return RuleResult(
            rule_id="RF09", rule_name="Khả năng trả nợ yếu (ICR)", status="CHƯA ĐÁNH GIÁ",
            comment="Thiếu EBIT hoặc chi phí lãi vay — không gán 0, không kết luận 'không có cảnh báo'.",
            verification_question="Hồ sơ có LNTT và chi phí lãi vay đầy đủ để tính ICR không?",
            recommended_action="Bổ sung báo cáo kết quả kinh doanh chi tiết trước khi đánh giá khả năng trả nợ.",
            evidence_refs=icr.evidence,
        )
    if icr.value < ICR_THRESHOLD:
        return RuleResult(
            rule_id="RF09", rule_name="Khả năng trả nợ yếu (ICR)", status="KÍCH HOẠT", severity="CRITICAL",
            evidence=[f"ICR = {icr.value} (< {ICR_THRESHOLD})"],
            threshold=f"quy tắc demo: ICR {ICR_THRESHOLD} lần",
            comment="Chưa xác nhận là chuẩn MSB chính thức — cần người thẩm định xác nhận trước khi dùng chính thức.",
            observed_value=icr.value, policy_version=RF09_POLICY_VERSION,
            verification_question="Nguồn trả nợ/CFADS có ổn định không? Khách hàng có phương án bổ sung tài sản đảm bảo hoặc nguồn thu thay thế không?",
            recommended_action="Yêu cầu phương án tăng cường nguồn trả nợ hoặc tài sản đảm bảo bổ sung; chuyển Credit Officer thẩm định kỹ.",
            evidence_refs=icr.evidence,
        )
    return RuleResult(
        rule_id="RF09", rule_name="Khả năng trả nợ yếu (ICR)", status="KHÔNG KÍCH HOẠT",
        observed_value=icr.value, policy_version=RF09_POLICY_VERSION, evidence_refs=icr.evidence,
    )


RF07_THRESHOLD = 0.30
RF07_POLICY_VERSION = "policy_mode=DEMO_UAT (ngưỡng demo, chưa xác nhận chuẩn MSB chính thức)"


def evaluate_rf07_high_interest_burden(inputs: EbFinancialInputs, field_evidence: dict | None = None) -> RuleResult:
    ebit = resolve_ebit_vnd(inputs)
    if ebit is None or not inputs.interest_expense_vnd or ebit <= 0:
        return RuleResult(
            rule_id="RF07", rule_name="Chi phí lãi vay lớn bất thường so với EBIT", status="CHƯA ĐÁNH GIÁ",
            comment="Thiếu EBIT hoặc chi phí lãi vay để đánh giá.",
            verification_question="Hồ sơ có LNTT, chi phí lãi vay đầy đủ để tính EBIT không?",
            recommended_action="Bổ sung báo cáo kết quả kinh doanh chi tiết.",
        )
    ratio = round(inputs.interest_expense_vnd / ebit, 4)
    if ratio > RF07_THRESHOLD:
        return RuleResult(
            rule_id="RF07", rule_name="Chi phí lãi vay lớn bất thường so với EBIT", status="KÍCH HOẠT", severity="MEDIUM",
            evidence=[f"Chi phí lãi vay / EBIT = {ratio} (> {RF07_THRESHOLD})"],
            threshold=f"quy tắc demo: > {RF07_THRESHOLD * 100:.0f}% EBIT",
            comment="Cảnh báo sớm trước khi ICR chạm ngưỡng 1.5x — cấu trúc chi phí lãi vay đã cao.",
            observed_value=ratio, policy_version=RF07_POLICY_VERSION,
            verification_question="Cơ cấu kỳ hạn nợ và khả năng đàm phán lãi suất hiện tại thế nào?",
            recommended_action="Xem xét cơ cấu kỳ hạn nợ hoặc bổ sung nguồn trả nợ.",
        )
    return RuleResult(
        rule_id="RF07", rule_name="Chi phí lãi vay lớn bất thường so với EBIT", status="KHÔNG KÍCH HOẠT",
        observed_value=ratio, policy_version=RF07_POLICY_VERSION,
    )
