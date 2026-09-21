import unicodedata

from .statement_parser import Transaction

_CASH_KEYWORDS = ["nop tien mat", "rut tien mat", "tien mat"]
_INTERBANK_KEYWORDS = ["chuyen khoan noi bo", "dieu chuyen noi bo", "chuyen tien noi bo"]


def _strip_accents_lower(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(c for c in normalized if not unicodedata.combining(c))
    return ascii_text.lower()


def _classify_one(txn: Transaction) -> str:
    desc = _strip_accents_lower(txn.description)
    if any(kw in desc for kw in _INTERBANK_KEYWORDS):
        return "interbank"
    if any(kw in desc for kw in _CASH_KEYWORDS):
        return "cash"
    return "direct"


def is_cash_transaction(txn: Transaction) -> bool:
    """True for cash deposits/withdrawals, shared with Rule 2's exclusions."""
    return _classify_one(txn) == "cash"


def classify_flows(transactions: list[Transaction]) -> dict:
    direct_inflow = cash_inflow = interbank_inflow = 0.0
    total_in = 0.0

    for txn in transactions:
        total_in += txn.credit
        category = _classify_one(txn)
        if category == "cash":
            cash_inflow += txn.credit
        elif category == "interbank":
            interbank_inflow += txn.credit
        else:
            direct_inflow += txn.credit

    operating_in = direct_inflow
    operating_in_pct = round(operating_in / total_in, 4) if total_in else 0.0

    return {
        "direct_inflow": direct_inflow,
        "cash_inflow": cash_inflow,
        "interbank_inflow": interbank_inflow,
        "operating_in": operating_in,
        "operating_in_pct": operating_in_pct,
    }
