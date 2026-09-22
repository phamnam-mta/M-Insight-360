from app.agents.crosssell.precheck_v2 import run_precheck_v2
from app.agents.crosssell.statement_parser import Transaction


def _txn(date="01/01/2026", debit=0.0, credit=100.0, balance=None):
    return Transaction(
        date=date, entry_no="1", debit=debit, credit=credit, description="",
        partner="", partner_account="", partner_bank="", currency="VND", source="",
        balance=balance,
    )


def test_pass_with_real_balance_column_is_independent():
    txns = [_txn(balance=8_500_000_000.0)]
    result = run_precheck_v2(txns, documents_have_simulated_marker=False, opening_balance=8_499_999_900.0, closing_balance=8_500_000_000.0)
    assert result.verdict == "PASS"
    assert result.balance_source == "doc_tu_sao_ke"
    assert result.confidence_cap == "H"


def test_pass_with_simulated_balance_marker_is_not_independent():
    txns = [_txn(balance=107_515_481_688.0)]
    result = run_precheck_v2(
        txns, documents_have_simulated_marker=True,
        opening_balance=0.0, closing_balance=100.0,
    )
    assert result.verdict == "PASS (khong doi chieu doc lap duoc)"
    assert result.balance_source == "suy_ra_mo_phong"
    assert result.confidence_cap == "M"
    assert "mo phong" in result.reason.lower() or "mô phỏng" in result.reason


def test_warn_when_no_balance_figures_supplied():
    result = run_precheck_v2([_txn()], documents_have_simulated_marker=False)
    assert result.verdict == "WARN"
    assert result.confidence_cap == "M"


def test_block_on_real_imbalance():
    txns = [_txn(credit=100.0)]
    result = run_precheck_v2(txns, documents_have_simulated_marker=False, opening_balance=0.0, closing_balance=999.0)
    assert result.verdict == "BLOCK"
    assert result.confidence_cap == "L"


def test_pass_without_any_balance_column_stays_plain_pass():
    # No per-row balance parsed at all (e.g. opening/closing entered manually,
    # no "So du" column in the file) — nothing to flag as simulated.
    txns = [_txn(credit=100.0)]
    result = run_precheck_v2(txns, documents_have_simulated_marker=False, opening_balance=0.0, closing_balance=100.0)
    assert result.verdict == "PASS"
    assert result.balance_source == "khong_co"
    assert result.confidence_cap == "M"
