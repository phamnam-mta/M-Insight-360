from app.extraction.types import ExtractedDocument
from app.agents.rb.document_classifier import classify_document, classify_document_types


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


def test_financial_statement_with_single_fs_keyword_is_not_outscored_by_tax_id_header():
    # A real BCTC's header routinely carries "Ma so thue"/"MST" as company
    # metadata - that must not make the document classify as TAX_DOCUMENT
    # instead of FINANCIAL_STATEMENT (a real bug: EB then reports the BCTC
    # it's holding as "missing").
    doc = _doc("Ma so thue: 0101234567\nBAO CAO TAI CHINH NAM 2024\nVon chu so huu: 5.000.000.000")
    doc_type, _ = classify_document(doc)
    assert doc_type == "FINANCIAL_STATEMENT"


def test_loan_request_with_tax_id_header_is_not_outscored_by_tax_id_header():
    doc = _doc("Ma so thue: 0101234567\nMST: 0101234567\nGIAY DE NGHI CAP TIN DUNG\nMuc dich vay von")
    doc_type, _ = classify_document(doc)
    assert doc_type == "LOAN_REQUEST"


def test_classify_document_types_returns_every_matching_category():
    # A single physical file can legitimately bundle a BCTC sheet with an
    # unrelated bank-statement sheet — both categories are genuinely
    # present and should both be reported, not just whichever has more
    # keyword hits.
    doc = _doc(
        "BAO CAO TAI CHINH NAM 2025\nBANG CAN DOI KE TOAN\nVon chu so huu: 500.000.000\n"
        + "\n".join("Ngay GD Ghi No Ghi Co So Du" for _ in range(20))
    )
    types = {t for t, _ in classify_document_types(doc)}
    assert "FINANCIAL_STATEMENT" in types
    assert "BANK_STATEMENT" in types


def test_classify_document_types_excludes_low_confidence_categories():
    doc = _doc("BAO CAO TAI CHINH NAM 2025\nBANG CAN DOI KE TOAN\nVon chu so huu: 500.000.000")
    types = {t for t, _ in classify_document_types(doc)}
    assert types == {"FINANCIAL_STATEMENT"}
