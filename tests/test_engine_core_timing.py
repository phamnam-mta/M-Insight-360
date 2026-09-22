import time

from app.engine.core.timing import REQUEST_TIME_BUDGET_SECONDS, narrative_budget_exceeded


def test_narrative_budget_not_exceeded_right_after_start():
    start = time.monotonic()
    assert narrative_budget_exceeded(start) is False


def test_narrative_budget_exceeded_after_the_budget_window():
    start = time.monotonic() - (REQUEST_TIME_BUDGET_SECONDS + 1)
    assert narrative_budget_exceeded(start) is True


def test_narrative_budget_respects_custom_budget():
    start = time.monotonic() - 5
    assert narrative_budget_exceeded(start, budget=3.0) is True
    assert narrative_budget_exceeded(start, budget=10.0) is False
