import re

from app.engine.core.numbers import parse_vn_number
from app.engine.core.types import ConditionRow, EvidencedField
from app.extraction.evidence_search import find_all_matches
from app.extraction.types import ExtractedDocument

from ._common import build_numeric_condition

_EQUITY_PATTERN = re.compile(r"von chu so huu[:\s]*(-?[\d.,]+)")
_LNST_PAKD_PATTERN = re.compile(r"lnst (?:theo )?pakd[:\s]*(-?[\d.,]+)")
_GROSS_PROFIT_PATTERN = re.compile(r"loi nhuan gop[:\s]*(-?[\d.,]+)")
_INTEREST_EXPENSE_PATTERN = re.compile(r"chi phi lai vay[:\s]*(-?[\d.,]+)")


def evaluate_equity(documents: list[ExtractedDocument]) -> ConditionRow:
    return build_numeric_condition(
        condition_id="C08", condition_name="Vốn chủ sở hữu", field_id="equity_vnd",
        documents=documents, pattern=_EQUITY_PATTERN, compare_rule_text="> 0",
        evaluate_fn=lambda v: v > 0,
    )


def evaluate_lnst_pakd(documents: list[ExtractedDocument]) -> ConditionRow:
    return build_numeric_condition(
        condition_id="C09", condition_name="LNST theo PAKD", field_id="lnst_pakd_vnd",
        documents=documents, pattern=_LNST_PAKD_PATTERN, compare_rule_text="> 0",
        evaluate_fn=lambda v: v > 0,
    )


def evaluate_gross_profit_less_interest(documents: list[ExtractedDocument]) -> ConditionRow:
    gross_matches = find_all_matches(documents, _GROSS_PROFIT_PATTERN)
    interest_matches = find_all_matches(documents, _INTEREST_EXPENSE_PATTERN)
    compare_rule = "> 0"
    if not gross_matches or not interest_matches:
        missing = []
        if not gross_matches:
            missing.append("lợi nhuận gộp")
        if not interest_matches:
            missing.append("chi phí lãi vay")
        observed = EvidencedField(
            field_id="gross_profit_less_interest_vnd", label="Lợi nhuận gộp trừ lãi vay",
            value=None, unit="VND", period=None, status="MISSING_DATA",
        )
        return ConditionRow(
            condition_id="C10", condition_name="Lợi nhuận gộp trừ lãi vay", observed=observed,
            compare_rule=compare_rule, result="INSUFFICIENT_DATA",
            reason_if_incomplete=f"Thiếu {', '.join(missing)} trong hồ sơ.",
        )

    gross_distinct = {round(parse_vn_number(r), 6) for _, r in gross_matches}
    interest_distinct = {round(parse_vn_number(r), 6) for _, r in interest_matches}
    refs = [ref for ref, _ in gross_matches] + [ref for ref, _ in interest_matches]
    if len(gross_distinct) > 1 or len(interest_distinct) > 1:
        observed = EvidencedField(
            field_id="gross_profit_less_interest_vnd", label="Lợi nhuận gộp trừ lãi vay",
            value=None, unit="VND", period=None, status="PENDING_REVIEW", evidence=refs,
        )
        return ConditionRow(
            condition_id="C10", condition_name="Lợi nhuận gộp trừ lãi vay", observed=observed,
            compare_rule=compare_rule, result="INSUFFICIENT_DATA",
            reason_if_incomplete="Các nguồn cho giá trị lợi nhuận gộp hoặc chi phí lãi vay khác nhau.",
        )

    gross = parse_vn_number(gross_matches[0][1])
    interest = parse_vn_number(interest_matches[0][1])
    value = gross - interest
    observed = EvidencedField(
        field_id="gross_profit_less_interest_vnd", label="Lợi nhuận gộp trừ lãi vay",
        value=value, unit="VND", period=None, status="COMPUTED", evidence=refs,
        formula="loi_nhuan_gop - chi_phi_lai_vay",
        input_fields=["gross_profit_vnd", "interest_expense_vnd"],
    )
    return ConditionRow(
        condition_id="C10", condition_name="Lợi nhuận gộp trừ lãi vay", observed=observed,
        compare_rule=compare_rule, result="PASS" if value > 0 else "FAIL",
    )
