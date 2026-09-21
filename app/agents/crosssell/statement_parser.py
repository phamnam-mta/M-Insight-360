import unicodedata
from dataclasses import dataclass

from app.extraction.types import ExtractedDocument, ExtractedTable


@dataclass(eq=True)
class Transaction:
    date: str
    entry_no: str
    debit: float
    credit: float
    description: str
    partner: str
    partner_account: str
    partner_bank: str
    currency: str
    source: str


# Different banks (and BTC's own MSB/MB/TPBank samples) don't all use MSB's exact
# HEADER_MAP header strings. Each entry lists observed/plausible spellings; this is
# an explicitly incomplete, best-effort list, not a schema guarantee — an unmapped
# required column still (correctly) drops that table rather than mis-mapping data.
_COLUMN_ALIASES: dict[str, list[str]] = {
    "date": ["ngay", "ngay gd", "ngay giao dich"],
    "entry_no": ["so but toan", "so bt", "so ct", "so chung tu"],
    "debit": ["ghi no", "no"],
    "credit": ["ghi co", "co"],
    "description": ["dien giai", "noi dung", "noi dung giao dich"],
    "partner": ["doi tac", "ten doi tac"],
    "partner_account": ["tai khoan doi tac", "tk doi tac"],
    "partner_bank": ["ngan hang doi tac", "nh doi tac"],
    "currency": ["loai tien"],
    "source": ["nguon"],
}
_REQUIRED_FOR_STATEMENT = {"date", "debit", "credit", "description"}


def _strip_accents_lower(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(c for c in normalized if not unicodedata.combining(c))
    return ascii_text.lower().strip()


def _map_header(header_row: list[str]) -> dict[str, int] | None:
    normalized = [_strip_accents_lower(h) for h in header_row]
    mapping: dict[str, int] = {}
    for field, aliases in _COLUMN_ALIASES.items():
        for i, cell in enumerate(normalized):
            if cell in aliases:
                mapping[field] = i
                break
    if not _REQUIRED_FOR_STATEMENT.issubset(mapping.keys()):
        return None
    return mapping


def _to_float(raw: str) -> float:
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
        # and a plain decimal point ("500000.5"). Bank-statement VND amounts
        # are whole numbers, so more than one dot, or a single dot followed
        # by exactly 3 digits, is treated as VN thousands grouping rather
        # than a fractional amount — this is the spec's own documented
        # domain (whole-VND statements), not a generic-number heuristic.
        parts = cleaned.split(".")
        if len(parts) > 2 or (len(parts) == 2 and len(parts[1]) == 3):
            cleaned = cleaned.replace(".", "")

    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def _parse_table(table: ExtractedTable) -> list[Transaction]:
    if not table.rows:
        return []
    mapping = _map_header(table.rows[0])
    if mapping is None:
        return []

    def cell(row: list[str], field: str) -> str:
        idx = mapping.get(field)
        if idx is None or idx >= len(row):
            return ""
        return row[idx] or ""

    transactions = []
    for row in table.rows[1:]:
        if not any(row):
            continue
        transactions.append(
            Transaction(
                date=cell(row, "date"),
                entry_no=cell(row, "entry_no"),
                debit=_to_float(cell(row, "debit")),
                credit=_to_float(cell(row, "credit")),
                description=cell(row, "description"),
                partner=cell(row, "partner"),
                partner_account=cell(row, "partner_account"),
                partner_bank=cell(row, "partner_bank"),
                currency=cell(row, "currency") or "VND",
                source=cell(row, "source"),
            )
        )
    return transactions


def parse_statement_documents(documents: list[ExtractedDocument]) -> list[Transaction]:
    transactions: list[Transaction] = []
    for doc in documents:
        for table in doc.tables:
            transactions.extend(_parse_table(table))
    return transactions
