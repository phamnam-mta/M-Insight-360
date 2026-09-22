from app.agents.eb.overview.customer_status import evaluate_customer_segment, evaluate_operating_status
from app.extraction.types import ExtractedDocument


def _doc(text: str):
    doc = ExtractedDocument(
        filename="dkkd.pdf", doc_type="pdf", text=text, tables=[],
        extraction_method="text_layer", confidence=1.0,
    )
    doc.file_id = "dkkd.pdf"
    doc.pages = [text]
    return doc


def test_customer_segment_always_pending_internal_check():
    row = evaluate_customer_segment()
    assert row.result == "PENDING_INTERNAL_CHECK"
    assert row.observed.status == "MISSING_DATA"
    assert row.observed.value is None


def test_operating_status_pass_when_active_keyword_found():
    row = evaluate_operating_status([_doc("Tinh trang: dang hoat dong")])
    assert row.result == "PASS"
    assert row.observed.value == "dang hoat dong"


def test_operating_status_fail_when_dissolved_keyword_found():
    row = evaluate_operating_status([_doc("Tinh trang: da giai the")])
    assert row.result == "FAIL"


def test_operating_status_insufficient_data_when_not_stated():
    row = evaluate_operating_status([_doc("Khong co thong tin tinh trang")])
    assert row.result == "INSUFFICIENT_DATA"
