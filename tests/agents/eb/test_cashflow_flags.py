from app.agents.eb.financial_inputs import EbFinancialInputs
from app.agents.eb.cashflow_flags import evaluate_rf02_negative_cfo


def test_rf02_activates_on_negative_cfo():
    result = evaluate_rf02_negative_cfo(EbFinancialInputs(cfo_vnd=-1_188_000_000))
    assert result.status == "KÍCH HOẠT"
    assert result.severity == "HIGH"


def test_rf02_not_activated_on_positive_cfo():
    result = evaluate_rf02_negative_cfo(EbFinancialInputs(cfo_vnd=500_000_000))
    assert result.status == "KHÔNG KÍCH HOẠT"


def test_rf02_not_evaluated_when_cfo_missing():
    result = evaluate_rf02_negative_cfo(EbFinancialInputs())
    assert result.status == "CHƯA ĐÁNH GIÁ"


def test_rf02_carries_evidence_refs_when_field_evidence_provided():
    from app.agents.eb.financial_inputs import FieldEvidence
    from app.engine.core.types import EvidenceRef

    ref = EvidenceRef(file_id="f1", filename="bctc.pdf", location="Trang 1", original_text="CFO: -1.188.000.000")
    field_evidence = {"cfo_vnd": FieldEvidence(status="COMPUTED", evidence=[ref])}
    result = evaluate_rf02_negative_cfo(EbFinancialInputs(cfo_vnd=-1_188_000_000), field_evidence)
    assert result.evidence_refs["cfo_vnd"] == [ref]
