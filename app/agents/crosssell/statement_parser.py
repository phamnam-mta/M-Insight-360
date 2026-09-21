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


_COLUMN_ALIASES: dict[str, list[str]] = {
    "date": ["ngay"],
    "entry_no": ["so but toan", "so bt"],
    "debit": ["ghi no"],
    "credit": ["ghi co"],
    "description": ["dien giai"],
    "partner": ["doi tac"],
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
    cleaned = raw.replace(",", "").strip()
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
