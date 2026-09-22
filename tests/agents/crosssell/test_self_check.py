from app.agents.crosssell.card_types import DetailBlock, Opportunity
from app.agents.crosssell.partners_v2 import PartnerRow
from app.agents.crosssell.self_check import run_self_check


def _good_opp(deal_size=169_910_860_881, rule_id="RULE3_IDLE"):
    return Opportunity(
        rule_id=rule_id, san_pham="Chứng chỉ tiền gửi (CCTG)", segment="EB",
        deal_size=deal_size, deal_size_headline="169,9 tỷ", deal_size_exact="169.910.860.881",
        priority="P1", confidence="M", ly_do_confidence="x",
        signal_1dong="Vốn nhàn rỗi 169,9 tỷ ổn định 2 năm.",
        chi_tiet=[DetailBlock("Công thức", "x = y")],
    )


def _good_kpi():
    return [
        {"nhan": "Tổng cơ hội", "gia_tri": "169,9 tỷ", "phu": "1 cơ hội", "nhan_manh": True},
        {"nhan": "Ưu tiên P1", "gia_tri": "1", "phu": ""},
        {"nhan": "Đối tác tiềm năng", "gia_tri": "0", "phu": ""},
        {"nhan": "Thị phần MSB", "gia_tri": "0%", "phu": ""},
    ]


def _good_badges():
    return [{"loai": "ok", "nhan": "924/924 khớp"}]


def _good_partner():
    return PartnerRow(ten="CONG TY A", chieu="Ca hai", so_gd=10, tong_gt=1_000_000_000, diem=50.0)


def test_all_good_produces_no_fails():
    fails = run_self_check([_good_opp()], _good_badges(), _good_kpi(), [_good_partner()])
    assert fails == []


def test_catches_technical_name_leak_in_signal():
    opp = _good_opp()
    opp.signal_1dong = "operating_in 365 tỷ đang ở ngoài MSB."
    fails = run_self_check([opp], _good_badges(), _good_kpi(), [])
    assert any("B:" in f for f in fails)


def test_catches_missing_cong_thuc_block():
    opp = _good_opp()
    opp.chi_tiet = []
    fails = run_self_check([opp], _good_badges(), _good_kpi(), [])
    assert any("D4" in f for f in fails)


def test_catches_signal_over_110_chars():
    opp = _good_opp()
    opp.signal_1dong = "x" * 111 + " 1"
    fails = run_self_check([opp], _good_badges(), _good_kpi(), [])
    assert any("D2" in f for f in fails)


def test_catches_wrong_kpi_count():
    fails = run_self_check([_good_opp()], _good_badges(), _good_kpi()[:2], [])
    assert any("D8" in f for f in fails)


def test_catches_partner_not_marked_chua_kiem_tra_cif():
    bad_partner = PartnerRow(ten="X", chieu="Ca hai", so_gd=1, tong_gt=1.0, diem=1.0, trang_thai="Du dieu kien")
    fails = run_self_check([_good_opp()], _good_badges(), _good_kpi(), [bad_partner])
    assert any("CIF" in f for f in fails)


def test_catches_out_of_order_deal_sizes():
    small = _good_opp(deal_size=1_000_000, rule_id="RULE1_PAYROLL")
    big = _good_opp(deal_size=100_000_000_000, rule_id="RULE6_LOAN")
    fails = run_self_check([small, big], _good_badges(), _good_kpi(), [])
    assert any("D10" in f for f in fails)
