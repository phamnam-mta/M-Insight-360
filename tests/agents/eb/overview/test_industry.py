from app.agents.eb.overview.industry import evaluate_industry
from app.extraction.types import ExtractedDocument


def _doc(text: str):
    doc = ExtractedDocument(
        filename="dkkd.pdf", doc_type="pdf", text=text, tables=[],
        extraction_method="text_layer", confidence=1.0,
    )
    doc.file_id = "dkkd.pdf"
    doc.pages = [text]
    return doc


def test_insufficient_data_when_prohibited_list_not_loaded():
    row = evaluate_industry([_doc("Nganh nghe kinh doanh: Ban le hang tieu dung")])
    assert row.result == "INSUFFICIENT_DATA"
    assert row.observed.value == "Ban le hang tieu dung"
    assert row.observed.status == "COMPUTED"


def test_insufficient_data_without_any_industry_text():
    row = evaluate_industry([_doc("khong co thong tin nganh")])
    assert row.result == "INSUFFICIENT_DATA"
    assert row.observed.value is None


def test_fail_when_list_loaded_and_industry_matches(monkeypatch):
    from app.agents.eb import policy_config

    monkeypatch.setitem(
        policy_config.POLICY_CONFIG, "PROHIBITED_INDUSTRIES",
        policy_config.PolicyThreshold(["ca do", "vu khi"]),
    )
    row = evaluate_industry([_doc("Nganh nghe kinh doanh: Ca do truc tuyen")])
    assert row.result == "FAIL"


def test_pass_when_list_loaded_and_industry_does_not_match(monkeypatch):
    from app.agents.eb import policy_config

    monkeypatch.setitem(
        policy_config.POLICY_CONFIG, "PROHIBITED_INDUSTRIES",
        policy_config.PolicyThreshold(["ca do", "vu khi"]),
    )
    row = evaluate_industry([_doc("Nganh nghe kinh doanh: Ban le hang tieu dung")])
    assert row.result == "PASS"
