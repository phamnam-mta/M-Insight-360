from app.agents.eb.financial_inputs import EbFinancialInputs
from app.agents.eb.repayment_capacity import (
    compute_dscr,
    compute_icr,
    evaluate_rf05_dscr_weak,
    evaluate_rf07_high_interest_burden,
    evaluate_rf09_icr_weak,
)
from app.engine.core.types import Metric


def test_dscr_computed():
    inputs = EbFinancialInputs(pat_vnd=1_000_000_000, depreciation_vnd=200_000_000, interest_due_vnd=200_000_000, principal_due_vnd=1_000_000_000)
    metric = compute_dscr(inputs)
    assert round(metric.value, 4) == round(1_400_000_000 / 1_200_000_000, 4)


def test_dscr_input_values_use_real_ebfinancialinputs_field_names_not_generic_keys():
    # Regression guard: input_values must be re-postable as EbFinancialInputs
    # kwargs (the Stress Test drawer's own data path), so the keys must be
    # real dataclass field names — never generic labels like "interest"/
    # "principal" that silently get dropped by a valid_fields filter.
    inputs = EbFinancialInputs(pat_vnd=1_000_000_000, depreciation_vnd=200_000_000, interest_due_vnd=200_000_000, principal_due_vnd=1_000_000_000)
    metric = compute_dscr(inputs)
    assert metric.input_values["interest_due_vnd"] == 200_000_000
    assert metric.input_values["principal_due_vnd"] == 1_000_000_000
    assert "interest" not in metric.input_values
    assert "principal" not in metric.input_values


def test_dscr_comprehensive_input_values_use_comprehensive_field_names():
    inputs = EbFinancialInputs(
        pat_vnd=1_000_000_000, depreciation_vnd=200_000_000,
        interest_expense_vnd=250_000_000, total_principal_due_vnd=1_200_000_000,
    )
    metric = compute_dscr(inputs, comprehensive=True)
    assert metric.input_values["interest_expense_vnd"] == 250_000_000
    assert metric.input_values["total_principal_due_vnd"] == 1_200_000_000


def test_dscr_missing_data_is_not_zero():
    metric = compute_dscr(EbFinancialInputs())
    assert metric.status == "NEED_MORE_DATA"
    assert metric.value is None


def test_dscr_comprehensive_mode_uses_total_principal_and_total_interest():
    inputs = EbFinancialInputs(
        pat_vnd=1_000_000_000, depreciation_vnd=200_000_000,
        interest_expense_vnd=250_000_000, total_principal_due_vnd=1_200_000_000,
    )
    metric = compute_dscr(inputs, comprehensive=True)
    assert round(metric.value, 4) == round(1_450_000_000 / 1_450_000_000, 4)


def test_dscr_comprehensive_mode_need_more_data_without_comprehensive_fields():
    # total_principal_due_vnd absent — must NOT silently fall back to
    # principal_due_vnd under the comprehensive label.
    inputs = EbFinancialInputs(pat_vnd=1_000_000_000, depreciation_vnd=200_000_000, interest_due_vnd=200_000_000, principal_due_vnd=1_000_000_000)
    metric = compute_dscr(inputs, comprehensive=True)
    assert metric.status == "NEED_MORE_DATA"


def test_icr_computed():
    inputs = EbFinancialInputs(pbt_vnd=600_000_000, interest_expense_vnd=200_000_000)
    metric = compute_icr(inputs)
    assert metric.value == 4.0


def test_icr_uses_ebit_fallback_when_ebit_vnd_not_directly_extracted():
    inputs = EbFinancialInputs(pbt_vnd=600_000_000, interest_expense_vnd=200_000_000)
    metric = compute_icr(inputs)
    assert metric.value == 4.0  # (600M + 200M) / 200M


def test_icr_zero_interest_expense_is_need_more_data_not_infinity():
    inputs = EbFinancialInputs(pbt_vnd=600_000_000, interest_expense_vnd=0)
    metric = compute_icr(inputs)
    assert metric.status == "NEED_MORE_DATA"


def test_rf05_fires_on_weak_dscr_only():
    dscr = Metric(metric="dscr", value=0.62, formula="x", input_values={}, input_sources={})
    result = evaluate_rf05_dscr_weak(dscr)
    assert result.rule_id == "RF05"
    assert result.status == "KÍCH HOẠT"
    assert result.observed_value == 0.62


def test_rf05_not_activated_when_dscr_healthy():
    dscr = Metric(metric="dscr", value=1.5, formula="x", input_values={}, input_sources={})
    result = evaluate_rf05_dscr_weak(dscr)
    assert result.status == "KHÔNG KÍCH HOẠT"


def test_rf05_insufficient_data_when_dscr_missing():
    dscr = Metric.need_more_data("dscr", "x")
    result = evaluate_rf05_dscr_weak(dscr)
    assert result.status == "CHƯA ĐÁNH GIÁ"


def test_rf09_fires_on_weak_icr_only():
    icr = Metric(metric="icr", value=0.75, formula="x", input_values={}, input_sources={})
    result = evaluate_rf09_icr_weak(icr)
    assert result.rule_id == "RF09"
    assert result.status == "KÍCH HOẠT"
    assert result.observed_value == 0.75


def test_rf09_insufficient_data_when_icr_missing():
    icr = Metric.need_more_data("icr", "x")
    result = evaluate_rf09_icr_weak(icr)
    assert result.status == "CHƯA ĐÁNH GIÁ"


def test_dscr_and_rf05_carry_evidence_refs():
    from app.agents.eb.financial_inputs import FieldEvidence
    from app.engine.core.types import EvidenceRef

    ref = EvidenceRef(file_id="f1", filename="pakd.pdf", location="Trang 1", original_text="Loi nhuan sau thue: 1.000.000.000")
    field_evidence = {"pat_vnd": FieldEvidence(status="COMPUTED", evidence=[ref])}
    inputs = EbFinancialInputs(pat_vnd=1_000_000_000, depreciation_vnd=200_000_000, interest_due_vnd=200_000_000, principal_due_vnd=1_000_000_000)
    dscr = compute_dscr(inputs, field_evidence)
    assert dscr.evidence["pat_vnd"] == [ref]
    result = evaluate_rf05_dscr_weak(dscr)
    assert result.evidence_refs.get("pat_vnd") == [ref]


def test_rf07_activates_when_interest_exceeds_30pct_of_ebit():
    inputs = EbFinancialInputs(pbt_vnd=600_000_000, interest_expense_vnd=300_000_000)  # EBIT = 900M, 300/900=33%
    result = evaluate_rf07_high_interest_burden(inputs)
    assert result.status == "KÍCH HOẠT"
    assert result.severity == "MEDIUM"


def test_rf07_not_activated_below_threshold():
    inputs = EbFinancialInputs(pbt_vnd=600_000_000, interest_expense_vnd=100_000_000)  # EBIT=700M, 100/700=14%
    result = evaluate_rf07_high_interest_burden(inputs)
    assert result.status == "KHÔNG KÍCH HOẠT"


def test_rf07_not_evaluated_without_data():
    result = evaluate_rf07_high_interest_burden(EbFinancialInputs())
    assert result.status == "CHƯA ĐÁNH GIÁ"
