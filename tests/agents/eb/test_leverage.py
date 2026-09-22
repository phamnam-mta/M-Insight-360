from app.agents.eb.financial_inputs import EbFinancialInputs
from app.agents.eb.leverage import compute_short_term_debt_ratio, evaluate_rf03_short_term_debt_ratio


def test_ratio_computed():
    inputs = EbFinancialInputs(short_term_debt_vnd=1_800_000_000, total_liabilities_vnd=3_000_000_000)
    metric = compute_short_term_debt_ratio(inputs)
    assert metric.value == 0.6


def test_ratio_zero_denominator_does_not_crash():
    inputs = EbFinancialInputs(short_term_debt_vnd=100, total_liabilities_vnd=0)
    metric = compute_short_term_debt_ratio(inputs)
    assert metric.status == "NEED_MORE_DATA"


def test_rf03_activates_above_50_percent():
    inputs = EbFinancialInputs(short_term_debt_vnd=1_800_000_000, total_liabilities_vnd=3_000_000_000)
    ratio = compute_short_term_debt_ratio(inputs)
    result = evaluate_rf03_short_term_debt_ratio(ratio)
    assert result.status == "KÍCH HOẠT"
    assert result.severity == "MEDIUM"
    assert "demo" in result.threshold.lower()


def test_rf03_not_activated_below_50_percent():
    inputs = EbFinancialInputs(short_term_debt_vnd=900_000_000, total_liabilities_vnd=3_000_000_000)
    ratio = compute_short_term_debt_ratio(inputs)
    result = evaluate_rf03_short_term_debt_ratio(ratio)
    assert result.status == "KHÔNG KÍCH HOẠT"


def test_rf03_not_evaluated_when_missing():
    result = evaluate_rf03_short_term_debt_ratio(compute_short_term_debt_ratio(EbFinancialInputs()))
    assert result.status == "CHƯA ĐÁNH GIÁ"


def test_ratio_and_rf03_carry_evidence_refs():
    from app.agents.eb.financial_inputs import FieldEvidence
    from app.engine.core.types import EvidenceRef

    ref = EvidenceRef(file_id="f1", filename="bctc.pdf", location="Trang 1", original_text="Vay ngan han: 1.800.000.000")
    field_evidence = {"short_term_debt_vnd": FieldEvidence(status="COMPUTED", evidence=[ref])}
    inputs = EbFinancialInputs(short_term_debt_vnd=1_800_000_000, total_liabilities_vnd=3_000_000_000)
    ratio = compute_short_term_debt_ratio(inputs, field_evidence)
    assert ratio.evidence["short_term_debt_vnd"] == [ref]
    result = evaluate_rf03_short_term_debt_ratio(ratio)
    assert result.evidence_refs["short_term_debt_vnd"] == [ref]
