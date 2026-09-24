import re
from collections.abc import Callable

from app.agents.eb.canonical import CanonicalField
from app.engine.core.numbers import parse_vn_number
from app.engine.core.types import ConditionRow, EvidencedField
from app.extraction.evidence_search import find_all_matches
from app.extraction.types import ExtractedDocument


def build_numeric_condition(
    condition_id: str,
    condition_name: str,
    field_id: str,
    documents: list[ExtractedDocument],
    pattern: re.Pattern,
    compare_rule_text: str,
    evaluate_fn: Callable[[float], bool],
    unit: str | None = "VND",
    period: str | None = None,
) -> ConditionRow:
    matches = find_all_matches(documents, pattern)
    if not matches:
        observed = EvidencedField(
            field_id=field_id, label=condition_name, value=None, unit=unit,
            period=period, status="MISSING_DATA",
        )
        return ConditionRow(
            condition_id=condition_id, condition_name=condition_name, observed=observed,
            compare_rule=compare_rule_text, result="INSUFFICIENT_DATA",
            reason_if_incomplete=f"Không tìm thấy dữ liệu cho '{condition_name}' trong hồ sơ đã tải lên.",
        )

    distinct_values = {round(parse_vn_number(raw), 6) for _, raw in matches}
    refs = [ref for ref, _ in matches]

    if len(distinct_values) > 1:
        observed = EvidencedField(
            field_id=field_id, label=condition_name, value=None, unit=unit,
            period=period, status="PENDING_REVIEW", evidence=refs,
        )
        return ConditionRow(
            condition_id=condition_id, condition_name=condition_name, observed=observed,
            compare_rule=compare_rule_text, result="INSUFFICIENT_DATA",
            reason_if_incomplete="Các nguồn tài liệu cho giá trị khác nhau — cần cán bộ xác nhận trước khi kết luận.",
        )

    value = parse_vn_number(matches[0][1])
    observed = EvidencedField(
        field_id=field_id, label=condition_name, value=value, unit=unit,
        period=period, status="COMPUTED", evidence=refs,
    )
    result = "PASS" if evaluate_fn(value) else "FAIL"
    return ConditionRow(
        condition_id=condition_id, condition_name=condition_name, observed=observed,
        compare_rule=compare_rule_text, result=result,
    )


def condition_from_canonical(
    condition_id: str,
    condition_name: str,
    canonical_field: "CanonicalField | None",
    compare_rule_text: str,
    evaluate_fn: Callable[[float], bool],
    unit: str | None = "VND",
) -> ConditionRow:
    if canonical_field is None or not canonical_field.co_gia_tri:
        # A field can be "no value yet" for two different reasons: never
        # matched at all (no evidence — genuinely MISSING_DATA), or matched
        # with conflicting values (evidence present — PENDING_REVIEW). The
        # two blocks (this one and financial_inputs_by_period) must agree
        # on which one it is for the same underlying CanonicalField.
        has_evidence = bool(canonical_field and canonical_field.evidence)
        observed = EvidencedField(
            field_id=condition_name, label=condition_name, value=None, unit=unit,
            period=canonical_field.nam if canonical_field else None,
            status="PENDING_REVIEW" if has_evidence else "MISSING_DATA",
            evidence=canonical_field.evidence if canonical_field else [],
        )
        reason = (
            f"Các nguồn cho '{condition_name}' khác nhau — cần cán bộ xác nhận trước khi kết luận."
            if has_evidence
            else f"Không tìm thấy dữ liệu cho '{condition_name}' trong hồ sơ đã tải lên."
        )
        return ConditionRow(
            condition_id=condition_id, condition_name=condition_name, observed=observed,
            compare_rule=compare_rule_text, result="INSUFFICIENT_DATA",
            reason_if_incomplete=reason,
        )
    value = canonical_field.gia_tri
    observed = EvidencedField(
        field_id=condition_name, label=condition_name, value=value, unit=unit,
        period=canonical_field.nam, status="COMPUTED", evidence=canonical_field.evidence,
    )
    return ConditionRow(
        condition_id=condition_id, condition_name=condition_name, observed=observed,
        compare_rule=compare_rule_text, result="PASS" if evaluate_fn(value) else "FAIL",
    )
