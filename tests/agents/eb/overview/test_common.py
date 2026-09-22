import re

from app.agents.eb.overview._common import build_numeric_condition
from app.extraction.types import ExtractedDocument

PATTERN = re.compile(r"von chu so huu[:\s]*(-?[\d.,]+)")


def _doc(text: str, filename="bctc.pdf"):
    doc = ExtractedDocument(
        filename=filename, doc_type="pdf", text=text, tables=[],
        extraction_method="text_layer", confidence=1.0,
    )
    doc.file_id = filename
    doc.pages = [text]
    return doc


def test_pass_when_value_satisfies_rule():
    row = build_numeric_condition(
        "C08", "Vốn chủ sở hữu", "equity_vnd", [_doc("Von chu so huu: 500.000.000")],
        PATTERN, "> 0", lambda v: v > 0,
    )
    assert row.result == "PASS"
    assert row.observed.value == 500_000_000
    assert row.observed.status == "COMPUTED"
    assert len(row.observed.evidence) == 1


def test_fail_when_value_does_not_satisfy_rule():
    row = build_numeric_condition(
        "C08", "Vốn chủ sở hữu", "equity_vnd", [_doc("Von chu so huu: -100.000.000")],
        PATTERN, "> 0", lambda v: v > 0,
    )
    assert row.result == "FAIL"


def test_insufficient_data_when_no_match():
    row = build_numeric_condition(
        "C08", "Vốn chủ sở hữu", "equity_vnd", [_doc("khong co gi")],
        PATTERN, "> 0", lambda v: v > 0,
    )
    assert row.result == "INSUFFICIENT_DATA"
    assert row.observed.value is None
    assert row.reason_if_incomplete is not None


def test_insufficient_data_when_sources_conflict():
    docs = [_doc("Von chu so huu: 500.000.000", "a.pdf"), _doc("Von chu so huu: 900.000.000", "b.pdf")]
    row = build_numeric_condition("C08", "Vốn chủ sở hữu", "equity_vnd", docs, PATTERN, "> 0", lambda v: v > 0)
    assert row.result == "INSUFFICIENT_DATA"
    assert row.observed.value is None
    assert len(row.observed.evidence) == 2
