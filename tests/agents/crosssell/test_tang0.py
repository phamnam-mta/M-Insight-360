from app.agents.crosssell.statement_parser import Transaction
from app.agents.crosssell.tang0 import dedup_transactions


def _txn(entry_no="1", date="01/01/2026", debit=0.0, credit=100.0, desc="thanh toan"):
    return Transaction(
        date=date, entry_no=entry_no, debit=debit, credit=credit, description=desc,
        partner="A", partner_account="", partner_bank="", currency="VND", source="",
    )


def test_exact_duplicate_rows_are_removed():
    t1 = _txn()
    t2 = _txn()  # identical on every dedup-key field
    result = dedup_transactions([t1, t2])
    assert result.raw_count == 2
    assert result.deduped_count == 1
    assert result.duplicate_count == 1


def test_same_entry_no_but_different_amounts_are_kept_distinct():
    # The real-world bug this guards against: a bank reuses one entry_no for
    # several sub-postings of a single instruction. Deduping on entry_no alone
    # would wrongly collapse these into one row.
    t1 = _txn(entry_no="BT1", credit=100.0)
    t2 = _txn(entry_no="BT1", credit=200.0)
    t3 = _txn(entry_no="BT1", debit=50.0, credit=0.0)
    result = dedup_transactions([t1, t2, t3])
    assert result.deduped_count == 3
    assert result.duplicate_count == 0
    assert result.unique_entry_no_count == 1  # fewer unique codes than rows is normal


def test_empty_input():
    result = dedup_transactions([])
    assert result.raw_count == 0
    assert result.deduped_count == 0
    assert result.transactions == []
