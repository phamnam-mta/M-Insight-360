from app.agents.crosssell.statement_parser import parse_statement_documents
from app.agents.eb.canonical import CanonicalField
from app.agents.eb.policy_config import POLICY_CONFIG
from app.engine.core.types import ConditionRow, EvidencedField, EvidenceRef
from app.extraction.types import ExtractedDocument

from ._common import condition_from_canonical


def evaluate_revenue_12m(canonical_fields: dict[str, "CanonicalField"]) -> ConditionRow:
    min_v = POLICY_CONFIG["REVENUE_12M_MIN_VND"].value
    max_v = POLICY_CONFIG["REVENUE_12M_MAX_VND"].value
    return condition_from_canonical(
        condition_id="C02", condition_name="Doanh thu 12 tháng gần nhất",
        canonical_field=canonical_fields.get("IS_REVENUE"),
        compare_rule_text=f"≥ {min_v:,.0f} và < {max_v:,.0f} VND",
        evaluate_fn=lambda v: min_v <= v < max_v,
    )


def evaluate_revenue_6m_statement(documents: list[ExtractedDocument]) -> ConditionRow:
    total_credit = 0.0
    evidence: list[EvidenceRef] = []
    for doc in documents:
        txns = parse_statement_documents([doc])
        if not txns:
            continue
        doc_credit = sum(t.credit for t in txns)
        total_credit += doc_credit
        file_id = getattr(doc, "file_id", doc.filename)
        evidence.append(EvidenceRef(
            file_id=file_id, filename=doc.filename,
            location=f"Toàn bộ sao kê ({len(txns)} giao dịch)",
            original_text=f"Tổng ghi Có: {doc_credit:,.0f} VND",
        ))
    compare_rule = "Tổng ghi Có/giao dịch đủ điều kiện trong 6 tháng gần nhất"
    if not evidence:
        observed = EvidencedField(
            field_id="revenue_6m_statement_vnd", label="Doanh thu 6 tháng gần nhất qua TKTT",
            value=None, unit="VND", period=None, status="MISSING_DATA",
        )
        return ConditionRow(
            condition_id="C03", condition_name="Doanh thu 6 tháng gần nhất qua TKTT",
            observed=observed, compare_rule=compare_rule, result="INSUFFICIENT_DATA",
            reason_if_incomplete="Không tìm thấy sao kê tài khoản thanh toán trong hồ sơ.",
        )
    observed = EvidencedField(
        field_id="revenue_6m_statement_vnd", label="Doanh thu 6 tháng gần nhất qua TKTT",
        value=round(total_credit, 2), unit="VND",
        period="Toàn bộ sao kê tải lên (chưa xác định chính xác cửa sổ 6 tháng)",
        status="COMPUTED", evidence=evidence,
    )
    return ConditionRow(
        condition_id="C03", condition_name="Doanh thu 6 tháng gần nhất qua TKTT",
        observed=observed, compare_rule=compare_rule, result="INSUFFICIENT_DATA",
        reason_if_incomplete=(
            "Có dữ liệu sao kê nhưng chưa xác định được chính xác cửa sổ 6 tháng gần nhất "
            "từ ngày giao dịch — cần cán bộ xác nhận kỳ trước khi kết luận Đạt/Không đạt."
        ),
    )
