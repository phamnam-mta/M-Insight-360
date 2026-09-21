from app.engine.core.types import Metric, RuleResult
from app.agents.rb.risk_flags import compute_risk_flags


def test_tax_id_mismatch_becomes_risk_flag():
    mandatory = {"required": [], "present": [], "missing": []}
    tax_id_result = RuleResult(
        rule_id="TAX_ID_MISMATCH", rule_name="x", status="KÍCH HOẠT", severity="HIGH",
        evidence=["a", "b"],
    )
    dti = Metric(metric="dti", value=0.2, formula="", input_values={}, input_sources={})
    flags = compute_risk_flags(mandatory, tax_id_result, dti)
    assert any(f.rule_id == "TAX_ID_MISMATCH" for f in flags)


def test_missing_mandatory_docs_becomes_risk_flag():
    mandatory = {"required": ["LEGAL_IDENTITY"], "present": [], "missing": ["LEGAL_IDENTITY"]}
    tax_id_result = RuleResult(rule_id="TAX_ID_MISMATCH", rule_name="x", status="CHƯA ĐÁNH GIÁ")
    dti = Metric.need_more_data("dti", "")
    flags = compute_risk_flags(mandatory, tax_id_result, dti)
    assert any(f.rule_id == "MISSING_MANDATORY_DOCUMENT" for f in flags)


def test_high_dti_becomes_risk_flag():
    mandatory = {"required": [], "present": [], "missing": []}
    tax_id_result = RuleResult(rule_id="TAX_ID_MISMATCH", rule_name="x", status="KHÔNG KÍCH HOẠT")
    dti = Metric(metric="dti", value=0.65, formula="", input_values={}, input_sources={})
    flags = compute_risk_flags(mandatory, tax_id_result, dti)
    assert any(f.rule_id == "HIGH_DTI" for f in flags)


def test_clean_case_has_no_flags():
    mandatory = {"required": [], "present": [], "missing": []}
    tax_id_result = RuleResult(rule_id="TAX_ID_MISMATCH", rule_name="x", status="KHÔNG KÍCH HOẠT")
    dti = Metric(metric="dti", value=0.2262, formula="", input_values={}, input_sources={})
    flags = compute_risk_flags(mandatory, tax_id_result, dti)
    assert flags == []


def test_flags_never_contain_forbidden_words():
    mandatory = {"required": ["LEGAL_IDENTITY"], "present": [], "missing": ["LEGAL_IDENTITY"]}
    tax_id_result = RuleResult(
        rule_id="TAX_ID_MISMATCH", rule_name="x", status="KÍCH HOẠT", severity="HIGH",
        evidence=["a", "b"], comment="cần xác minh thủ công",
    )
    dti = Metric(metric="dti", value=0.65, formula="", input_values={}, input_sources={})
    flags = compute_risk_flags(mandatory, tax_id_result, dti)
    for flag in flags:
        blob = f"{flag.comment} {flag.rule_name}".upper()
        assert "FAKE" not in blob
        assert "GIAN LẬN" not in blob
        assert "GIAN LAN" not in blob


def test_unclassified_document_forces_manual_review():
    # RB plan Global Constraint / spec §5: a document whose classification
    # confidence is below threshold becomes UNCLASSIFIED and flags the case for
    # MANUAL_REVIEW_REQUIRED — "never silently dropped". Nothing looked at
    # classification confidence at all before.
    mandatory = {"required": [], "present": [], "missing": []}
    tax_id_result = RuleResult(rule_id="TAX_ID_MISMATCH", rule_name="x", status="KHÔNG KÍCH HOẠT")
    dti = Metric(metric="dti", value=0.2, formula="", input_values={}, input_sources={})
    flags = compute_risk_flags(
        mandatory, tax_id_result, dti,
        classified_documents=[("la_gi_do.pdf", "UNCLASSIFIED", 0.0), ("cccd.pdf", "LEGAL_IDENTITY", 1.0)],
    )
    flag = next(f for f in flags if f.rule_id == "UNCLASSIFIED_DOCUMENT")
    assert flag.severity == "HIGH"  # -> determine_readiness returns MANUAL_REVIEW_REQUIRED
    assert any("la_gi_do.pdf" in e for e in flag.evidence)
    assert not any("cccd.pdf" in e for e in flag.evidence)


def test_no_unclassified_document_flag_when_all_documents_are_classified():
    mandatory = {"required": [], "present": [], "missing": []}
    tax_id_result = RuleResult(rule_id="TAX_ID_MISMATCH", rule_name="x", status="KHÔNG KÍCH HOẠT")
    dti = Metric(metric="dti", value=0.2, formula="", input_values={}, input_sources={})
    flags = compute_risk_flags(
        mandatory, tax_id_result, dti, classified_documents=[("cccd.pdf", "LEGAL_IDENTITY", 1.0)]
    )
    assert not any(f.rule_id == "UNCLASSIFIED_DOCUMENT" for f in flags)
