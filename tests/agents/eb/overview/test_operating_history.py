from datetime import date

from app.agents.eb.overview.operating_history import evaluate_operating_history
from app.extraction.types import ExtractedDocument


def _doc(text: str):
    doc = ExtractedDocument(
        filename="dkkd.pdf", doc_type="pdf", text=text, tables=[],
        extraction_method="text_layer", confidence=1.0,
    )
    doc.file_id = "dkkd.pdf"
    doc.pages = [text]
    return doc


def test_pass_when_operating_at_least_24_months():
    row = evaluate_operating_history([_doc("Ngay thanh lap: 01/01/2023")], today=date(2026, 1, 1))
    assert row.result == "PASS"
    assert row.observed.value == 36


def test_fail_when_operating_less_than_24_months():
    row = evaluate_operating_history([_doc("Ngay thanh lap: 01/01/2025")], today=date(2026, 1, 1))
    assert row.result == "FAIL"
    assert row.observed.value == 12


def test_insufficient_data_without_a_date():
    row = evaluate_operating_history([_doc("khong co ngay thanh lap")], today=date(2026, 1, 1))
    assert row.result == "INSUFFICIENT_DATA"


def test_insufficient_data_on_conflicting_dates():
    doc1 = _doc("Ngay thanh lap: 01/01/2020")
    doc2_text = "Ngay thanh lap: 01/01/2022"
    doc2 = ExtractedDocument(filename="b.pdf", doc_type="pdf", text=doc2_text, tables=[], extraction_method="text_layer", confidence=1.0)
    doc2.file_id = "b.pdf"
    doc2.pages = [doc2_text]
    row = evaluate_operating_history([doc1, doc2], today=date(2026, 1, 1))
    assert row.result == "INSUFFICIENT_DATA"
