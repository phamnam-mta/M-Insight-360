from app.extraction.types import ExtractedDocument

DOCUMENT_TYPES = [
    "LEGAL_IDENTITY", "BUSINESS_REGISTRATION", "TAX_DOCUMENT", "BANK_STATEMENT",
    "INCOME_DOCUMENT", "ECOMMERCE_REVENUE", "CIC_REPORT", "LOAN_REQUEST",
    "PURCHASE_CONTRACT", "SUPPLIER_INVOICE", "COLLATERAL_DOCUMENT",
    "FINANCIAL_STATEMENT", "BUSINESS_CONTRACT", "OTHER",
]

_KEYWORDS: dict[str, list[str]] = {
    "LEGAL_IDENTITY": ["cccd", "cmnd", "can cuoc cong dan", "chung minh nhan dan"],
    "BUSINESS_REGISTRATION": ["dang ky kinh doanh", "dkkd", "giay chung nhan dang ky doanh nghiep"],
    "TAX_DOCUMENT": ["to khai thue", "etax", "quyet toan thue"],
    "BANK_STATEMENT": ["sao ke", "statement", "ghi no", "ghi co", "so du"],
    "INCOME_DOCUMENT": ["bang luong", "sao ke luong", "thu nhap"],
    "ECOMMERCE_REVENUE": ["tiktok shop", "shopee", "doanh thu san"],
    "CIC_REPORT": ["cic", "trung tam thong tin tin dung"],
    "LOAN_REQUEST": ["de nghi cap tin dung", "de nghi vay", "phuong an vay", "muc dich vay"],
    "PURCHASE_CONTRACT": ["hop dong mua ban"],
    "SUPPLIER_INVOICE": ["hoa don", "invoice"],
    "COLLATERAL_DOCUMENT": ["tai san bao dam", "gcn qsdd", "quyen su dung dat"],
    "FINANCIAL_STATEMENT": ["bao cao tai chinh", "bctc", "bang can doi ke toan"],
    "BUSINESS_CONTRACT": ["hop dong kinh doanh", "hop dong thue"],
}


def _strip_accents_lower(text: str) -> str:
    import unicodedata

    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(c for c in normalized if not unicodedata.combining(c))
    return ascii_text.lower()


def classify_document(doc: ExtractedDocument) -> tuple[str, float]:
    haystack = _strip_accents_lower(doc.text + " " + doc.filename)
    best_type, best_score = "OTHER", 0
    for doc_type, keywords in _KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in haystack)
        if score > best_score:
            best_type, best_score = doc_type, score
    confidence = min(1.0, best_score / 2) if best_score > 0 else 0.0
    if confidence < 0.3:
        return "UNCLASSIFIED", confidence
    return best_type, confidence


def classify_document_types(doc: ExtractedDocument, min_confidence: float = 0.3) -> list[tuple[str, float]]:
    """Multi-label variant of classify_document: every doc_type whose own
    keyword score clears min_confidence, not just the single
    highest-scoring one. A real upload can legitimately bundle content for
    more than one category in one physical file (e.g. a BCTC sheet
    alongside a bank-statement sheet with hundreds of transaction rows,
    each repeating "ghi no"/"ghi co"/"so du") — classify_document's
    winner-take-all scoring would let the larger sheet's keyword count
    swamp the smaller one's and silently drop it from a mandatory-document
    presence check."""
    haystack = _strip_accents_lower(doc.text + " " + doc.filename)
    matched: list[tuple[str, float]] = []
    for doc_type, keywords in _KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in haystack)
        confidence = min(1.0, score / 2) if score > 0 else 0.0
        if confidence >= min_confidence:
            matched.append((doc_type, confidence))
    return matched
