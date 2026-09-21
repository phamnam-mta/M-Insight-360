"""Locale-aware numeric parsing shared by all three agents.

Vietnamese documents write amounts as "500.000.000" ("." = thousands
separator, "," = decimal separator), but the same corpus also contains
US-style "1,234,567.89" (exported spreadsheets, bank portals). Every agent
reads the same bundles, so they must agree on how to read a number — this
module is the single implementation. It was extracted from Cross-sell's
statement parser, which was the only place that got it right.
"""


def parse_vn_number(raw: str) -> float:
    """Parse a VN- or US-formatted number; return 0.0 if unparseable.

    "500.000.000" -> 5e8, "1.234.567,89" -> 1234567.89,
    "1,234,567.89" -> 1234567.89, "1234,56" -> 1234.56, "22.5" -> 22.5
    """
    if not raw:
        return 0.0
    cleaned = raw.strip()
    if not cleaned:
        return 0.0

    has_comma = "," in cleaned
    has_dot = "." in cleaned

    if has_comma and has_dot:
        if cleaned.rfind(",") > cleaned.rfind("."):
            # e.g. "1.234.567,89" — VN/EU style: "." thousands, "," decimal.
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            # e.g. "1,234,567.89" — US style: "," thousands, "." decimal.
            cleaned = cleaned.replace(",", "")
    elif has_comma:
        # Only commas: ambiguous between US thousands ("1,234,567") and a VN
        # decimal comma ("1234,56"). A single comma followed by 1-2 digits
        # reads as a decimal; anything else is treated as thousands grouping.
        parts = cleaned.split(",")
        if len(parts) == 2 and 1 <= len(parts[1]) <= 2:
            cleaned = cleaned.replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif has_dot:
        # Only dots: ambiguous between VN thousands grouping ("500.000.000")
        # and a plain decimal point ("500000.5"). VND amounts in this domain
        # are whole numbers, so more than one dot, or a single dot followed
        # by exactly 3 digits, is treated as VN thousands grouping rather
        # than a fractional amount — this is the spec's own documented
        # domain (whole-VND figures), not a generic-number heuristic.
        parts = cleaned.split(".")
        if len(parts) > 2 or (len(parts) == 2 and len(parts[1]) == 3):
            cleaned = cleaned.replace(".", "")

    try:
        return float(cleaned)
    except ValueError:
        return 0.0
