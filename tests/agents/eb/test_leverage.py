from app.agents.eb.financial_inputs import EbFinancialInputs
from app.agents.eb.leverage import (
    compute_short_term_debt_ratio,
    evaluate_rf03_short_term_debt_ratio,
    evaluate_rf06_receivables_inventory_concentration,
    evaluate_rf08_leverage,
)
from app.engine.core.types import Metric


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


def test_rf06_activates_above_70_pct_concentration():
    inputs = EbFinancialInputs(receivables_vnd=500_000_000, inventory_vnd=300_000_000, current_assets_vnd=1_000_000_000)
    result = evaluate_rf06_receivables_inventory_concentration(inputs)
    assert result.status == "KÍCH HOẠT"
    assert result.severity == "MEDIUM"


def test_rf06_not_activated_below_threshold():
    inputs = EbFinancialInputs(receivables_vnd=100_000_000, inventory_vnd=100_000_000, current_assets_vnd=1_000_000_000)
    result = evaluate_rf06_receivables_inventory_concentration(inputs)
    assert result.status == "KHÔNG KÍCH HOẠT"


def test_rf06_not_evaluated_without_data():
    result = evaluate_rf06_receivables_inventory_concentration(EbFinancialInputs())
    assert result.status == "CHƯA ĐÁNH GIÁ"


def test_rf08_fires_when_leverage_exceeds_2x():
    borrowings = Metric(metric="total_borrowings", value=300, formula="x", input_values={}, input_sources={})
    inputs = EbFinancialInputs(equity_vnd=100)
    result = evaluate_rf08_leverage(borrowings, inputs)
    assert result.rule_id == "RF08"
    assert result.status == "KÍCH HOẠT"
    assert result.observed_value == 3.0


def test_rf08_not_activated_at_or_below_2x():
    borrowings = Metric(metric="total_borrowings", value=200, formula="x", input_values={}, input_sources={})
    inputs = EbFinancialInputs(equity_vnd=100)
    result = evaluate_rf08_leverage(borrowings, inputs)
    assert result.status == "KHÔNG KÍCH HOẠT"


def test_rf08_insufficient_data_when_equity_missing_or_non_positive():
    borrowings = Metric(metric="total_borrowings", value=300, formula="x", input_values={}, input_sources={})
    assert evaluate_rf08_leverage(borrowings, EbFinancialInputs()).status == "CHƯA ĐÁNH GIÁ"
    assert evaluate_rf08_leverage(borrowings, EbFinancialInputs(equity_vnd=0)).status == "CHƯA ĐÁNH GIÁ"


def test_rf08_insufficient_data_when_borrowings_missing():
    result = evaluate_rf08_leverage(Metric.need_more_data("total_borrowings", "x"), EbFinancialInputs(equity_vnd=100))
    assert result.status == "CHƯA ĐÁNH GIÁ"
