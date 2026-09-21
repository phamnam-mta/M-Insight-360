import re

from app.engine.core.types import RuleResult
from app.extraction.types import ExtractedDocument

# VN tax IDs are 10 digits, optionally with a 3-digit branch suffix
# ("0319998887" or "0319998887-001" / "0319998887001"). A bare \d{10} pattern
# would also match a VN phone number (also exactly 10 digits), an account
# number, an invoice number, etc. anywhere in a document, producing a false
# HIGH-severity TAX_ID_MISMATCH on any case that merely mentions one of those.
# So candidate numbers are only accepted near explicit tax-ID keyword context
# ("mã số thuế", "MST", "eTax", "số thuế").
_TAX_ID_CONTEXT_PATTERN = re.compile(
    r"(?:ma so thue|mst|etax|so thue)[^\d]{0,40}(\d{10}(?:-?\d{3})?)",
    re.IGNORECASE,
)
_VALID_TAX_ID_FORMAT = re.compile(r"^\d{10}(\d{3})?$")

# A bundle legitimately contains other companies' tax IDs: RB's own
# SUPPLIER_INVOICE and PURCHASE_CONTRACT types are *expected* to carry the
# counterparty's. Only a tax ID introduced by applicant-side wording is
# comparable to the declared one; one introduced by seller-side wording is a
# counterparty's and is ignored. A tax ID with no role wording near it is still
# treated as the applicant's (that is the hackathon's own eTax-lookup example),
# so this narrows the false positives it can rule out, not all of them.
_COUNTERPARTY_ROLE_MARKERS = (
    "don vi ban hang", "don vi ban", "ben ban", "nguoi ban", "don vi cung cap",
    "nha cung cap", "ben cho thue", "ben cho vay", "don vi thu huong",
)
_APPLICANT_ROLE_MARKERS = (
    "don vi mua hang", "don vi mua", "ben mua", "nguoi mua", "nguoi nop thue",
    "ben vay", "khach hang", "chu ho so",
)
# How far back to look for the role wording that introduces a tax ID.
_ROLE_CONTEXT_CHARS = 150


def _normalize(raw: str) -> str:
    return raw.replace("-", "").replace(" ", "").strip()


def _parent_tax_id(normalized: str) -> str:
    """The 10-digit parent of a 13-digit branch tax ID ("0319998887001")."""
    return normalized[:10] if len(normalized) == 13 else normalized


def _belongs_to_counterparty(haystack: str, match_start: int) -> bool:
    """True when the nearest preceding role wording is a seller-side one."""
    window = haystack[max(0, match_start - _ROLE_CONTEXT_CHARS):match_start]
    last_counterparty = max((window.rfind(m) for m in _COUNTERPARTY_ROLE_MARKERS), default=-1)
    last_applicant = max((window.rfind(m) for m in _APPLICANT_ROLE_MARKERS), default=-1)
    return last_counterparty > last_applicant


def _strip_accents_lower(text: str) -> str:
    import unicodedata

    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(c for c in normalized if not unicodedata.combining(c))
    return ascii_text.lower()


def check_tax_id_consistency(
    declared_tax_id: str, documents: list[ExtractedDocument]
) -> RuleResult:
    declared_normalized = _normalize(declared_tax_id or "")
    declared_is_well_formed = bool(_VALID_TAX_ID_FORMAT.match(declared_normalized))

    found_ids: set[str] = set()
    for doc in documents:
        haystack = _strip_accents_lower(doc.text)
        for match in _TAX_ID_CONTEXT_PATTERN.finditer(haystack):
            if _belongs_to_counterparty(haystack, match.start()):
                continue
            found_ids.add(_normalize(match.group(1)))

    if not found_ids:
        return RuleResult(
            rule_id="TAX_ID_MISMATCH",
            rule_name="Đối chiếu mã số thuế",
            status="CHƯA ĐÁNH GIÁ",
            comment="Không tìm thấy mã số thuế nào trong hồ sơ để đối chiếu.",
        )

    if not declared_is_well_formed:
        # Declared tax ID doesn't fit VN's 10/13-digit format — this is a weak,
        # low-confidence comparison, not something to raise/crash on.
        return RuleResult(
            rule_id="TAX_ID_MISMATCH",
            rule_name="Đối chiếu mã số thuế",
            status="CHƯA ĐÁNH GIÁ",
            comment=(
                "Mã số thuế khai báo không đúng định dạng 10/13 số theo quy định VN — "
                "không thể đối chiếu tin cậy, cần nhập lại hoặc xác minh thủ công."
            ),
            evidence=[f"MST khai báo trên form: {declared_tax_id}"],
        )

    # A branch tax ID ("0319998887-001") belongs to the declared entity
    # ("0319998887") — the same taxpayer, not a mismatch.
    declared_parent = _parent_tax_id(declared_normalized)
    mismatches = {
        found for found in found_ids if _parent_tax_id(found) != declared_parent
    }
    if mismatches:
        return RuleResult(
            rule_id="TAX_ID_MISMATCH",
            rule_name="Đối chiếu mã số thuế",
            status="KÍCH HOẠT",
            severity="HIGH",
            evidence=[
                f"MST khai báo trên form: {declared_tax_id}",
                f"MST tìm thấy trong hồ sơ: {', '.join(sorted(mismatches))}",
            ],
            comment=(
                "Mã số thuế trong hồ sơ không khớp với mã số thuế khai báo. "
                "Cần xác minh thủ công — không kết luận là chứng từ không hợp lệ."
            ),
            verification_question=(
                "Vui lòng xác nhận mã số thuế chính xác của khách hàng và giải thích "
                "sự khác biệt giữa mã số thuế khai báo và mã số thuế trong hồ sơ."
            ),
            recommended_action="Chuyển Credit Officer xác minh thủ công mã số thuế trước khi thẩm định tiếp.",
        )
    return RuleResult(
        rule_id="TAX_ID_MISMATCH",
        rule_name="Đối chiếu mã số thuế",
        status="KHÔNG KÍCH HOẠT",
    )
