from app.extraction.types import ExtractedDocument
from app.agents.rb.profile_checks import check_tax_id_consistency


def _doc(text: str) -> ExtractedDocument:
    return ExtractedDocument(
        filename="f.pdf", doc_type="pdf", text=text, tables=[],
        extraction_method="text_layer", confidence=1.0,
    )


def test_matching_tax_id_does_not_activate():
    docs = [_doc("MST: 0319998887, ten cong ty ABC")]
    result = check_tax_id_consistency("0319998887", docs)
    assert result.status == "KHÔNG KÍCH HOẠT"


def test_mismatched_tax_id_activates_and_never_says_fake(monkeypatch=None):
    # Hackathon's own worked example (spec §5 / §23): profile 0319998887 vs eTax 0319998897.
    docs = [_doc("KET QUA TRA CUU ETAX. Ma so thue: 0319998897")]
    result = check_tax_id_consistency("0319998887", docs)
    assert result.status == "KÍCH HOẠT"
    assert result.severity == "HIGH"
    assert "0319998887" in " ".join(result.evidence)
    assert "0319998897" in " ".join(result.evidence)
    assert "FAKE" not in result.comment.upper()
    assert "GIAN LẬN" not in result.comment.upper()
    assert "GIAN LAN" not in result.comment.upper()


def test_no_tax_id_found_is_not_evaluated():
    docs = [_doc("Khong co thong tin ve ma so thue trong tai lieu nay")]
    result = check_tax_id_consistency("0319998887", docs)
    assert result.status == "CHƯA ĐÁNH GIÁ"


def test_malformed_declared_tax_id_does_not_crash():
    docs = [_doc("MST: 0319998887")]
    result = check_tax_id_consistency("abc", docs)
    assert result.status in ("KHÔNG KÍCH HOẠT", "KÍCH HOẠT", "CHƯA ĐÁNH GIÁ")


def test_forbidden_words_never_appear_regardless_of_outcome():
    forbidden = ["FAKE", "GIAN LẬN", "GIAN LAN"]
    cases = [
        ("0319998887", [_doc("MST: 0319998887")]),
        ("0319998887", [_doc("Ma so thue: 0319998897")]),
        ("0319998887", [_doc("Khong co ma so thue")]),
        ("abc", [_doc("MST: 0319998887")]),
    ]
    for declared, docs in cases:
        result = check_tax_id_consistency(declared, docs)
        text = (result.comment or "").upper()
        for word in forbidden:
            assert word not in text
