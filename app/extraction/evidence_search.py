import re
import unicodedata

from app.engine.core.numbers import parse_vn_number
from app.engine.core.types import EvidenceRef

from .period_columns import detect_document_primary_year, detect_table_primary_year, detect_year_columns
from .types import ExtractedDocument


def _strip_accents_lower(text: str) -> str:
    # NFKD has no decomposition for Đ/đ — see period_columns.py's copy of
    # this same fix for why that matters for real BCTC headers.
    text = text.replace("Đ", "D").replace("đ", "d")
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(c for c in normalized if not unicodedata.combining(c))
    return ascii_text.lower()


def _is_stt_or_ma_so_like(raw: str) -> bool:
    """A bare 1-3 digit integer, with no thousands separators — the shape
    of a row-number (STT) or a BCTC "Mã số" code, never a real financial
    figure (those always run into the thousands at minimum)."""
    return bool(re.fullmatch(r"\d{1,3}", raw))


def _last_numeric_cell(row: list[str]) -> str | None:
    """The row's own value cell, skipped past any leading STT/Ma-so code
    columns. A normal 2-column "label | current | prior" row (no
    recognized year header) must still yield its FIRST value column, not
    its rightmost one (that would silently return the PRIOR year's figure
    instead of the current one) — but a leading STT/Ma-so column (T31: a
    row like ["10", "Doanh thu thuan", "10", "90105893754"]) must never be
    captured as the value either. Prefer the first cell that doesn't look
    like an STT/Ma-so code; only fall back to one that does when every
    numeric cell in the row looks that way."""
    numeric_cells = [c.strip() for c in row if c.strip() and re.fullmatch(r"-?[\d.,]+", c.strip())]
    if not numeric_cells:
        return None
    for cell in numeric_cells:
        if not _is_stt_or_ma_so_like(cell):
            return cell
    return numeric_cells[-1]


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
        # A document-wide fallback for tables that carry no date signal of
        # their own — never the primary source: a single upload can bundle
        # unrelated sheets (a BCTC table alongside a bank-statement "sao ke"
        # sheet whose hundreds of transaction dates would otherwise swamp a
        # document-wide max() and misdetect the BCTC's own fiscal year), so
        # each table's own year must come from its own rows first.
        doc_primary_year = detect_document_primary_year(doc)

        matched_in_tables = False
        for table in doc.tables:
            if not table.rows:
                continue
            primary_year = detect_table_primary_year(table)
            if primary_year is None:
                primary_year = doc_primary_year
            # The header isn't always row 0 — a real xlsx export often has a
            # title row ("BAO CAO TAI CHINH TOM TAT...") above the actual
            # "Chi tieu | So cuoi nam | So dau nam" header. Scan forward for
            # the first row that actually carries a year signal before
            # falling back to row 0's (possibly empty) mapping.
            header_idx = 0
            year_columns = detect_year_columns(table.rows[0], primary_year)
            if not year_columns:
                # Require at least 2 mapped columns (current + prior) to
                # accept a row found by scanning forward — a trailing
                # footnote like "Bao cao lap ngay 31/12/2025" maps only its
                # own single cell and is not a real header; accepting it
                # would silently exclude every real data row that comes
                # BEFORE it in the table.
                for idx, row in enumerate(table.rows):
                    candidate = detect_year_columns(row, primary_year)
                    if len(candidate) >= 2:
                        header_idx, year_columns = idx, candidate
                        break
            for row_idx, row in enumerate(table.rows[header_idx + 1:], start=header_idx + 1):
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
                    # rather than silently discarding a real match. Prefer
                    # the row's rightmost purely-numeric cell over the
                    # regex's own capture group — a leading STT/Ma-so column
                    # would otherwise be captured instead of the real figure
                    # (T31).
                    match = pattern.search(haystack)
                    value = _last_numeric_cell(row) or _extract_value(joined, match)
                    year = str(primary_year) if primary_year else "khong_xac_dinh"
                    results.append((
                        EvidenceRef(
                            file_id=file_id, filename=doc.filename,
                            location=f"Sheet '{table.sheet_or_page}', dòng {row_idx + 1}",
                            original_text=joined, period=year,
                        ),
                        value, year, "suy_doan",
                    ))

        if not matched_in_tables and doc.text:
            haystack = _strip_accents_lower(doc.text)
            match = pattern.search(haystack)
            if match:
                line = next(
                    (l for l in doc.text.splitlines() if pattern.search(_strip_accents_lower(l))),
                    doc.text,
                )
                year = str(doc_primary_year) if doc_primary_year else "khong_xac_dinh"
                results.append((
                    EvidenceRef(
                        file_id=file_id, filename=doc.filename,
                        location="Toàn văn bản", original_text=line.strip(), period=year,
                    ),
                    _extract_value(doc.text, match), year, "suy_doan",
                ))
    return results
