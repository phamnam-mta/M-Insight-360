"""EB's mandatory-document presence check (spec §6 step 1 "Kiểm kê & định danh hồ sơ").

Classification itself is RB's — ``app.agents.rb.document_classifier.classify_document``
— exactly as the EB plan's Task 10 specifies. EB previously carried its own
keyword classifier because it was built in an isolated worktree that could not
read ``app/agents/rb/``; that constraint is gone now that both agents are
merged, and the duplicate was actively harmful: it returned on the *first*
keyword match in insertion order and listed "ma so thue" under LEGAL_IDENTITY,
so every Vietnamese business document (whose header carries a tax ID) — BCTCs
and loan requests included — came back as LEGAL_IDENTITY and EB reported the
documents it was holding as missing.

All this module still owns is EB's own mandatory-category list and the mapping
from RB's finer-grained document types onto those categories.
"""

from app.agents.rb.document_classifier import classify_document_types
from app.extraction.types import ExtractedDocument

LEGAL_IDENTITY = "LEGAL_IDENTITY"
FINANCIAL_STATEMENT = "FINANCIAL_STATEMENT"
LOAN_REQUEST = "LOAN_REQUEST"

MANDATORY_DOC_TYPES = [LEGAL_IDENTITY, FINANCIAL_STATEMENT, LOAN_REQUEST]

# RB's taxonomy is finer-grained than EB's three mandatory categories. An
# enterprise customer's "legal identity" is satisfied by the business
# registration certificate or the tax registration just as much as by a
# personal ID, so those three RB types all count towards LEGAL_IDENTITY.
_RB_TYPES_BY_EB_CATEGORY: dict[str, set[str]] = {
    LEGAL_IDENTITY: {"LEGAL_IDENTITY", "BUSINESS_REGISTRATION", "TAX_DOCUMENT"},
    FINANCIAL_STATEMENT: {"FINANCIAL_STATEMENT"},
    LOAN_REQUEST: {"LOAN_REQUEST"},
}


def classify_documents(documents: list[ExtractedDocument]) -> list[tuple[str, float]]:
    """Every (doc_type, confidence) pair present across the bundle, using
    RB's shared multi-label classifier — not one type per document. A
    single physical upload can legitimately bundle content for more than
    one category (e.g. a BCTC sheet alongside a bank-statement sheet with
    hundreds of transaction rows); EB only cares whether each mandatory
    category is present SOMEWHERE in the bundle, so a winner-take-all
    single label per document (RB's own classify_document, used for RB's
    own per-document display) would silently drop a real category whose
    keyword count lost out to a larger, unrelated sheet in the same file.
    """
    return [t for doc in documents for t in classify_document_types(doc)]


def find_missing_mandatory_types(documents: list[ExtractedDocument]) -> list[str]:
    """EB mandatory categories with no matching document in the bundle."""
    return missing_from_classified(classify_documents(documents))


def missing_from_classified(classified: list[tuple[str, float]]) -> list[str]:
    """Same as :func:`find_missing_mandatory_types` for already-classified docs."""
    present_rb_types = {doc_type for doc_type, _ in classified}
    return [
        category
        for category in MANDATORY_DOC_TYPES
        if not (_RB_TYPES_BY_EB_CATEGORY[category] & present_rb_types)
    ]
