import re
import unicodedata

from app.agents.eb.internal_systems import check_internal_system
from app.engine.core.types import ConditionRow, EvidencedField
from app.extraction.evidence_search import find_all_matches
from app.extraction.types import ExtractedDocument

_STATUS_PATTERN = re.compile(r"(dang hoat dong|tam ngung hoat dong|da giai the|giai the)")


def _strip_accents_lower(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(c for c in normalized if not unicodedata.combining(c))
    return ascii_text.lower()


def evaluate_customer_segment() -> ConditionRow:
    # Whether this customer is new or existing at MSB can only come from the
    # bank's own CIF/credit-relationship history — a BCTC or business
    # registration certificate, however complete, cannot answer this.
    observed = EvidencedField(
        field_id="customer_segment", label="Đối tượng áp dụng", value=None,
        unit=None, period=None, status="MISSING_DATA",
    )
    return ConditionRow(
        condition_id="C01", condition_name="Đối tượng áp dụng", observed=observed,
        compare_rule="Xác định KH tín dụng mới hay hiện hữu qua CIF",
        result=check_internal_system("CIF"),
        reason_if_incomplete="Cần đối chiếu CIF/lịch sử quan hệ tín dụng tại MSB — hồ sơ tải lên không đủ căn cứ.",
    )


def evaluate_operating_status(documents: list[ExtractedDocument]) -> ConditionRow:
    # Simplification (documented, not hidden): this reads only the status
    # keyword stated in the uploaded documents themselves, not a live query
    # against the authoritative national business registry.
    matches = find_all_matches(documents, _STATUS_PATTERN)
    compare_rule = "Phải đang hoạt động (không tạm ngừng/giải thể)"
    if not matches:
        observed = EvidencedField(
            field_id="operating_status", label="Tình trạng hoạt động", value=None,
            unit=None, period=None, status="MISSING_DATA",
        )
        return ConditionRow(
            condition_id="C05", condition_name="Tình trạng hoạt động", observed=observed,
            compare_rule=compare_rule, result="INSUFFICIENT_DATA",
            reason_if_incomplete="Không tìm thấy công bố tình trạng hoạt động trong hồ sơ.",
        )
    distinct = {v for _, v in matches}
    refs = [ref for ref, _ in matches]
    if len(distinct) > 1:
        observed = EvidencedField(
            field_id="operating_status", label="Tình trạng hoạt động", value=None,
            unit=None, period=None, status="PENDING_REVIEW", evidence=refs,
        )
        return ConditionRow(
            condition_id="C05", condition_name="Tình trạng hoạt động", observed=observed,
            compare_rule=compare_rule, result="INSUFFICIENT_DATA",
            reason_if_incomplete="Các nguồn công bố tình trạng hoạt động mâu thuẫn nhau.",
        )
    status_text = matches[0][1]
    observed = EvidencedField(
        field_id="operating_status", label="Tình trạng hoạt động", value=status_text,
        unit=None, period=None, status="COMPUTED", evidence=refs,
    )
    is_active = status_text == "dang hoat dong"
    return ConditionRow(
        condition_id="C05", condition_name="Tình trạng hoạt động", observed=observed,
        compare_rule=compare_rule, result="PASS" if is_active else "FAIL",
    )
