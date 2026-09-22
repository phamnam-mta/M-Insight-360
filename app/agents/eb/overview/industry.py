import re
import unicodedata

from app.agents.eb.policy_config import POLICY_CONFIG
from app.engine.core.types import ConditionRow, EvidencedField
from app.extraction.evidence_search import find_all_matches
from app.extraction.types import ExtractedDocument

_INDUSTRY_PATTERN = re.compile(r"nganh nghe(?: kinh doanh)?[:\s]*([^\n]+)")


def _strip_accents_lower(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(c for c in normalized if not unicodedata.combining(c))
    return ascii_text.lower()


def evaluate_industry(documents: list[ExtractedDocument]) -> ConditionRow:
    compare_rule = "Không thuộc danh sách ngành cấm/loại trừ của MSB"
    matches = find_all_matches(documents, _INDUSTRY_PATTERN)
    if not matches:
        observed = EvidencedField(
            field_id="industry", label="Ngành nghề", value=None, unit=None,
            period=None, status="MISSING_DATA",
        )
        return ConditionRow(
            condition_id="C04", condition_name="Ngành nghề", observed=observed,
            compare_rule=compare_rule, result="INSUFFICIENT_DATA",
            reason_if_incomplete="Không tìm thấy ngành nghề đăng ký trong hồ sơ.",
        )

    ref, raw_value = matches[0]
    industry_name = raw_value.strip()
    threshold = POLICY_CONFIG["PROHIBITED_INDUSTRIES"]
    observed = EvidencedField(
        field_id="industry", label="Ngành nghề", value=industry_name, unit=None,
        period=None, status="COMPUTED", evidence=[ref],
        policy_version=threshold.policy_version_label,
    )
    prohibited = threshold.value
    if not prohibited:
        return ConditionRow(
            condition_id="C04", condition_name="Ngành nghề", observed=observed,
            compare_rule=compare_rule, result="INSUFFICIENT_DATA",
            reason_if_incomplete=(
                "Chưa nạp danh sách ngành cấm/loại trừ có kiểm soát phiên bản — không thể kết luận."
            ),
        )
    haystack = _strip_accents_lower(industry_name)
    is_prohibited = any(_strip_accents_lower(p) in haystack for p in prohibited)
    return ConditionRow(
        condition_id="C04", condition_name="Ngành nghề", observed=observed,
        compare_rule=compare_rule, result="FAIL" if is_prohibited else "PASS",
    )
