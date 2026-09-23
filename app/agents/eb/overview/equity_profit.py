import re

from app.agents.eb.canonical import CanonicalField
from app.engine.core.types import ConditionRow, EvidencedField
from app.extraction.types import ExtractedDocument

from ._common import build_numeric_condition, condition_from_canonical

_LNST_PAKD_PATTERN = re.compile(r"lnst (?:theo )?pakd[:\s]*(-?[\d.,]+)")


def evaluate_equity(canonical_fields: dict[str, CanonicalField]) -> ConditionRow:
    return condition_from_canonical(
        condition_id="C08", condition_name="Vốn chủ sở hữu",
        canonical_field=canonical_fields.get("BS_EQUITY"),
        compare_rule_text="> 0", evaluate_fn=lambda v: v > 0,
    )


def evaluate_lnst_pakd(documents: list[ExtractedDocument]) -> ConditionRow:
    # "LNST theo PAKD" is a business-plan/projection figure, not a BCTC
    # line item — never a FIELD_CODE_MAP entry — so it keeps searching
    # documents directly instead of migrating to canonical.
    return build_numeric_condition(
        condition_id="C09", condition_name="LNST theo PAKD", field_id="lnst_pakd_vnd",
        documents=documents, pattern=_LNST_PAKD_PATTERN, compare_rule_text="> 0",
        evaluate_fn=lambda v: v > 0,
    )


def evaluate_gross_profit_less_interest(canonical_fields: dict[str, CanonicalField]) -> ConditionRow:
    gross = canonical_fields.get("IS_GROSS_PROFIT")
    interest = canonical_fields.get("IS_INTEREST")

    if gross is None or not gross.co_gia_tri or interest is None or not interest.co_gia_tri:
        missing = []
        if gross is None or not gross.co_gia_tri:
            missing.append("lợi nhuận gộp")
        if interest is None or not interest.co_gia_tri:
            missing.append("chi phí lãi vay")
        observed = EvidencedField(
            field_id="gross_profit_less_interest_vnd", label="Lợi nhuận gộp trừ lãi vay",
            value=None, unit="VND", period=None, status="MISSING_DATA",
        )
        return ConditionRow(
            condition_id="C10", condition_name="Lợi nhuận gộp trừ lãi vay", observed=observed,
            compare_rule="> 0", result="INSUFFICIENT_DATA",
            reason_if_incomplete=f"Thiếu {', '.join(missing)} trong hồ sơ.",
        )
    value = gross.gia_tri - interest.gia_tri
    observed = EvidencedField(
        field_id="gross_profit_less_interest_vnd", label="Lợi nhuận gộp trừ lãi vay",
        value=value, unit="VND", period=gross.nam, status="COMPUTED",
        evidence=gross.evidence + interest.evidence,
        formula="loi_nhuan_gop - chi_phi_lai_vay", input_fields=["IS_GROSS_PROFIT", "IS_INTEREST"],
    )
    return ConditionRow(
        condition_id="C10", condition_name="Lợi nhuận gộp trừ lãi vay", observed=observed,
        compare_rule="> 0", result="PASS" if value > 0 else "FAIL",
    )
