from app.engine.core.types import RuleResult


def determine_readiness(
    mandatory_check: dict, risk_flags: list[RuleResult]
) -> tuple[str, str]:
    if mandatory_check["missing"]:
        return "NOT_READY", "ADDITIONAL_DOCUMENTS_REQUIRED"

    high_severity = [f for f in risk_flags if f.severity == "HIGH"]
    if high_severity:
        return "MANUAL_REVIEW_REQUIRED", "REQUIRES_CREDIT_OFFICER_REVIEW"

    if risk_flags:
        return "READY_WITH_CONDITIONS", "PROCEED_WITH_CONDITIONS"

    return "READY", "PROCEED_FOR_HUMAN_REVIEW"
