"""Minimal, self-contained mandatory-document presence check for Agent EB.

Deviation from the plan: the plan's Task 10 imports
``app.agents.rb.document_classifier.classify_document`` and reuses it. That
module does not exist in this isolated worktree (Agent RB is being built
concurrently, in its own worktree, and this worktree must not read or write
anything under ``app/agents/rb/``). Rather than take a hard import
dependency on a sibling agent's not-yet-merged module — which would make
this worktree's test suite fail to even collect — EB gets its own small,
keyword-based classifier sufficient for its own mandatory-document check
(spec §6 step 1 "Kiểm kê & định danh hồ sơ"). This does not duplicate RB's
full document taxonomy; it only distinguishes the handful of categories EB's
mandatory check needs. If/when this is merged alongside Agent RB, the two
implementations can be reconciled by the controller.
"""

import re
import unicodedata

from app.extraction.types import ExtractedDocument

LEGAL_IDENTITY = "LEGAL_IDENTITY"
FINANCIAL_STATEMENT = "FINANCIAL_STATEMENT"
LOAN_REQUEST = "LOAN_REQUEST"
UNCLASSIFIED = "UNCLASSIFIED"

MANDATORY_DOC_TYPES = [LEGAL_IDENTITY, FINANCIAL_STATEMENT, LOAN_REQUEST]

_KEYWORDS: dict[str, list[str]] = {
    LEGAL_IDENTITY: [
        "giay chung nhan dang ky doanh nghiep",
        "dang ky kinh doanh",
        "giay phep kinh doanh",
        "can cuoc cong dan",
        "chung minh nhan dan",
        "ma so thue",
    ],
    FINANCIAL_STATEMENT: [
        "bao cao tai chinh",
        "bang can doi ke toan",
        "von chu so huu",
        "tai san ngan han",
        "luu chuyen tien thuan",
        "ket qua hoat dong kinh doanh",
    ],
    LOAN_REQUEST: [
        "de nghi vay von",
        "giay de nghi cap tin dung",
        "ho so vay von",
        "de xuat cap tin dung",
        "phuong an vay",
    ],
}


def _strip_accents_lower(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(c for c in normalized if not unicodedata.combining(c))
    return ascii_text.lower()


def classify_document_for_eb(document: ExtractedDocument) -> tuple[str, float]:
    """Return (doc_type, confidence) for EB's mandatory-document check only.

    Not a general-purpose document classifier — see module docstring.
    """
    haystack = _strip_accents_lower(f"{document.filename}\n{document.text}")
    for doc_type, keywords in _KEYWORDS.items():
        for keyword in keywords:
            if re.search(re.escape(keyword), haystack):
                return doc_type, 0.7
    return UNCLASSIFIED, 0.0
