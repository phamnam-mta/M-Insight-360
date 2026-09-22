from app.agents.crosssell.deal_engine import (
    evaluate_rule1,
    evaluate_rule2,
    evaluate_rule3,
    evaluate_rule4,
    evaluate_rule6,
)
from app.agents.crosssell.statement_parser import Transaction


def _txn(date="01/06/2025", debit=0.0, credit=0.0, desc="", partner="", currency="VND", balance=None):
    return Transaction(
        date=date, entry_no="1", debit=debit, credit=credit, description=desc,
        partner=partner, partner_account="", partner_bank="", currency=currency, source="",
        balance=balance,
    )


# ───────────────────────── Rule 1 ─────────────────────────

def test_rule1_no_payroll_transactions_is_pna():
    result = evaluate_rule1([_txn()], period_months=12, confidence_cap="H")
    assert result.priority == "P-NA"
    assert result.deal_size is None


def test_rule1_statement_only_annualizes():
    txns = [_txn(debit=100_000_000, desc="tra luong thang 1") for _ in range(6)]
    result = evaluate_rule1(txns, period_months=6, confidence_cap="H")
    # 600,000,000 / 6 months * 12 = 1,200,000,000
    assert result.deal_size == 1_200_000_000
    assert result.priority == "P3"


def test_rule1_switches_to_lctt_when_statement_underreports():
    txns = [_txn(debit=100_000_000, desc="tra luong thang 1")]
    # statement annualized would be tiny; LCTT shows the real payroll figure
    result = evaluate_rule1(txns, period_months=1, confidence_cap="H", lctt_payroll_vnd=3_950_214_073)
    assert result.deal_size == 3_950_214_073
    assert any(b.tieu_de == "Công thức" for b in result.chi_tiet)


def test_rule1_confidence_capped_by_precheck():
    txns = [_txn(debit=100_000_000, desc="tra luong")]
    result = evaluate_rule1(txns, period_months=12, confidence_cap="L")
    assert result.confidence == "L"


# ───────────────────────── Rule 2 ─────────────────────────

def test_rule2_no_qualifying_partner_is_pna():
    txns = [_txn(credit=100_000_000, partner="A") for _ in range(2)]  # below 3-GD threshold
    result = evaluate_rule2(txns, period_months=12, confidence_cap="H")
    assert result.priority == "P-NA"


def test_rule2_applies_revenue_cap_when_it_is_the_tightest():
    # 3 GD, 600M each = 1.8B total over 12 months -> annualized 1.8B -> 80% = 1.44B
    # revenue cap 10% of 9,010,589,375 -> ~901M, tighter than both the 80% figure and the 20B cap
    txns = [_txn(credit=600_000_000, partner="DOI TAC A") for _ in range(3)]
    result = evaluate_rule2(txns, period_months=12, confidence_cap="H", revenue_vnd=9_010_589_375)
    assert result.deal_size == round(9_010_589_375 * 0.10)
    assert "10% doanh thu" in result.chi_tiet[0].noi_dung


def test_rule2_uses_20b_cap_when_no_revenue_given():
    txns = [_txn(credit=10_000_000_000, partner="DOI TAC LON") for _ in range(3)]
    result = evaluate_rule2(txns, period_months=12, confidence_cap="H")
    # deal_tho = 30B annualized * 80% = 24B, capped at 20B (no revenue cap applies)
    assert result.deal_size == 20_000_000_000


def test_rule2_low_revenue_adds_ineligibility_warning():
    txns = [_txn(credit=600_000_000, partner="DOI TAC A") for _ in range(3)]
    result = evaluate_rule2(txns, period_months=12, confidence_cap="H", revenue_vnd=90_000_000_000)
    assert any("100 tỷ" in w for w in result.canh_bao)


# ───────────────────────── Rule 3 ─────────────────────────

def test_rule3_no_balance_data_is_pna():
    result = evaluate_rule3({}, confidence_cap="H", balance_is_simulated=False)
    assert result.priority == "P-NA"


def test_rule3_fewer_than_10_days_above_threshold_is_pna():
    balances = {f"day{i}": 6_000_000_000.0 for i in range(5)}
    result = evaluate_rule3(balances, confidence_cap="H", balance_is_simulated=False)
    assert result.priority == "P-NA"


def test_rule3_uses_raw_minimum_when_not_an_outlier():
    balances = {f"day{i}": 8_000_000_000.0 for i in range(15)}
    result = evaluate_rule3(balances, confidence_cap="H", balance_is_simulated=False)
    assert result.deal_size == 8_000_000_000


def test_rule3_outlier_minimum_uses_5th_percentile_not_raw_min():
    balances = {f"day{i}": 100_000_000_000.0 for i in range(19)}
    balances["outlier"] = 191.0  # one technical trough day, far below 5% of the average
    result = evaluate_rule3(balances, confidence_cap="H", balance_is_simulated=False)
    assert result.deal_size != 191
    assert result.deal_size > 1_000_000_000
    assert any("điểm trũng" in w for w in result.canh_bao)


def test_rule3_simulated_balance_never_sells():
    balances = {f"day{i}": 8_000_000_000.0 for i in range(15)}
    result = evaluate_rule3(balances, confidence_cap="H", balance_is_simulated=True)
    assert result.priority == "P-NA"
    assert result.deal_size is None
    assert any("mô phỏng" in w for w in result.canh_bao)


# ───────────────────────── Rule 4 ─────────────────────────

def test_rule4_all_vnd_is_pna_and_does_not_conclude_no_fx_need():
    txns = [_txn(credit=1.0, currency="VND")]
    result = evaluate_rule4(txns, period_months=12, confidence_cap="H")
    assert result.priority == "P-NA"
    joined = " ".join(result.canh_bao)
    assert "không có nhu cầu" not in joined.lower() or "không kết luận" in joined.lower()


def test_rule4_fx_transactions_annualized():
    txns = [_txn(credit=1_000_000_000, currency="USD") for _ in range(6)]
    result = evaluate_rule4(txns, period_months=6, confidence_cap="H")
    assert result.deal_size == 12_000_000_000


# ───────────────────────── Rule 6 ─────────────────────────

def test_rule6_no_loan_signal_is_pna():
    result = evaluate_rule6([_txn()], confidence_cap="H")
    assert result.priority == "P-NA"


def test_rule6_without_bctc_gives_chua_xac_dinh_not_null_silently():
    txns = [_txn(debit=6_000_000_000, desc="tra no vay")]
    result = evaluate_rule6(txns, confidence_cap="H")
    assert result.deal_size is None
    assert result.deal_size_headline == "CHƯA XÁC ĐỊNH — cần CIC"
    assert result.priority == "P1"  # scale evidence still present even without BCTC


def test_rule6_with_bctc_uses_short_term_debt_balance():
    txns = [_txn(credit=0.0, debit=1_000_000_000, desc="tra no vay")]
    result = evaluate_rule6(
        txns, confidence_cap="H",
        cdkt_short_term_debt_vnd=78_810_636_239,
        cdkt_short_term_debt_opening_vnd=82_915_982_025,
        lctt_loan_disbursement_vnd=155_529_325_400,
        lctt_loan_repayment_vnd=159_634_671_186,
    )
    assert result.deal_size == 78_810_636_239
    assert any("cần RM lấy CIC" in w.lower() or "CIC" in w for w in result.canh_bao)


def test_rule6_zero_disbursement_flags_direct_to_supplier_signal():
    txns = [_txn(credit=0.0, debit=1_000_000_000, desc="tra no vay khe uoc LD123")]
    result = evaluate_rule6(txns, confidence_cap="H", cdkt_short_term_debt_vnd=1_000_000_000)
    assert any("giải ngân không về tài khoản này" in w for w in result.canh_bao)
