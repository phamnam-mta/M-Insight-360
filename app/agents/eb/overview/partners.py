from app.agents.crosssell.rule2_partners import is_excluded_from_partner_ranking
from app.agents.crosssell.statement_parser import parse_statement_documents
from app.agents.eb.policy_config import POLICY_CONFIG
from app.engine.core.types import ConditionRow, EvidencedField, EvidenceRef
from app.extraction.types import ExtractedDocument


def evaluate_top_partners(documents: list[ExtractedDocument]) -> ConditionRow:
    compare_rule = "≥ 03/05 đối tác đầu ra/đầu vào có hoạt động/hóa đơn trong 6 tháng"
    outbound_partners: set[str] = set()  # đầu ra: partner paid us (credit)
    inbound_partners: set[str] = set()   # đầu vào: we paid partner (debit)
    evidence: list[EvidenceRef] = []

    for doc in documents:
        txns = parse_statement_documents([doc])
        if not txns:
            continue
        for t in txns:
            if is_excluded_from_partner_ranking(t) or not t.partner.strip():
                continue
            if t.credit > 0:
                outbound_partners.add(t.partner)
            if t.debit > 0:
                inbound_partners.add(t.partner)
        if outbound_partners or inbound_partners:
            file_id = getattr(doc, "file_id", doc.filename)
            evidence.append(EvidenceRef(
                file_id=file_id, filename=doc.filename,
                location=f"Toàn bộ sổ chi tiết ({len(txns)} giao dịch)",
                original_text=f"Đầu ra: {len(outbound_partners)} đối tác, Đầu vào: {len(inbound_partners)} đối tác",
            ))

    if not evidence:
        observed = EvidencedField(
            field_id="top_partners_count", label="03/05 đối tác đầu ra, đầu vào lớn nhất",
            value=None, unit=None, period=None, status="MISSING_DATA",
        )
        return ConditionRow(
            condition_id="C06", condition_name="03/05 đối tác đầu ra, đầu vào lớn nhất",
            observed=observed, compare_rule=compare_rule, result="INSUFFICIENT_DATA",
            reason_if_incomplete="Không tìm thấy sổ chi tiết bán/mua hàng hoặc sao kê trong hồ sơ.",
        )

    threshold = POLICY_CONFIG["TOP_PARTNERS_COUNT"]
    observed = EvidencedField(
        field_id="top_partners_count", label="03/05 đối tác đầu ra, đầu vào lớn nhất",
        value=f"Đầu ra: {len(outbound_partners)} đối tác, Đầu vào: {len(inbound_partners)} đối tác",
        unit=None, period=None, status="COMPUTED", evidence=evidence,
        policy_version=threshold.policy_version_label,
    )
    return ConditionRow(
        condition_id="C06", condition_name="03/05 đối tác đầu ra, đầu vào lớn nhất",
        observed=observed, compare_rule=compare_rule, result="INSUFFICIENT_DATA",
        reason_if_incomplete=threshold.open_question,
    )
