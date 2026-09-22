import re

from app.agents.crosssell.card_types import Opportunity
from app.agents.crosssell.scenario_templates import generate_partner_scenarios, generate_scenarios


def _opp(priority="P1", rule_id="RULE3_IDLE", signal="Vốn nhàn rỗi 169,9 tỷ nằm ở chứng khoán, ổn định 2 năm."):
    return Opportunity(
        rule_id=rule_id, san_pham="Chứng chỉ tiền gửi (CCTG) — nguồn vốn nhàn rỗi", segment="EB",
        deal_size=169_910_860_881, deal_size_headline="169,9 tỷ", deal_size_exact="169.910.860.881",
        priority=priority, confidence="M", ly_do_confidence="x", signal_1dong=signal,
    )


def test_pna_opportunity_gets_no_scenarios():
    assert generate_scenarios(_opp(priority="P-NA")) == []


def test_p1_p2_get_both_scenario_types():
    scenarios = generate_scenarios(_opp(priority="P1"))
    kinds = {s.loai for s in scenarios}
    assert kinds == {"A", "B"}


def test_p3_gets_only_scenario_a():
    scenarios = generate_scenarios(_opp(priority="P3"))
    assert [s.loai for s in scenarios] == ["A"]


def test_scenario_b_contains_no_digits():
    scenarios = generate_scenarios(_opp(priority="P1"))
    b = next(s for s in scenarios if s.loai == "B")
    assert not re.search(r"\d", b.noi_dung)


def test_scenario_b_does_not_name_the_source_customer():
    customer_name = "CONG TY CO PHAN DAU TU ALPHA GROUP"
    scenarios = generate_scenarios(_opp(priority="P1"))
    b = next(s for s in scenarios if s.loai == "B")
    assert customer_name.upper() not in b.noi_dung.upper()
    assert "ALPHA" not in b.noi_dung.upper()


def test_scenario_a_contains_at_least_one_figure_from_the_signal():
    scenarios = generate_scenarios(_opp(priority="P3"))
    a = scenarios[0]
    assert re.search(r"\d", a.noi_dung) or "tỷ" in a.noi_dung


def test_partner_scenario_never_names_partner_or_source():
    scenarios = generate_partner_scenarios("CONG TY A036", "Ca hai", "holding / đầu tư tài chính")
    assert len(scenarios) == 1
    assert "A036" not in scenarios[0].noi_dung
    assert not re.search(r"\d", scenarios[0].noi_dung)
