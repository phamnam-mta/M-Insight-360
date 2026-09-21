from app.engine.core.types import RuleResult
from app.agents.rb.readiness import determine_readiness

_NO_MISSING = {"required": [], "present": [], "missing": []}


def test_missing_docs_forces_additional_documents_required():
    mandatory = {"required": ["X"], "present": [], "missing": ["X"]}
    readiness, recommendation = determine_readiness(mandatory, [])
    assert readiness == "NOT_READY"
    assert recommendation == "ADDITIONAL_DOCUMENTS_REQUIRED"


def test_high_severity_flag_forces_manual_review():
    flags = [RuleResult(rule_id="TAX_ID_MISMATCH", rule_name="x", status="KÍCH HOẠT", severity="HIGH")]
    readiness, recommendation = determine_readiness(_NO_MISSING, flags)
    assert readiness == "MANUAL_REVIEW_REQUIRED"
    assert recommendation == "REQUIRES_CREDIT_OFFICER_REVIEW"


def test_low_severity_flags_allow_conditional_proceed():
    flags = [RuleResult(rule_id="LOW_OCR_CONFIDENCE", rule_name="x", status="KÍCH HOẠT", severity="LOW")]
    readiness, recommendation = determine_readiness(_NO_MISSING, flags)
    assert readiness == "READY_WITH_CONDITIONS"
    assert recommendation == "PROCEED_WITH_CONDITIONS"


def test_clean_case_is_ready():
    readiness, recommendation = determine_readiness(_NO_MISSING, [])
    assert readiness == "READY"
    assert recommendation == "PROCEED_FOR_HUMAN_REVIEW"


def test_recommendation_is_always_a_legal_value():
    legal = {"PROCEED_FOR_HUMAN_REVIEW", "PROCEED_WITH_CONDITIONS", "ADDITIONAL_DOCUMENTS_REQUIRED", "REQUIRES_CREDIT_OFFICER_REVIEW"}
    for mandatory, flags in [
        (_NO_MISSING, []),
        ({"required": ["X"], "present": [], "missing": ["X"]}, []),
        (_NO_MISSING, [RuleResult(rule_id="A", rule_name="a", status="KÍCH HOẠT", severity="HIGH")]),
        (_NO_MISSING, [RuleResult(rule_id="A", rule_name="a", status="KÍCH HOẠT", severity="LOW")]),
    ]:
        _, recommendation = determine_readiness(mandatory, flags)
        assert recommendation in legal


def test_readiness_is_always_a_legal_value():
    legal_readiness = {"READY", "READY_WITH_CONDITIONS", "NOT_READY", "MANUAL_REVIEW_REQUIRED"}
    for mandatory, flags in [
        (_NO_MISSING, []),
        ({"required": ["X"], "present": [], "missing": ["X"]}, []),
        (_NO_MISSING, [RuleResult(rule_id="A", rule_name="a", status="KÍCH HOẠT", severity="HIGH")]),
        (_NO_MISSING, [RuleResult(rule_id="A", rule_name="a", status="KÍCH HOẠT", severity="MEDIUM")]),
        (_NO_MISSING, [RuleResult(rule_id="A", rule_name="a", status="KÍCH HOẠT", severity="LOW")]),
    ]:
        readiness, _ = determine_readiness(mandatory, flags)
        assert readiness in legal_readiness
