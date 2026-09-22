"""Detects which BCTC table column belongs to which fiscal year.

Vietnamese BCTC tables show the current and prior year side by side, either
with an explicit date/year in the header ("31/12/2025") or a relative label
("So cuoi nam"/"So dau nam"). This resolves both forms against the
document's own detected primary reporting year so a value never gets
silently attributed to the wrong year.
"""

import re
import unicodedata

from .types import ExtractedDocument

_YEAR_RE = re.compile(r"\b(20\d{2})\b")
_CURRENT_LABELS = ("so cuoi nam", "cuoi ky", "cuoi nam", "nam nay")
_PRIOR_LABELS = ("so dau nam", "dau ky", "dau nam", "nam truoc")


def _strip_accents_lower(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(c for c in normalized if not unicodedata.combining(c)).lower()


def detect_document_primary_year(doc: ExtractedDocument) -> int | None:
    haystacks = [doc.text] if doc.text else []
    haystacks.extend(" ".join(row) for table in doc.tables for row in table.rows[:1])
    years: list[int] = []
    for text in haystacks:
        years.extend(int(y) for y in _YEAR_RE.findall(text))
    return max(years) if years else None


def detect_year_columns(header_row: list[str], primary_year: int | None) -> dict[int, str]:
    mapping: dict[int, str] = {}
    for i, cell in enumerate(header_row):
        stripped = _strip_accents_lower(cell)
        explicit = _YEAR_RE.findall(cell)
        if explicit:
            mapping[i] = explicit[0]
            continue
        if primary_year is None:
            continue
        if any(label in stripped for label in _CURRENT_LABELS):
            mapping[i] = str(primary_year)
        elif any(label in stripped for label in _PRIOR_LABELS):
            mapping[i] = str(primary_year - 1)
    return mapping
