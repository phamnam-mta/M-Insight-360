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


def test_bundled_bctc_and_bank_statement_in_one_file_both_recognised():
    # Production bug: a single upload can legitimately bundle a BCTC sheet
    # together with an unrelated bank-statement ("sao ke") sheet — real
    # sao ke data runs to hundreds of transaction rows, each repeating
    # "ghi no"/"ghi co"/"so du" column headers, so a winner-take-all
    # classifier (highest total keyword count wins the WHOLE document)
    # lets the bank-statement keywords swamp the BCTC's own, and the
    # document gets classified as BANK_STATEMENT only — EB then reports
    # FINANCIAL_STATEMENT as missing even though the BCTC data is present
    # and was correctly extracted.
    bundled = _doc(
        "ho_so_demo.xlsx",
        "BAO CAO TAI CHINH NAM 2025\n"
        "BANG CAN DOI KE TOAN\n"
        "Von chu so huu: 580.965.107.518\n"
        "Tai san ngan han: 293.369.838.619\n"
        + "\n".join(f"Ngay GD Dien giai Ghi no Ghi co So du giao dich {i}" for i in range(1, 50)),
    )
    missing = find_missing_mandatory_types([bundled])
    assert "FINANCIAL_STATEMENT" not in missing
