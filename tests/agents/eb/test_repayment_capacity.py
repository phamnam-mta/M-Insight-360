from app.agents.eb.financial_inputs import EbFinancialInputs
from app.agents.eb.repayment_capacity import compute_dscr, compute_icr, evaluate_rf05_weak_repayment_capacity


def test_dscr_computed():
    inputs = EbFinancialInputs(pat_vnd=1_000_000_000, depreciation_vnd=200_000_000, interest_due_vnd=200_000_000, principal_due_vnd=1_000_000_000)
    metric = compute_dscr(inputs)
    assert round(metric.value, 4) == round(1_400_000_000 / 1_200_000_000, 4)


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


def test_rf05_activates_when_dscr_below_1():
    dscr = compute_dscr(EbFinancialInputs(pat_vnd=100_000_000, depreciation_vnd=0, principal_due_vnd=1_000_000_000, interest_due_vnd=0))
    icr = compute_icr(EbFinancialInputs(pbt_vnd=600_000_000, interest_expense_vnd=200_000_000))
    result = evaluate_rf05_weak_repayment_capacity(dscr, icr)
    assert result.status == "KÍCH HOẠT"
    assert result.severity == "CRITICAL"


def test_rf05_not_evaluated_when_both_metrics_missing():
    dscr = compute_dscr(EbFinancialInputs())
    icr = compute_icr(EbFinancialInputs())
    result = evaluate_rf05_weak_repayment_capacity(dscr, icr)
    assert result.status == "CHƯA ĐÁNH GIÁ"


def test_rf05_not_activated_when_both_metrics_healthy():
    dscr = compute_dscr(EbFinancialInputs(pat_vnd=1_000_000_000, depreciation_vnd=0, principal_due_vnd=1_000_000_000, interest_due_vnd=0))
    icr = compute_icr(EbFinancialInputs(pbt_vnd=600_000_000, interest_expense_vnd=200_000_000))
    result = evaluate_rf05_weak_repayment_capacity(dscr, icr)
    assert result.status == "KHÔNG KÍCH HOẠT"


def test_rf05_activates_when_one_metric_missing_and_other_weak():
    # Spec: thiếu LNST/khấu hao/gốc/lãi -> KHÔNG ĐỦ DỮ LIỆU for that metric, never 0 —
    # but if the OTHER metric (ICR) is present and weak, RF05 must still activate
    # rather than being swallowed by the missing DSCR.
    dscr = compute_dscr(EbFinancialInputs())
    icr = compute_icr(EbFinancialInputs(pbt_vnd=-100_000_000, interest_expense_vnd=200_000_000))
    result = evaluate_rf05_weak_repayment_capacity(dscr, icr)
    assert result.status == "KÍCH HOẠT"
    assert result.severity == "CRITICAL"


def test_rf05_missing_dscr_with_healthy_icr_is_not_a_clean_pass():
    # Spec §6: a missing DSCR must never read as a pass. RF05 only reported
    # CHƯA ĐÁNH GIÁ when *both* metrics were missing, so a bundle with no debt
    # schedule but a healthy ICR came back "KHÔNG KÍCH HOẠT" — indistinguishable
    # from a company that was actually assessed and found sound.
    dscr = compute_dscr(EbFinancialInputs())
    icr = compute_icr(EbFinancialInputs(pbt_vnd=600_000_000, interest_expense_vnd=200_000_000))
    result = evaluate_rf05_weak_repayment_capacity(dscr, icr)
    assert result.status == "CHƯA ĐÁNH GIÁ"
    assert result.observed_value == "KHÔNG ĐỦ DỮ LIỆU"


def test_rf05_missing_icr_with_healthy_dscr_is_not_a_clean_pass():
    dscr = compute_dscr(EbFinancialInputs(pat_vnd=1_000_000_000, depreciation_vnd=0, principal_due_vnd=1_000_000_000, interest_due_vnd=0))
    icr = compute_icr(EbFinancialInputs())
    result = evaluate_rf05_weak_repayment_capacity(dscr, icr)
    assert result.status == "CHƯA ĐÁNH GIÁ"


def test_dscr_and_rf05_carry_evidence_refs():
    from app.agents.eb.financial_inputs import FieldEvidence
    from app.engine.core.types import EvidenceRef

    ref = EvidenceRef(file_id="f1", filename="pakd.pdf", location="Trang 1", original_text="Loi nhuan sau thue: 1.000.000.000")
    field_evidence = {"pat_vnd": FieldEvidence(status="COMPUTED", evidence=[ref])}
    inputs = EbFinancialInputs(pat_vnd=1_000_000_000, depreciation_vnd=200_000_000, interest_due_vnd=200_000_000, principal_due_vnd=1_000_000_000)
    dscr = compute_dscr(inputs, field_evidence)
    assert dscr.evidence["pat_vnd"] == [ref]
    icr = compute_icr(EbFinancialInputs(pbt_vnd=600_000_000, interest_expense_vnd=200_000_000))
    result = evaluate_rf05_weak_repayment_capacity(dscr, icr)
    assert result.evidence_refs.get("pat_vnd") == [ref]
