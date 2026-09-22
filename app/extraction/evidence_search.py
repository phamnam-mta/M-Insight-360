import re
import unicodedata

from app.engine.core.numbers import parse_vn_number
from app.engine.core.types import EvidenceRef

from .period_columns import detect_document_primary_year, detect_year_columns
from .types import ExtractedDocument


def _strip_accents_lower(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(c for c in normalized if not unicodedata.combining(c))
    return ascii_text.lower()


def _extract_value(original: str, stripped_match: re.Match) -> str:
    # NFKD-decompose-and-strip is character-count-preserving for standard
    # Vietnamese text (every character maps to exactly one base character,
    # combining marks aside), so a match span found in the accent-stripped
    # haystack indexes correctly into the ORIGINAL string too. Slicing the
    # original here (instead of returning stripped_match.group(1)) recovers
    # proper Vietnamese diacritics/casing for free-text captures like an
    # industry name — numeric captures are unaffected either way.
    start, end = stripped_match.span(1) if stripped_match.groups() else stripped_match.span(0)
    return original[start:end]


def find_all_matches(
    documents: list[ExtractedDocument], pattern: re.Pattern
) -> list[tuple[EvidenceRef, str]]:
    results: list[tuple[EvidenceRef, str]] = []
    for doc in documents:
        file_id = getattr(doc, "file_id", doc.filename)
        pages = getattr(doc, "pages", None)
        if pages:
            for i, page_text in enumerate(pages):
                haystack = _strip_accents_lower(page_text)
                match = pattern.search(haystack)
                if match:
                    line = next(
                        (l for l in page_text.splitlines() if pattern.search(_strip_accents_lower(l))),
                        page_text,
                    )
                    results.append((
                        EvidenceRef(
                            file_id=file_id, filename=doc.filename,
                            location=f"Trang {i + 1}", original_text=line.strip(),
                        ),
                        _extract_value(page_text, match),
                    ))
            continue

        if doc.tables:
            for table in doc.tables:
                for row_idx, row in enumerate(table.rows):
                    joined = " | ".join(row)
                    # Field patterns are written colon-style ("...[:\s]*(...)")
                    # to match prose like "Von chu so huu: 9.000.000.000", but
                    # the far more common spreadsheet layout has the label and
                    # value in separate cells, joined here with " | " — a bare
                    # "|" satisfies neither ":" nor "\s", so the standard
                    # two-column layout would otherwise never match any field
                    # pattern. Replacing "|" with a space (1-for-1, so match
                    # spans still index correctly into the original `joined`
                    # string below) makes the join transparent to those
                    # patterns without having to rewrite every one of them.
                    haystack = _strip_accents_lower(joined).replace("|", " ")
                    match = pattern.search(haystack)
                    if match:
                        results.append((
                            EvidenceRef(
                                file_id=file_id, filename=doc.filename,
                                location=f"Sheet '{table.sheet_or_page}', dòng {row_idx + 1}",
                                original_text=joined,
                            ),
                            _extract_value(joined, match),
                        ))
            # xlsx/csv build doc.text from the exact same rows as doc.tables
            # (see xlsx_csv_parser.py), so falling through to search doc.text
            # there would only double-count every match already found above.
            # docx tables, though, are Word tables extracted separately from
            # the document's paragraph text (see docx_parser.py) — the two
            # are disjoint, so a field written as plain narrative text (very
            # common in real BCTC docx uploads) must still be searched, or it
            # is silently missed even though the document plainly contains it.
            if doc.doc_type != "docx":
                continue

        if doc.text:
            haystack = _strip_accents_lower(doc.text)
            match = pattern.search(haystack)
            if match:
                line = next(
                    (l for l in doc.text.splitlines() if pattern.search(_strip_accents_lower(l))),
                    doc.text,
                )
                results.append((
                    EvidenceRef(
                        file_id=file_id, filename=doc.filename,
                        location="Toàn văn bản", original_text=line.strip(),
                    ),
                    _extract_value(doc.text, match),
                ))
    return results


def find_all_matches_by_period(
    documents: list[ExtractedDocument], pattern: re.Pattern
) -> list[tuple[EvidenceRef, str, str, str]]:
    """Like find_all_matches, but for each matching TABLE row it extracts
    every numeric cell (not just the first capture) and tags each one with
    its fiscal year, resolved from the table's header row. Non-tabular
    matches (plain paragraph text) keep single-value behavior, tagged to
    the document's detected primary year with confidence "suy_doan" —
    real BCTC figures are overwhelmingly tabular, so multi-column fidelity
    concentrates where it matters instead of guessing at prose structure.
    """
    results: list[tuple[EvidenceRef, str, str, str]] = []
    for doc in documents:
        file_id = getattr(doc, "file_id", doc.filename)
        primary_year = detect_document_primary_year(doc)

        matched_in_tables = False
        for table in doc.tables:
            if not table.rows:
                continue
            year_columns = detect_year_columns(table.rows[0], primary_year)
            for row_idx, row in enumerate(table.rows[1:], start=1):
                joined = " | ".join(row)
                haystack = _strip_accents_lower(joined).replace("|", " ")
                if not pattern.search(haystack):
                    continue
                matched_in_tables = True
                if year_columns:
                    for col_idx, cell in enumerate(row):
                        if col_idx not in year_columns:
                            continue
                        if not cell or (parse_vn_number(cell) == 0.0 and not any(ch.isdigit() for ch in cell)):
                            continue
                        results.append((
                            EvidenceRef(
                                file_id=file_id, filename=doc.filename,
                                location=f"Sheet '{table.sheet_or_page}', dòng {row_idx + 1}",
                                original_text=joined, period=year_columns[col_idx],
                            ),
                            cell, year_columns[col_idx], "explicit",
                        ))
                else:
                    # No year signal in this table's header at all — keep the
                    # first captured value as a single best-effort guess
                    # rather than silently discarding a real match.
                    match = pattern.search(haystack)
                    year = str(primary_year) if primary_year else "khong_xac_dinh"
                    results.append((
                        EvidenceRef(
                            file_id=file_id, filename=doc.filename,
                            location=f"Sheet '{table.sheet_or_page}', dòng {row_idx + 1}",
                            original_text=joined, period=year,
                        ),
                        _extract_value(joined, match), year, "suy_doan",
                    ))

        if not matched_in_tables and doc.text:
            haystack = _strip_accents_lower(doc.text)
            match = pattern.search(haystack)
            if match:
                line = next(
                    (l for l in doc.text.splitlines() if pattern.search(_strip_accents_lower(l))),
                    doc.text,
                )
                year = str(primary_year) if primary_year else "khong_xac_dinh"
                results.append((
                    EvidenceRef(
                        file_id=file_id, filename=doc.filename,
                        location="Toàn văn bản", original_text=line.strip(), period=year,
                    ),
                    _extract_value(doc.text, match), year, "suy_doan",
                ))
    return results
