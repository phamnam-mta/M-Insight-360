from app.agents.crosssell.partners_v2 import (
    CIF_STATUS,
    build_partner_row,
    is_junk_partner_name,
    is_person_partner,
    score_partner,
)


def test_tk_prefix_is_never_filtered_as_junk():
    # Real case from spec: "TK XD TM HUY HUNG" was wrongly filtered — TK here
    # means THIET KE (design) in a construction company's name, not a balance row.
    assert not is_junk_partner_name("TK XD TM HUY HUNG")


def test_balance_summary_rows_are_junk():
    assert is_junk_partner_name("TONG SO DU")
    assert is_junk_partner_name("BALANCE")
    assert is_junk_partner_name("123456")
    assert is_junk_partner_name("CONG")
    assert is_junk_partner_name("TONG CONG")


def test_normal_company_names_starting_with_cong_ty_are_not_junk():
    # "CONG"/"TONG" alone mark a balance-summary row, but substring-matching
    # them also nuked every ordinary "CÔNG TY..." (company) or "TỔNG CÔNG
    # TY..." (corporation) name — exactly what §0B's own heading warns against.
    assert not is_junk_partner_name("CONG TY DOI TAC B")
    assert not is_junk_partner_name("CONG TY TNHH ABC XYZ")
    assert not is_junk_partner_name("TONG CONG TY XAY DUNG SO 1")


def test_short_name_is_junk():
    assert is_junk_partner_name("AB")


def test_person_prefixes_detected():
    assert is_person_partner("CA NHAN P01")
    assert is_person_partner("ONG NGUYEN VAN A")
    assert not is_person_partner("CONG TY TNHH ABC")


def test_score_formula_weights_value_frequency_and_spread():
    score = score_partner(
        total_value=110_126_321_436, max_partner_value=110_126_321_436,
        months_active=12, total_period_months=13, freq_per_month=88 / 13,
    )
    # value component maxed (40), frequency capped at 30, spread ~18.46
    assert 88 <= score <= 90


def test_person_partner_routed_to_rb_never_scf():
    row = build_partner_row("CA NHAN P01", "Dau vao (NCC)", 10, 1_053_764_673, 30.0)
    assert row.nhan_canh_bao == "Cá nhân → sản phẩm RB"
    assert "RB" in row.sp_de_xuat
    assert "SCF" not in row.sp_de_xuat or "KHONG" in row.sp_de_xuat.upper() or "KHÔNG" in row.sp_de_xuat


def test_related_party_warning_blocks_scf_pitch():
    row = build_partner_row("CONG TY A036", "Ca hai", 88, 110_126_321_436, 100.0, related_party_warning="Tạm dừng — nghi bên liên quan")
    assert row.co_canh_bao is True
    assert "SCF" not in row.sp_de_xuat or "xác minh" in row.sp_de_xuat.lower()


def test_every_partner_carries_chua_kiem_tra_cif():
    row = build_partner_row("CONG TY A020", "Ca hai", 50, 53_457_665_807, 75.2)
    assert row.trang_thai == CIF_STATUS
    assert "du dieu kien" not in row.trang_thai.lower()
    assert "đủ điều kiện" not in row.trang_thai.lower()
