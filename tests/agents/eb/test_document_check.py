from app.agents.eb.document_check import MANDATORY_DOC_TYPES, find_missing_mandatory_types
from app.extraction.types import ExtractedDocument


def _doc(filename: str, text: str) -> ExtractedDocument:
    return ExtractedDocument(
        filename=filename, doc_type="pdf", text=text, tables=[],
        extraction_method="text_layer", confidence=1.0,
    )


# Every Vietnamese business document carries "Mã số thuế" in its header. EB's
# own classifier returned on the first keyword match in insertion order and
# LEGAL_IDENTITY listed "ma so thue" first, so a real BCTC + loan-request
# bundle came back as all-LEGAL_IDENTITY and EB reported the BCTC missing
# while holding it.
_BCTC = _doc(
    "bctc_2024.pdf",
    "CONG TY TNHH ABC - Ma so thue: 0319998887\n"
    "BAO CAO TAI CHINH NAM 2024\n"
    "BANG CAN DOI KE TOAN\n"
    "Von chu so huu: 5.000.000.000\n"
    "Tai san ngan han: 3.500.000.000\n",
)
_LOAN_REQUEST = _doc(
    "de_nghi_vay.pdf",
    "CONG TY TNHH ABC - Ma so thue: 0319998887\n"
    "GIAY DE NGHI CAP TIN DUNG\n"
    "Muc dich vay: bo sung von luu dong\n"
    "So tien de nghi vay: 5.000.000.000 VND\n",
)
_DKKD = _doc(
    "dkkd.pdf",
    "GIAY CHUNG NHAN DANG KY DOANH NGHIEP\n"
    "Dang ky kinh doanh lan dau ngay 01/01/2020 - Ma so thue: 0319998887\n",
)


def test_bctc_is_recognised_as_financial_statement_not_legal_identity():
    missing = find_missing_mandatory_types([_BCTC])
    assert "FINANCIAL_STATEMENT" not in missing


def test_full_bundle_has_no_missing_mandatory_types():
    missing = find_missing_mandatory_types([_DKKD, _BCTC, _LOAN_REQUEST])
    assert missing == []


def test_loan_request_is_recognised_despite_tax_id_header():
    missing = find_missing_mandatory_types([_LOAN_REQUEST])
    assert "LOAN_REQUEST" not in missing


def test_irrelevant_document_leaves_all_mandatory_types_missing():
    missing = find_missing_mandatory_types([_doc("x.csv", "khong co gi lien quan")])
    assert missing == MANDATORY_DOC_TYPES
