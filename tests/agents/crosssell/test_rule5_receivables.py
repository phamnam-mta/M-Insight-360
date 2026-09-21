from app.agents.crosssell.rule5_receivables import (
    compute_dso_dpo,
    deal_size_receivables_financing,
    evaluate_rule5,
    leak_ratio_msb_share,
)


def test_deal_size_default_method_is_80_percent():
    assert deal_size_receivables_financing(receivables_131_current_vnd=1_000_000_000) == 800_000_000


def test_deal_size_lc_method_is_90_percent():
    assert deal_size_receivables_financing(receivables_131_current_vnd=1_000_000_000, method="lc_or_bltt") == 900_000_000


def test_deal_size_perfect_lc_bct_method_is_98_percent():
    assert deal_size_receivables_financing(receivables_131_current_vnd=1_000_000_000, method="perfect_bct_lc") == 980_000_000


def test_dso_dpo_computed():
    result = compute_dso_dpo(receivables_131_vnd=500_000_000, revenue_period_vnd=3_000_000_000, payables_331_vnd=300_000_000, cogs_period_vnd=2_000_000_000, period_days=365)
    assert round(result["dso_days"], 1) == round(500_000_000 / 3_000_000_000 * 365, 1)
    assert round(result["dpo_days"], 1) == round(300_000_000 / 2_000_000_000 * 365, 1)


def test_leak_ratio_below_50_percent_is_strong_signal():
    ratio = leak_ratio_msb_share(operating_in_msb_vnd=400_000_000, total_receivable_credit_131_vnd=1_000_000_000)
    assert ratio == 0.4


def test_evaluate_rule5_skipped_without_debt_aging_table():
    result = evaluate_rule5(receivables_131_current_vnd=None, payables_331_vnd=None)
    assert result.status == "CHƯA ĐÁNH GIÁ"
    assert "bỏ qua" in result.comment.lower() or "khong co bang" in result.comment.lower().replace("ô", "o").replace("ư", "u")


def test_evaluate_rule5_activates_with_receivables_data():
    result = evaluate_rule5(receivables_131_current_vnd=1_000_000_000, payables_331_vnd=None)
    assert result.status == "KÍCH HOẠT"
    assert "800" in result.evidence[0].replace(",", "")
