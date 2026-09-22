import re
import unicodedata

from app.engine.core.types import EvidenceRef

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
