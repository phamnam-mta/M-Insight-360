import re
from datetime import date

from app.agents.eb.policy_config import POLICY_CONFIG
from app.engine.core.types import ConditionRow, EvidencedField
from app.extraction.evidence_search import find_all_matches
from app.extraction.types import ExtractedDocument

_DATE_PATTERN = re.compile(r"ngay thanh lap[:\s]*(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4})")


def _parse_vn_date(raw: str) -> date | None:
    for sep in ("/", "-", "."):
        if sep in raw:
            parts = raw.split(sep)
            if len(parts) == 3:
                try:
                    d, m, y = int(parts[0]), int(parts[1]), int(parts[2])
                    if y < 100:
                        y += 2000
                    return date(y, m, d)
                except ValueError:
                    return None
    return None


def evaluate_operating_history(
    documents: list[ExtractedDocument], today: date | None = None
) -> ConditionRow:
    today = today or date.today()
    threshold = POLICY_CONFIG["MIN_OPERATING_MONTHS"].value
    compare_rule = f"≥ {threshold} tháng"
    matches = find_all_matches(documents, _DATE_PATTERN)
    if not matches:
        observed = EvidencedField(
            field_id="operating_months", label="Số năm hoạt động", value=None,
            unit="tháng", period=None, status="MISSING_DATA",
        )
        return ConditionRow(
            condition_id="C07", condition_name="Số năm hoạt động", observed=observed,
            compare_rule=compare_rule, result="INSUFFICIENT_DATA",
            reason_if_incomplete="Không tìm thấy ngày thành lập trong hồ sơ.",
        )

    parsed_dates = {_parse_vn_date(raw) for _, raw in matches}
    parsed_dates.discard(None)
    refs = [ref for ref, _ in matches]
    if len(parsed_dates) != 1:
        observed = EvidencedField(
            field_id="operating_months", label="Số năm hoạt động", value=None,
            unit="tháng", period=None, status="PENDING_REVIEW", evidence=refs,
        )
        return ConditionRow(
            condition_id="C07", condition_name="Số năm hoạt động", observed=observed,
            compare_rule=compare_rule, result="INSUFFICIENT_DATA",
            reason_if_incomplete="Không xác định được một ngày thành lập duy nhất, đáng tin cậy từ hồ sơ.",
        )

    start_date = next(iter(parsed_dates))
    months = (today.year - start_date.year) * 12 + (today.month - start_date.month)
    observed = EvidencedField(
        field_id="operating_months", label="Số năm hoạt động", value=months,
        unit="tháng", period=None, status="COMPUTED", evidence=refs,
        policy_version=POLICY_CONFIG["MIN_OPERATING_MONTHS"].policy_version_label,
    )
    return ConditionRow(
        condition_id="C07", condition_name="Số năm hoạt động", observed=observed,
        compare_rule=compare_rule, result="PASS" if months >= threshold else "FAIL",
    )
