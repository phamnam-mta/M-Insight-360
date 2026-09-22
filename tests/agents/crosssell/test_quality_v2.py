from app.agents.crosssell.quality_v2 import check_name_quality_v2
from app.agents.crosssell.statement_parser import Transaction


def _txn(partner=""):
    return Transaction(
        date="01/01/2026", entry_no="1", debit=0.0, credit=100.0, description="",
        partner=partner, partner_account="", partner_bank="", currency="VND", source="",
    )


def test_all_clean_names_pass():
    txns = [_txn("CONG TY TNHH ABC XYZ") for _ in range(10)]
    result = check_name_quality_v2(txns)
    assert result.verdict == "PASS"
    assert result.confidence_cap == "H"


def test_reports_numerator_and_denominator_for_every_metric():
    txns = [_txn("CONG TY TNHH ABC") for _ in range(5)] + [_txn("") for _ in range(5)]
    result = check_name_quality_v2(txns)
    empty = next(m for m in result.metrics if m.label == "Tên đối tác rỗng")
    assert empty.numerator == 5
    assert empty.denominator == 10
    assert "5/10" in empty.result_text


def test_high_empty_pct_triggers_warn():
    txns = [_txn("") for _ in range(4)] + [_txn("CONG TY TNHH ABC XYZ") for _ in range(6)]
    result = check_name_quality_v2(txns)
    assert result.verdict == "WARN"
    assert result.confidence_cap == "M"


def test_tk_prefix_is_not_a_truncated_fragment():
    txns = [_txn("TK XD TM HUY HUNG") for _ in range(5)]
    result = check_name_quality_v2(txns)
    truncated = next(m for m in result.metrics if m.label == "Tên cụt đầu")
    assert truncated.numerator == 0


def test_detects_truncated_name_fragment():
    txns = [_txn("PANY ABC XYZ") for _ in range(5)]
    result = check_name_quality_v2(txns)
    truncated = next(m for m in result.metrics if m.label == "Tên cụt đầu")
    assert truncated.numerator == 5
    assert result.verdict == "WARN"


def test_short_and_no_space_denominators_exclude_empty_names():
    txns = [_txn("") for _ in range(3)] + [_txn("ABCDEFGHIJ KL") for _ in range(7)]
    result = check_name_quality_v2(txns)
    short = next(m for m in result.metrics if m.label == "Tên < 8 ký tự")
    assert short.denominator == 7  # not 10 — empty names excluded from this ratio
