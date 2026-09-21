from app.agents.eb.financial_inputs import EbFinancialInputs
from app.agents.eb.dsp_reconciliation import evaluate_rf04_dsp_mismatch


def test_rf04_not_evaluated_when_dsp_absent():
    # Spec §6: no DSP data => "CHƯA ĐÁNH GIÁ", never "đạt"/KHÔNG KÍCH HOẠT.
    result = evaluate_rf04_dsp_mismatch(EbFinancialInputs(revenue_bctc_vnd=1_000_000_000))
    assert result.status == "CHƯA ĐÁNH GIÁ"
    assert result.status != "KHÔNG KÍCH HOẠT"


def test_rf04_activates_above_5_percent_deviation():
    inputs = EbFinancialInputs(revenue_bctc_vnd=1_000_000_000, revenue_dsp_vnd=1_100_000_000)
    result = evaluate_rf04_dsp_mismatch(inputs)
    assert result.status == "KÍCH HOẠT"
    assert result.severity == "HIGH"


def test_rf04_not_activated_within_5_percent():
    inputs = EbFinancialInputs(revenue_bctc_vnd=1_000_000_000, revenue_dsp_vnd=1_020_000_000)
    result = evaluate_rf04_dsp_mismatch(inputs)
    assert result.status == "KHÔNG KÍCH HOẠT"


def test_rf04_zero_bctc_revenue_is_chua_danh_gia_not_crash():
    inputs = EbFinancialInputs(revenue_bctc_vnd=0, revenue_dsp_vnd=100)
    result = evaluate_rf04_dsp_mismatch(inputs)
    assert result.status == "CHƯA ĐÁNH GIÁ"
