from app.engine.core.types import RuleResult

from .statement_parser import Transaction

RULE2_MIN_TRANSACTIONS = 3
RULE2_MIN_VALUE_VND = 500_000_000


def rank_top_partners(transactions: list[Transaction]) -> list[dict]:
    by_partner: dict[str, dict] = {}
    for txn in transactions:
        if not txn.partner.strip():
            continue
        entry = by_partner.setdefault(
            txn.partner, {"partner": txn.partner, "transaction_count": 0, "total_value": 0.0}
        )
        entry["transaction_count"] += 1
        entry["total_value"] += txn.credit + txn.debit

    for entry in by_partner.values():
        entry["qualifies"] = (
            entry["transaction_count"] >= RULE2_MIN_TRANSACTIONS
            and entry["total_value"] >= RULE2_MIN_VALUE_VND
        )

    return sorted(
        by_partner.values(),
        key=lambda e: (-e["total_value"], -e["transaction_count"], e["partner"]),
    )


def evaluate_rule2_top_partners(transactions: list[Transaction]) -> RuleResult:
    ranked = rank_top_partners(transactions)
    qualifying = [p for p in ranked if p["qualifies"]]
    if not qualifying:
        return RuleResult(
            rule_id="RULE2_SCF", rule_name="Tài trợ chuỗi / Thanh toán (EB)", status="KHÔNG KÍCH HOẠT",
        )
    return RuleResult(
        rule_id="RULE2_SCF", rule_name="Tài trợ chuỗi / Thanh toán (EB)", status="KÍCH HOẠT",
        evidence=[
            f"{p['partner']}: {p['transaction_count']} GD, {p['total_value']:,.0f} VND" for p in qualifying[:5]
        ],
        threshold=f"quy tắc demo: ≥{RULE2_MIN_TRANSACTIONS} GD và ≥{RULE2_MIN_VALUE_VND:,.0f} VND",
        comment="Cơ hội SCF hoặc Bảo lãnh thanh toán (L/C) với các đối tác tần suất/giá trị cao.",
    )
