from app.agents.eb.canonical import build_canonical
from app.agents.eb.overview import evaluate_overview
from app.extraction.types import ExtractedDocument


def _doc(text: str, filename="doc.pdf"):
    doc = ExtractedDocument(
        filename=filename, doc_type="pdf", text=text, tables=[],
        extraction_method="text_layer", confidence=1.0,
    )
    doc.file_id = filename
    doc.pages = [text]
    return doc


def _canonical_fields(docs):
    canonical = build_canonical(docs)
    if not canonical.fields_by_year:
        return {}
    return next(iter(canonical.fields_by_year.values()))


def test_returns_eleven_condition_rows():
    docs = [_doc("khong co gi ca")]
    rows, summary = evaluate_overview(docs, _canonical_fields(docs))
    assert len(rows) == 11
    assert summary["total"] == 11


def test_summary_counts_pending_conditions_correctly():
    docs = [_doc("khong co gi ca")]
    rows, summary = evaluate_overview(docs, _canonical_fields(docs))
    assert summary["checked"] == 0
    assert summary["pending"] == 11


def test_summary_reflects_a_passing_condition():
    text = "Von chu so huu: 500.000.000\n"
    docs = [_doc(text)]
    rows, summary = evaluate_overview(docs, _canonical_fields(docs))
    equity_row = next(r for r in rows if r.condition_id == "C08")
    assert equity_row.result == "PASS"
    assert summary["passed"] >= 1
    assert summary["checked"] >= 1
