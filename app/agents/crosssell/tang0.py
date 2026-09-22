"""Tầng 0 — chuẩn hoá đầu vào: khử trùng giao dịch bằng khoá ghép.

Spec (AGENT_CrossSell_INSTRUCTION v3.1) §Tầng 0.3: dedup by a single column
(entry_no) deletes real transactions when a bank reuses one entry code for
several sub-postings of one instruction — verified on a real case (924 rows,
only 768 unique entry codes). The composite key
(date, entry_no, debit, credit, description) is required instead.
"""

from dataclasses import dataclass

from .statement_parser import Transaction


@dataclass
class Tang0Result:
    raw_count: int
    deduped_count: int
    duplicate_count: int
    unique_entry_no_count: int
    transactions: list[Transaction]


def _dedup_key(t: Transaction) -> tuple:
    return (t.date, t.entry_no, t.debit, t.credit, t.description)


def dedup_transactions(transactions: list[Transaction]) -> Tang0Result:
    seen: set[tuple] = set()
    deduped: list[Transaction] = []
    for t in transactions:
        key = _dedup_key(t)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(t)

    unique_entry_no = {t.entry_no for t in deduped if t.entry_no}

    return Tang0Result(
        raw_count=len(transactions),
        deduped_count=len(deduped),
        duplicate_count=len(transactions) - len(deduped),
        unique_entry_no_count=len(unique_entry_no),
        transactions=deduped,
    )
