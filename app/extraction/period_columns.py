"""Detects which BCTC table column belongs to which fiscal year.

Vietnamese BCTC tables show the current and prior year side by side, either
with an explicit date/year in the header ("31/12/2025") or a relative label
("So cuoi nam"/"So dau nam"). This resolves both forms against the
document's own detected primary reporting year so a value never gets
silently attributed to the wrong year.
"""

import re
import unicodedata

from .types import ExtractedDocument, ExtractedTable

_YEAR_RE = re.compile(r"\b(20\d{2})\b")
_CURRENT_LABELS = ("so cuoi nam", "cuoi ky", "cuoi nam", "nam nay", "ky nay")
_PRIOR_LABELS = ("so dau nam", "dau ky", "dau nam", "nam truoc", "ky truoc")


def _strip_accents_lower(text: str) -> str:
    # NFKD has no decomposition for Đ/đ (it isn't a base-letter-plus-
    # combining-mark in Unicode) — without this, "Số đầu năm" (the
    # standard, extremely common real BCTC prior-year header) never
    # reduces to "so dau nam" and the prior-year column goes unrecognized.
    text = text.replace("Đ", "D").replace("đ", "d")
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(c for c in normalized if not unicodedata.combining(c)).lower()


def detect_document_primary_year(doc: ExtractedDocument) -> int | None:
    haystacks = [doc.text] if doc.text else []
    haystacks.extend(" ".join(row) for table in doc.tables for row in table.rows[:1])
    years: list[int] = []
    for text in haystacks:
        years.extend(int(y) for y in _YEAR_RE.findall(text))
    return max(years) if years else None


def detect_table_primary_year(table: ExtractedTable) -> int | None:
    """Same signal search as detect_document_primary_year, but scoped to a
    single table's own rows — an upload can bundle a BCTC sheet together
    with an unrelated sheet (e.g. a bank-statement "sao ke" with hundreds
    of transaction dates); scanning the whole document's text for that
    BCTC sheet's year would let the other sheet's dates swamp max() and
    misdetect the BCTC's own fiscal year."""
    text = " ".join(" ".join(row) for row in table.rows)
    years = [int(y) for y in _YEAR_RE.findall(text)]
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
