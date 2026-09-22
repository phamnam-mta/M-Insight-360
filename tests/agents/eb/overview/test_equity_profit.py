from app.agents.eb.overview.equity_profit import (
    evaluate_equity, evaluate_gross_profit_less_interest, evaluate_lnst_pakd,
)
from app.extraction.types import ExtractedDocument


def _doc(text: str, filename="doc.pdf"):
    doc = ExtractedDocument(
        filename=filename, doc_type="pdf", text=text, tables=[],
        extraction_method="text_layer", confidence=1.0,
    )
    doc.file_id = filename
    doc.pages = [text]
    return doc


def test_equity_pass_when_positive():
    row = evaluate_equity([_doc("Von chu so huu: 500.000.000")])
    assert row.result == "PASS"


def test_equity_fail_when_non_positive():
    row = evaluate_equity([_doc("Von chu so huu: 0")])
    assert row.result == "FAIL"


def test_lnst_pakd_pass_when_positive():
    row = evaluate_lnst_pakd([_doc("LNST theo PAKD: 200.000.000")])
    assert row.result == "PASS"


def test_lnst_pakd_insufficient_without_match():
    row = evaluate_lnst_pakd([_doc("khong co gi")])
    assert row.result == "INSUFFICIENT_DATA"


def test_gross_profit_less_interest_computed_and_passes():
    doc = _doc("Loi nhuan gop: 1.000.000.000\nChi phi lai vay: 300.000.000")
    row = evaluate_gross_profit_less_interest([doc])
    assert row.result == "PASS"
    assert row.observed.value == 700_000_000
    assert row.observed.formula == "loi_nhuan_gop - chi_phi_lai_vay"


def test_gross_profit_less_interest_fails_when_negative():
    doc = _doc("Loi nhuan gop: 100.000.000\nChi phi lai vay: 300.000.000")
    row = evaluate_gross_profit_less_interest([doc])
    assert row.result == "FAIL"


def test_gross_profit_less_interest_insufficient_when_either_missing():
    row = evaluate_gross_profit_less_interest([_doc("Loi nhuan gop: 100.000.000")])
    assert row.result == "INSUFFICIENT_DATA"
    assert "lãi vay" in row.reason_if_incomplete
