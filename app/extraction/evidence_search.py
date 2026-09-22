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
                    haystack = _strip_accents_lower(joined)
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
            continue

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
