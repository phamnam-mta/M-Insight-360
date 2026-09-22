from app.engine.core.types import ConditionResult


def check_internal_system(system: str) -> ConditionResult:
    """Always PENDING_INTERNAL_CHECK today — no real CIF/CIC/DSP/AML
    connection exists. Swap this function's body, not its callers, when a
    real integration lands."""
    return "PENDING_INTERNAL_CHECK"
