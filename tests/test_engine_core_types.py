import pytest

from app.engine.core.types import ConditionRow, EvidencedField, EvidenceRef, Metric, RuleResult


def _evidence():
    return EvidenceRef(
        file_id="f1", filename="bctc.pdf", location="Trang 3",
        original_text="Von chu so huu: 500.000.000",
    )


def test_evidenced_field_missing_data_cannot_carry_a_value():
    with pytest.raises(ValueError):
        EvidencedField(
            field_id="equity_vnd", label="Vốn chủ sở hữu", value=500_000_000,
            unit="VND", period=None, status="MISSING_DATA",
        )


def test_evidenced_field_ok_with_value_when_computed():
    f = EvidencedField(
        field_id="equity_vnd", label="Vốn chủ sở hữu", value=500_000_000,
        unit="VND", period="2025", status="COMPUTED", evidence=[_evidence()],
    )
    assert f.value == 500_000_000
    assert f.evidence[0].location == "Trang 3"


def test_condition_row_pass_requires_observed_value():
    observed = EvidencedField(
        field_id="revenue_12m_vnd", label="Doanh thu 12 tháng", value=None,
        unit="VND", period=None, status="MISSING_DATA",
    )
    with pytest.raises(ValueError):
        ConditionRow(
            condition_id="C02", condition_name="Doanh thu 12 tháng",
            observed=observed, compare_rule="≥20 tỷ và <1.000 tỷ", result="PASS",
        )


def test_condition_row_insufficient_data_does_not_require_value():
    observed = EvidencedField(
        field_id="revenue_12m_vnd", label="Doanh thu 12 tháng", value=None,
        unit="VND", period=None, status="MISSING_DATA",
    )
    row = ConditionRow(
        condition_id="C02", condition_name="Doanh thu 12 tháng",
        observed=observed, compare_rule="≥20 tỷ và <1.000 tỷ",
        result="INSUFFICIENT_DATA", reason_if_incomplete="Thiếu B02/BCTC.",
    )
    assert row.result == "INSUFFICIENT_DATA"


def test_metric_evidence_defaults_to_empty_dict():
    m = Metric(metric="nwc", value=None, formula="a - b", input_values={}, input_sources={})
    assert m.evidence == {}


def test_rule_result_evidence_refs_defaults_to_empty_dict_and_keeps_existing_evidence_list():
    r = RuleResult(rule_id="RF01", rule_name="Mất cân đối vốn", status="KHÔNG KÍCH HOẠT")
    assert r.evidence_refs == {}
    assert r.evidence == []
