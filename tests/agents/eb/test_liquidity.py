from app.agents.eb.financial_inputs import EbFinancialInputs
from app.agents.eb.liquidity import compute_current_ratio, compute_nwc, evaluate_rf01_capital_imbalance


def test_compute_nwc():
    inputs = EbFinancialInputs(current_assets_vnd=2_000_000_000, current_liabilities_vnd=2_500_000_000)
    metric = compute_nwc(inputs)
    assert metric.value == -500_000_000


def test_compute_nwc_missing_data():
    metric = compute_nwc(EbFinancialInputs())
    assert metric.status == "NEED_MORE_DATA"


def test_current_ratio_only_when_denominator_positive():
    inputs = EbFinancialInputs(current_assets_vnd=2_000_000_000, current_liabilities_vnd=0)
    metric = compute_current_ratio(inputs)
    assert metric.status == "NEED_MORE_DATA"


def test_current_ratio_computed():
    inputs = EbFinancialInputs(current_assets_vnd=2_000_000_000, current_liabilities_vnd=1_000_000_000)
    metric = compute_current_ratio(inputs)
    assert metric.value == 2.0


def test_rf01_activates_on_negative_nwc():
    inputs = EbFinancialInputs(equity_vnd=500_000_000, current_assets_vnd=1_000_000_000, current_liabilities_vnd=1_500_000_000)
    nwc = compute_nwc(inputs)
    result = evaluate_rf01_capital_imbalance(inputs, nwc)
    assert result.status == "KÍCH HOẠT"
    assert result.severity == "HIGH"


def test_rf01_activates_on_zero_equity():
    inputs = EbFinancialInputs(equity_vnd=0, current_assets_vnd=1_000_000_000, current_liabilities_vnd=500_000_000)
    nwc = compute_nwc(inputs)
    result = evaluate_rf01_capital_imbalance(inputs, nwc)
    assert result.status == "KÍCH HOẠT"


def test_rf01_not_activated_when_healthy():
    inputs = EbFinancialInputs(equity_vnd=1_000_000_000, current_assets_vnd=2_000_000_000, current_liabilities_vnd=500_000_000)
    nwc = compute_nwc(inputs)
    result = evaluate_rf01_capital_imbalance(inputs, nwc)
    assert result.status == "KHÔNG KÍCH HOẠT"


def test_rf01_not_evaluated_when_data_missing():
    result = evaluate_rf01_capital_imbalance(EbFinancialInputs(), compute_nwc(EbFinancialInputs()))
    assert result.status == "CHƯA ĐÁNH GIÁ"


def test_nwc_carries_evidence_when_field_evidence_provided():
    from app.agents.eb.financial_inputs import FieldEvidence
    from app.engine.core.types import EvidenceRef

    ref = EvidenceRef(file_id="f1", filename="bctc.pdf", location="Trang 1", original_text="Tai san ngan han: 2.000.000.000")
    field_evidence = {
        "current_assets_vnd": FieldEvidence(status="COMPUTED", evidence=[ref]),
        "current_liabilities_vnd": FieldEvidence(status="COMPUTED", evidence=[]),
    }
    inputs = EbFinancialInputs(current_assets_vnd=2_000_000_000, current_liabilities_vnd=2_500_000_000)
    metric = compute_nwc(inputs, field_evidence)
    assert metric.evidence["current_assets_vnd"] == [ref]
