from app.agents.eb.internal_systems import check_internal_system
from app.engine.core.types import ConditionRow, EvidencedField


def evaluate_credit_history() -> ConditionRow:
    observed = EvidencedField(
        field_id="credit_history", label="Lịch sử quan hệ tín dụng", value=None,
        unit=None, period=None, status="MISSING_DATA",
    )
    return ConditionRow(
        condition_id="C11", condition_name="Lịch sử quan hệ tín dụng", observed=observed,
        compare_rule="Không nợ nhóm 2/chậm trả ≥10 ngày trong 12 tháng; không nợ xấu trong 36 tháng",
        result=check_internal_system("CIC"),
        reason_if_incomplete="Cần dữ liệu CIC và lịch sử tại MSB — không thể kết luận chỉ từ hồ sơ tải lên.",
    )
