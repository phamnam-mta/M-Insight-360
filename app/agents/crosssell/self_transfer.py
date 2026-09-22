"""Detects the customer's own self-transfer transactions.

Spec §"Nhận diện giao dịch tự chuyển": the previous version hard-coded one
customer's name into the regex, so it silently stopped working for every
other customer. The regex must be built at call time from the tax id's own
company name instead, and must exclude "LIEN DANH" joint-venture partners —
`'PHUC ANH' in blob` really did match a genuine ~6.4B VND partner named
"LIÊN DANH NHÀ THẦU PHÚC ANH – PHƯƠNG ĐÔNG".
"""

import re
import unicodedata

_STOPWORDS = {
    "CONG", "TY", "CO", "PHAN", "TNHH", "MTV", "JSC", "CP", "CTY", "LTD",
    "DAU", "TU", "GROUP",
}


def _strip_accents_upper(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(c for c in normalized if not unicodedata.combining(c))
    return ascii_text.upper()


def build_self_transfer_pattern(customer_name: str) -> re.Pattern | None:
    normalized = _strip_accents_upper(customer_name)
    core_words = [
        w for w in re.findall(r"[A-Z0-9]+", normalized)
        if w not in _STOPWORDS and len(w) > 1
    ]
    if not core_words:
        return None
    return re.compile(r"\b" + r"\W{0,10}".join(core_words) + r"\b")


def is_self_transfer(
    text: str,
    pattern: re.Pattern | None,
    self_accounts: list[str] | None = None,
) -> bool:
    blob = _strip_accents_upper(text)
    if self_accounts:
        if any(acct and acct in blob for acct in self_accounts):
            return True
    if pattern is None:
        return False
    return bool(pattern.search(blob)) and "LIEN DANH" not in blob
