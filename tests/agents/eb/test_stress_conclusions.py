from app.engine.core.types import Metric
from app.agents.eb.stress_conclusions import generate_conclusions, generate_recommended_actions


def _metric(value, status="OK"):
    return Metric(metric="m", value=value, formula="f", input_values={}, input_sources={}, status=status)


def test_conclusion_cites_dscr_crossing_below_threshold():
    before = {"dscr": _metric(1.28), "icr": _metric(2.0)}
    after = {"dscr": _metric(0.94), "icr": _metric(1.8)}
    conclusions = generate_conclusions(before, after, comprehensive=False)
    assert any("1.28" in c and "0.94" in c and "1.0" in c for c in conclusions)


def test_conclusion_cites_icr_degradation():
    before = {"dscr": _metric(1.5), "icr": _metric(1.8)}
    after = {"dscr": _metric(1.4), "icr": _metric(1.42)}
    conclusions = generate_conclusions(before, after, comprehensive=False)
    assert any("1.42" in c for c in conclusions)


def test_conclusions_capped_at_three():
    before = {"dscr": _metric(2.0), "icr": _metric(3.0)}
    after = {"dscr": _metric(0.5), "icr": _metric(0.5)}
    conclusions = generate_conclusions(before, after, comprehensive=False)
    assert len(conclusions) <= 3


def test_no_conclusions_when_nothing_crosses_a_threshold():
    before = {"dscr": _metric(2.0), "icr": _metric(3.0)}
    after = {"dscr": _metric(1.9), "icr": _metric(2.9)}
    assert generate_conclusions(before, after, comprehensive=False) == []


def test_recommended_actions_ordered_when_dscr_weak_after_stress():
    before = {"dscr": _metric(1.3), "icr": _metric(2.0)}
    after = {"dscr": _metric(0.9), "icr": _metric(1.6)}
    actions = generate_recommended_actions(before, after)
    assert actions[0].startswith("Yêu cầu bảng tuổi nợ")


def test_no_recommended_actions_when_nothing_degrades_past_threshold():
    before = {"dscr": _metric(2.0), "icr": _metric(3.0)}
    after = {"dscr": _metric(1.9), "icr": _metric(2.9)}
    assert generate_recommended_actions(before, after) == []
