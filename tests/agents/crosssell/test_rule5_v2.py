from app.agents.crosssell.rule5_v2 import (
    compute_dso_dpo,
    evaluate_rule5a_receivables_financing,
    evaluate_rule5b_payables_scf,
    evaluate_rule5d_leak,
    rule5c_conclusion,
)


def test_rule5a_no_table_is_pna():
    result = evaluate_rule5a_receivables_financing(None, None, has_aging_column=False, confidence_cap="H")
    assert result.priority == "P-NA"


def test_rule5a_default_rate_80_pct():
    result = evaluate_rule5a_receivables_financing(
        1_030_523_666, None, has_aging_column=False, confidence_cap="H",
    )
    assert result.deal_size == round(1_030_523_666 * 0.80)
    assert any("cột tuổi nợ" in w for w in result.canh_bao)


def test_rule5a_no_warning_when_aging_column_present():
    result = evaluate_rule5a_receivables_financing(
        1_000_000_000, None, has_aging_column=True, confidence_cap="H",
    )
    assert not any("cột tuổi nợ" in w for w in result.canh_bao)


def test_rule5a_flags_closing_much_lower_than_opening():
    result = evaluate_rule5a_receivables_financing(
        1_000_000_000, 10_000_000_000, has_aging_column=True, confidence_cap="H",
    )
    assert any("điểm trũng" in w or "bình quân" in w for w in result.canh_bao)


def test_rule5b_no_table_is_pna():
    result = evaluate_rule5b_payables_scf(None, None, confidence_cap="H")
    assert result.priority == "P-NA"


def test_rule5b_uses_average_when_closing_is_a_trough():
    result = evaluate_rule5b_payables_scf(1_440_085_191, 15_656_147_696, confidence_cap="H")
    assert result.deal_size == round((1_440_085_191 + 15_656_147_696) / 2)
    assert any("bình quân" in w for w in result.canh_bao)


def test_rule5b_uses_closing_when_stable():
    result = evaluate_rule5b_payables_scf(8_000_000_000, 8_500_000_000, confidence_cap="H")
    assert result.deal_size == 8_000_000_000


def test_dso_dpo_computation():
    r = compute_dso_dpo(1_030_523_666, 90_105_893_754, 1_440_085_191, 73_340_931_618)
    assert round(r["dso_days"], 2) == 4.17
    assert round(r["dpo_days"], 2) == 7.17


def test_rule5c_low_dso_dpo_redirects_focus():
    conclusion = rule5c_conclusion(4.17, 7.17)
    assert "KHÔNG bị chiếm dụng" in conclusion


def test_rule5c_missing_inputs_returns_none():
    assert rule5c_conclusion(None, None) is None


def test_rule5d_no_msb_statement_is_the_opportunity_not_missing_data():
    result = evaluate_rule5d_leak(0.0, 100_000_000_000, has_msb_statement=False)
    assert result["status"] == "khong_tinh_duoc"
    assert "cơ hội" in result["note"]


def test_rule5d_computes_ratio_when_msb_statement_present():
    result = evaluate_rule5d_leak(40_000_000_000, 100_000_000_000, has_msb_statement=True)
    assert result["status"] == "tinh_duoc"
    assert result["ratio"] == 0.4
