from app.extraction.types import ExtractedDocument
from app.agents.rb.document_classifier import classify_document


def _doc(text: str, filename: str = "f.pdf") -> ExtractedDocument:
    return ExtractedDocument(
        filename=filename, doc_type="pdf", text=text, tables=[],
        extraction_method="text_layer", confidence=1.0,
    )


def test_classifies_bank_statement():
    doc = _doc("SAO KE TAI KHOAN\nNgay | Ghi No | Ghi Co | So Du\n01/01 | 0 | 500000 | 500000")
    doc_type, confidence = classify_document(doc)
    assert doc_type == "BANK_STATEMENT"
    assert confidence > 0


def test_classifies_legal_identity():
    doc = _doc("CAN CUOC CONG DAN\nHo va ten: NGUYEN VAN A\nSo CCCD: 001234567890")
    doc_type, _ = classify_document(doc)
    assert doc_type == "LEGAL_IDENTITY"


def test_classifies_loan_request():
    doc = _doc("GIAY DE NGHI CAP TIN DUNG\nSo tien de nghi vay: 450,000,000 VND\nMuc dich vay von")
    doc_type, _ = classify_document(doc)
    assert doc_type == "LOAN_REQUEST"


def test_unrelated_document_is_unclassified():
    doc = _doc("Thiep moi du tiec sinh nhat")
    doc_type, confidence = classify_document(doc)
    assert doc_type == "UNCLASSIFIED"
    assert confidence < 0.3
