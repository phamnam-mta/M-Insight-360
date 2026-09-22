import time

# GreenNode's AgentBase Runtime gateway sits in front of this container and
# has its own hard request timeout (observed empirically at ~58-65s; not
# configurable via runtime.sh) that this app cannot extend. The narrative
# LLM call is the one non-essential step in each agent's pipeline — the
# deterministic numbers/red-flags are what matters for a credit decision —
# so it is skipped rather than risking a 502 that would throw away already-
# computed, correct results along with it. Budget is kept well under the
# observed ceiling to leave room for the narrative call's own timeout
# (narrative.py's httpx client) plus response-serialization overhead.
REQUEST_TIME_BUDGET_SECONDS = 30.0


def narrative_budget_exceeded(start_time: float, budget: float = REQUEST_TIME_BUDGET_SECONDS) -> bool:
    return (time.monotonic() - start_time) > budget
