from collections import OrderedDict

from .statement_parser import Transaction


def _month_key(date_str: str) -> str:
    parts = date_str.strip().split("/")
    if len(parts) != 3:
        return "KHÔNG XÁC ĐỊNH"
    _, month, year = parts
    if not (month.isdigit() and year.isdigit()):
        return "KHÔNG XÁC ĐỊNH"
    return f"{int(month):02d}/{year}"


def build_monthly_dashboard(transactions: list[Transaction]) -> list[dict]:
    grouped: "OrderedDict[str, dict]" = OrderedDict()
    for txn in transactions:
        key = _month_key(txn.date)
        row = grouped.setdefault(
            key, {"month": key, "transaction_count": 0, "total_in": 0.0, "total_out": 0.0, "net": 0.0}
        )
        row["transaction_count"] += 1
        row["total_in"] += txn.credit
        row["total_out"] += txn.debit
        row["net"] = row["total_in"] - row["total_out"]

    def sort_key(month: str):
        if month == "KHÔNG XÁC ĐỊNH":
            return (9999, 99)
        m, y = month.split("/")
        return (int(y), int(m))

    return [grouped[k] for k in sorted(grouped.keys(), key=sort_key)]
