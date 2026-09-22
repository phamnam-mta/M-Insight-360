from app.agents.eb.document_status import build_document_status_list
from app.engine.core.types import ConditionRow, EvidencedField, EvidenceRef, Metric
from app.extraction.types import ExtractedDocument


def _doc(filename, file_id):
    doc = ExtractedDocument(
        filename=filename, doc_type="pdf", text="x", tables=[],
        extraction_method="text_layer", confidence=1.0,
    )
    doc.file_id = file_id
    return doc


def test_extraction_failure_is_khong_doc_duoc():
    statuses = build_document_status_list(
        documents=[], extraction_warnings=["broken.jpg: không đọc được nội dung file (bad format)"],
        condition_rows=[], metrics={},
    )
    assert statuses[0]["filename"] == "broken.jpg"
    assert statuses[0]["status"] == "KHÔNG_ĐỌC_ĐƯỢC"


def test_file_cited_by_computed_evidence_is_da_trich_xuat():
    doc = _doc("bctc.pdf", "f1")
    ref = EvidenceRef(file_id="f1", filename="bctc.pdf", location="Trang 1", original_text="x")
    field_ = EvidencedField(
        field_id="equity_vnd", label="Vốn chủ sở hữu", value=1, unit="VND",
        period=None, status="COMPUTED", evidence=[ref],
    )
    row = ConditionRow(condition_id="C08", condition_name="Vốn chủ sở hữu", observed=field_, compare_rule="> 0", result="PASS")
    statuses = build_document_status_list([doc], [], [row], {})
    assert statuses[0]["status"] == "ĐÃ_TRÍCH_XUẤT"
    assert statuses[0]["cited_field_count"] == 1


def test_file_cited_only_by_pending_review_metric_is_cho_xac_minh():
    doc = _doc("bctc.pdf", "f1")
    ref = EvidenceRef(file_id="f1", filename="bctc.pdf", location="Trang 1", original_text="x")
    metric = Metric(
        metric="nwc", value=None, formula="a-b", input_values={}, input_sources={},
        evidence={"current_assets_vnd": [ref]},
    )
    statuses = build_document_status_list([doc], [], [], {"nwc": metric})
    assert statuses[0]["status"] in ("ĐÃ_TRÍCH_XUẤT", "CHỜ_XÁC_MINH")


def test_uncited_extracted_file_is_da_tai_len():
    doc = _doc("khac.pdf", "f2")
    statuses = build_document_status_list([doc], [], [], {})
    assert statuses[0]["status"] == "ĐÃ_TẢI_LÊN"
