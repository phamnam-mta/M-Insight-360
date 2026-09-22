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
        principal = inputs.total_principal_due_vnd
        interest = inputs.interest_expense_vnd
        formula = "(LNST + khau_hao + tong_chi_phi_lai_vay) / (tong_no_goc_den_han + tong_chi_phi_lai_vay)"
    else:
        numerator_fields = ("pat_vnd", "depreciation_vnd", "interest_due_vnd")
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
        input_values={"pat_vnd": inputs.pat_vnd, "depreciation_vnd": inputs.depreciation_vnd, "interest": interest, "principal": principal},
        input_sources={"pat_vnd": "bctc", "depreciation_vnd": "bctc"},
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


def _insufficient_data(dscr: Metric, icr: Metric) -> RuleResult:
    missing = [
        name
        for name, metric in (("DSCR", dscr), ("ICR", icr))
        if metric.status == "NEED_MORE_DATA"
    ]
    return RuleResult(
        rule_id="RF05", rule_name="Khả năng trả nợ yếu", status="CHƯA ĐÁNH GIÁ",
        evidence=[f"{name} = KHÔNG ĐỦ DỮ LIỆU" for name in missing],
        comment="Thiếu CFO/CFADS, gốc/lãi đến hạn, hoặc EBIT/chi phí lãi vay — không gán 0, "
                "không kết luận 'không có cảnh báo'.",
        observed_value="KHÔNG ĐỦ DỮ LIỆU",
        verification_question="Hồ sơ có lịch trả nợ (gốc/lãi đến hạn) và số liệu CFADS/EBIT để tính DSCR, ICR không?",
        recommended_action="Bổ sung lịch trả nợ và báo cáo tài chính chi tiết trước khi đánh giá khả năng trả nợ.",
        evidence_refs={**dscr.evidence, **icr.evidence},
    )


def evaluate_rf05_weak_repayment_capacity(
    dscr: Metric, icr: Metric, field_evidence: dict | None = None
) -> RuleResult:
    if dscr.status == "NEED_MORE_DATA" and icr.status == "NEED_MORE_DATA":
        return _insufficient_data(dscr, icr)

    dscr_weak = dscr.status == "OK" and dscr.value < DSCR_THRESHOLD
    icr_weak = icr.status == "OK" and icr.value < ICR_THRESHOLD

    if dscr_weak or icr_weak:
        evidence = []
        if dscr_weak:
            evidence.append(f"DSCR = {dscr.value} (< {DSCR_THRESHOLD})")
        elif dscr.status == "NEED_MORE_DATA":
            evidence.append("DSCR = KHÔNG ĐỦ DỮ LIỆU")
        if icr_weak:
            evidence.append(f"ICR = {icr.value} (< {ICR_THRESHOLD})")
        elif icr.status == "NEED_MORE_DATA":
            evidence.append("ICR = KHÔNG ĐỦ DỮ LIỆU")
        return RuleResult(
            rule_id="RF05", rule_name="Khả năng trả nợ yếu", status="KÍCH HOẠT", severity="CRITICAL",
            evidence=evidence, threshold=f"quy tắc demo: DSCR {DSCR_THRESHOLD} lần, ICR {ICR_THRESHOLD} lần",
            comment="Chưa xác nhận là chuẩn MSB chính thức — cần người thẩm định xác nhận trước khi dùng chính thức.",
            observed_value=dscr.value if dscr_weak else icr.value,
            policy_version=RF05_POLICY_VERSION,
            verification_question="Nguồn trả nợ/CFADS có ổn định không? Khách hàng có phương án bổ sung tài sản đảm bảo hoặc nguồn thu thay thế không?",
            recommended_action="Yêu cầu phương án tăng cường nguồn trả nợ hoặc tài sản đảm bảo bổ sung; chuyển Credit Officer thẩm định kỹ.",
            evidence_refs={**dscr.evidence, **icr.evidence},
        )

    # Neither metric is weak — but spec §6 forbids reporting a clean pass while
    # one of them is missing: "không kết luận 'không có cảnh báo'". A healthy
    # ICR says nothing about a DSCR that was never computable.
    if dscr.status == "NEED_MORE_DATA" or icr.status == "NEED_MORE_DATA":
        return _insufficient_data(dscr, icr)

    return RuleResult(
        rule_id="RF05", rule_name="Khả năng trả nợ yếu", status="KHÔNG KÍCH HOẠT",
        policy_version=RF05_POLICY_VERSION,
        evidence_refs={**dscr.evidence, **icr.evidence},
    )
