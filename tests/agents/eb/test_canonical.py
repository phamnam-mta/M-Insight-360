from app.extraction.types import ExtractedDocument, ExtractedTable
from app.agents.eb.canonical import build_canonical, classify_sheet


def test_classify_sheet_by_name_bctc_tom_tat():
    table = ExtractedTable(sheet_or_page="10_BCTC_TOM_TAT", rows=[["Chi tieu", "So cuoi nam"], ["Von chu so huu", "500000000"]])
    included, reason = classify_sheet(table)
    assert included is True
    assert "tên sheet" in reason.lower() or "tom tat" in reason.lower()


def test_classify_sheet_by_name_cdkt():
    table = ExtractedTable(sheet_or_page="CDKT", rows=[["Chi tieu", "Ma so", "So cuoi nam"]])
    included, _ = classify_sheet(table)
    assert included is True


def test_classify_sheet_sparse_labels_still_included_by_content():
    # A real BCTC sheet whose sheet name gives no signal at all, but whose
    # rows still carry enough BCTC-field-pattern hits to clear the content
    # threshold — Review Focus #2.
    table = ExtractedTable(
        sheet_or_page="Sheet1",
        rows=[
            ["Von chu so huu", "580965107518"],
            ["Tai san ngan han", "293369838619"],
            ["No ngan han", "165307940854"],
            ["Doanh thu thuan", "90105893754"],
        ],
    )
    included, _ = classify_sheet(table)
    assert included is True


def test_classify_sheet_bank_statement_excluded_with_reason():
    table = ExtractedTable(
        sheet_or_page="SAO KE",
        rows=[["Ngay GD", "Dien giai", "Ghi No", "Ghi Co", "So Du"]]
        + [[f"{d:02d}/01/2026", f"Giao dich {d}", "0", "1000000", "1000000"] for d in range(1, 30)],
    )
    included, reason = classify_sheet(table)
    assert included is False
    assert reason  # a real, non-empty reason is always given (Bước 0)


def test_classify_sheet_irrelevant_content_excluded():
    table = ExtractedTable(sheet_or_page="Notes", rows=[["Ghi chu noi bo", "khong lien quan"]])
    included, _ = classify_sheet(table)
    assert included is False


def _bctc_table(rows, sheet="10_BCTC_TOM_TAT"):
    return ExtractedTable(sheet_or_page=sheet, rows=rows)


def test_build_canonical_ignores_bank_statement_sheet_dates_t29():
    # T29 — 14-sheet-scale scenario reduced to 2 sheets: BCTC (2025, no
    # explicit year in header, relative labels) + sao ke (2026 dates).
    bctc = _bctc_table([
        ["Chi tieu", "So cuoi nam", "So dau nam"],
        ["Von chu so huu", "580965107518", "500000000000"],
        ["Bao cao lap ngay 31/12/2025"],
    ])
    saoke = _bctc_table(
        [["Ngay GD", "Dien giai", "So tien"]] + [[f"{d:02d}/01/2026", f"GD {d}", "1000000"] for d in range(1, 30)],
        sheet="SAO KE",
    )
    doc = ExtractedDocument(filename="f.xlsx", doc_type="xlsx", text="", tables=[bctc, saoke], extraction_method="spreadsheet", confidence=1.0)
    result = build_canonical([doc])
    assert "2025" in result.fields_by_year
    assert result.fields_by_year["2025"]["BS_EQUITY"].gia_tri == 580965107518.0
    assert "2026" not in result.fields_by_year or "BS_EQUITY" not in result.fields_by_year.get("2026", {})
    included = {s.sheet: s.included for s in result.sheet_scan}
    assert included["10_BCTC_TOM_TAT"] is True
    assert included["SAO KE"] is False


def test_build_canonical_row_number_column_never_captured_as_field_t31():
    # T31 — a leading STT (row-number) column 1..20 must never itself be
    # picked up as a field value merely because it numerically coincides
    # with a KQKD ma (10, 11).
    bctc = _bctc_table([
        ["STT", "Chi tieu", "Ma so", "So tien"],
        ["10", "Doanh thu thuan", "10", "90105893754"],
        ["11", "Cac khoan giam tru doanh thu", "11", "0"],
    ])
    doc = ExtractedDocument(filename="f.xlsx", doc_type="xlsx", text="", tables=[bctc], extraction_method="spreadsheet", confidence=1.0)
    result = build_canonical([doc])
    year = next(iter(result.fields_by_year))
    revenue = result.fields_by_year[year]["IS_REVENUE"]
    assert revenue.gia_tri == 90105893754.0
    for field_dict in result.fields_by_year.values():
        for cf in field_dict.values():
            assert cf.gia_tri != 10 and cf.gia_tri != 11


def test_build_canonical_conflicting_values_flagged_not_silently_chosen():
    # Two BCTC-included sheets both reporting Vốn chủ sở hữu for the SAME
    # year with DIFFERENT numbers — a genuine consistency conflict.
    sheet_a = _bctc_table([["Chi tieu", "31/12/2025"], ["Von chu so huu", "580965107518"]], sheet="CDKT")
    sheet_b = _bctc_table([["Chi tieu", "31/12/2025"], ["Von chu so huu", "999999999999"]], sheet="BCTC TOM TAT")
    doc = ExtractedDocument(filename="f.xlsx", doc_type="xlsx", text="", tables=[sheet_a, sheet_b], extraction_method="spreadsheet", confidence=1.0)
    result = build_canonical([doc])
    assert result.consistency.khop is False
    assert any("Vốn chủ sở hữu" in str(d) or "BS_EQUITY" in str(d) for d in result.consistency.danh_sach_lech)


def test_build_canonical_different_years_never_flagged_as_conflict():
    # Same field, DIFFERENT years across sheets is not a conflict at all.
    sheet_a = _bctc_table([["Chi tieu", "31/12/2025"], ["Von chu so huu", "580965107518"]], sheet="CDKT 2025")
    sheet_b = _bctc_table([["Chi tieu", "31/12/2024"], ["Von chu so huu", "500000000000"]], sheet="CDKT 2024")
    doc = ExtractedDocument(filename="f.xlsx", doc_type="xlsx", text="", tables=[sheet_a, sheet_b], extraction_method="spreadsheet", confidence=1.0)
    result = build_canonical([doc])
    assert result.consistency.khop is True


def test_build_canonical_sheets_all_includes_excluded_sheet():
    saoke = _bctc_table([["Ngay", "So tien"], ["01/01/2026", "1000000"]], sheet="SAO KE")
    doc = ExtractedDocument(filename="f.xlsx", doc_type="xlsx", text="", tables=[saoke], extraction_method="spreadsheet", confidence=1.0)
    default_result = build_canonical([doc])
    all_result = build_canonical([doc], include_all_sheets=True)
    default_included = {s.sheet: s.included for s in default_result.sheet_scan}
    all_included = {s.sheet: s.included for s in all_result.sheet_scan}
    assert default_included["SAO KE"] is False
    assert all_included["SAO KE"] is True


def test_build_canonical_no_bctc_sheets_returns_empty_fields_not_error():
    saoke = _bctc_table([["Ngay", "So tien"], ["01/01/2026", "1000000"]], sheet="SAO KE")
    doc = ExtractedDocument(filename="f.xlsx", doc_type="xlsx", text="", tables=[saoke], extraction_method="spreadsheet", confidence=1.0)
    result = build_canonical([doc])
    assert result.fields_by_year == {}
    assert result.sheet_scan[0].included is False


def test_build_canonical_same_sheet_multiple_matches_never_hard_blocks():
    # Review finding C1: a field-pattern regex is a label substring match,
    # so a real CDKT's "Hang ton kho" (141) and "Du phong giam gia hang ton
    # kho" (149) both match the same "hang ton kho" pattern within ONE
    # sheet — that is noise from the sheet's own layout, not a real
    # cross-source disagreement, and must never hard-block export.
    table = _bctc_table([
        ["Chi tieu", "Ma so", "31/12/2025"],
        ["1. Hang ton kho", "141", "-20"],
        ["2. Du phong giam gia hang ton kho", "149", "320"],
    ], sheet="CDKT")
    doc = ExtractedDocument(filename="f.xlsx", doc_type="xlsx", text="", tables=[table], extraction_method="spreadsheet", confidence=1.0)
    result = build_canonical([doc])
    assert result.consistency.khop is True
    assert result.consistency.danh_sach_lech == []
    assert result.fields_by_year["2025"]["BS_INVENTORY"].co_gia_tri is False


def test_build_canonical_cross_sheet_conflict_still_hard_blocks():
    sheet_a = _bctc_table([["Chi tieu", "31/12/2025"], ["Von chu so huu", "580965107518"]], sheet="CDKT")
    sheet_b = _bctc_table([["Chi tieu", "31/12/2025"], ["Von chu so huu", "999999999999"]], sheet="BCTC TOM TAT")
    doc = ExtractedDocument(filename="f.xlsx", doc_type="xlsx", text="", tables=[sheet_a, sheet_b], extraction_method="spreadsheet", confidence=1.0)
    result = build_canonical([doc])
    assert result.consistency.khop is False
    assert len(result.consistency.danh_sach_lech) == 1


def test_classify_sheet_by_name_handles_d_with_stroke():
    # Review finding C4: NFKD does not decompose Đ/đ, so "CĐKT" (a very
    # common real sheet name) must still be recognized as a BCTC sheet.
    table = ExtractedTable(sheet_or_page="CĐKT", rows=[["Chi tieu", "Ma so", "So cuoi nam"]])
    included, _ = classify_sheet(table)
    assert included is True


def test_classify_sheet_two_labels_now_clears_lowered_threshold():
    # Review finding C4: a real, terse single-purpose sheet with only 2
    # populated BCTC labels (no sheet-name signal) must not be entirely
    # excluded from canonical extraction.
    table = ExtractedTable(
        sheet_or_page="Sheet1",
        rows=[["Tai san ngan han", "293369838619"], ["No ngan han", "165307940854"]],
    )
    included, _ = classify_sheet(table)
    assert included is True


def _real_cdkt_table(sheet="CĐKT"):
    # Rows verified against a real uploaded BCTC (Mẫu B01-DN, Thông tư
    # 200/2014/TT-BTC) this session — exact mã số, labels and figures.
    return ExtractedTable(
        sheet_or_page=sheet,
        rows=[
            ["BẢNG CÂN ĐỐI KẾ TOÁN"],
            ["Tại ngày 31 tháng 12 năm 2025"],
            ["TÀI SẢN", "Mã số", "Thuyết minh", "Số cuối năm", "Số đầu năm"],
            ["A - TÀI SẢN NGẮN HẠN", "100", "", "293369838619", "211204710746"],
            ["I. Tiền và các khoản tương đương tiền", "110", "", "624458391", "25457970"],
            ["1. Phải thu ngắn hạn của khách hàng", "131", "", "1030523666", "6970818056"],
            ["1. Hàng tồn kho", "141", "", "13676836829", "11441820291"],
            ["2. Dự phòng giảm giá hàng tồn kho (*)", "149", "", "0", "0"],
            ["B - TÀI SẢN DÀI HẠN", "200", "", "576704461430", "572855142017"],
            ["C - NỢ PHẢI TRẢ", "300", "", "289109192531", "203118013011"],
            ["I. Nợ ngắn hạn", "310", "", "165307940854", "203118013011"],
            ["10. Vay và nợ thuê tài chính ngắn hạn", "320", "", "78810636239", "82915982025"],
            ["8. Vay và nợ thuê tài chính dài hạn", "338", "", "0", "0"],
            ["D - VỐN CHỦ SỞ HỮU", "400", "", "580965107518", "580941839752"],
            ["1. Vốn góp của chủ sở hữu", "411", "", "580000000000", "580000000000"],
        ],
    )


def _real_kqkd_table(sheet="KQKD"):
    return ExtractedTable(
        sheet_or_page=sheet,
        rows=[
            ["BÁO CÁO KẾT QUẢ HOẠT ĐỘNG KINH DOANH"],
            ["Kỳ tính thuế: Năm 2025"],
            ["Chỉ tiêu", "Mã số", "Thuyết minh", "Năm nay", "Năm trước"],
            ["3. Doanh thu thuần về bán hàng và cung cấp dịch vụ", "10", "", "90105893754", "75087670552"],
            ["4. Giá vốn hàng bán", "11", "", "73340931618", "62244286018"],
            ["5. Lợi nhuận gộp về bán hàng và cung cấp dịch vụ", "20", "", "16764962136", "12843384534"],
            ["- Trong đó: Chi phí lãi vay", "23", "", "12131595580", "6600912167"],
            ["14. Tổng lợi nhuận kế toán trước thuế", "50", "", "29084707", "79966510"],
            ["17. Lợi nhuận sau thuế thu nhập doanh nghiệp", "60", "", "23267766", "63973208"],
        ],
    )


def _real_lctt_table(sheet="LCTT"):
    return ExtractedTable(
        sheet_or_page=sheet,
        rows=[
            ["BÁO CÁO LƯU CHUYỂN TIỀN TỆ"],
            ["Kỳ tính thuế: Năm 2025"],
            ["Chỉ tiêu", "Mã số", "Thuyết minh", "Năm nay", "Năm trước"],
            ["Lưu chuyển tiền thuần từ hoạt động kinh doanh", "20", "", "8624346207", "(68201460796)"],
        ],
    )


def test_build_canonical_real_cdkt_extracts_by_ma_so_both_years():
    doc = ExtractedDocument(filename="f.xlsx", doc_type="xlsx", text="", tables=[_real_cdkt_table()], extraction_method="spreadsheet", confidence=1.0)
    result = build_canonical([doc])
    assert result.fields_by_year["2025"]["BS_EQUITY"].gia_tri == 580965107518.0
    assert result.fields_by_year["2024"]["BS_EQUITY"].gia_tri == 580941839752.0
    assert result.fields_by_year["2025"]["BS_CASH"].gia_tri == 624458391.0
    assert result.fields_by_year["2025"]["BS_AR_CUSTOMER"].gia_tri == 1030523666.0
    assert result.fields_by_year["2025"]["BS_ST_BORROWINGS"].gia_tri == 78810636239.0


def test_build_canonical_real_cdkt_inventory_never_confused_with_provision_row():
    # T31-style: mã 141 "Hàng tồn kho" and mã 149 "Dự phòng giảm giá hàng
    # tồn kho" both contain the label substring "hàng tồn kho" — a
    # regex-only match would be ambiguous within this one sheet (and,
    # before this fix, silently flagged the field as unresolved). The
    # mã-số route must read exactly mã 141, no ambiguity at all.
    doc = ExtractedDocument(filename="f.xlsx", doc_type="xlsx", text="", tables=[_real_cdkt_table()], extraction_method="spreadsheet", confidence=1.0)
    result = build_canonical([doc])
    field = result.fields_by_year["2025"]["BS_INVENTORY"]
    assert field.co_gia_tri is True
    assert field.gia_tri == 13676836829.0


def test_build_canonical_real_kqkd_extracts_by_ma_so():
    doc = ExtractedDocument(filename="f.xlsx", doc_type="xlsx", text="", tables=[_real_kqkd_table()], extraction_method="spreadsheet", confidence=1.0)
    result = build_canonical([doc])
    assert result.fields_by_year["2025"]["IS_REVENUE"].gia_tri == 90105893754.0
    assert result.fields_by_year["2025"]["IS_COGS"].gia_tri == 73340931618.0
    assert result.fields_by_year["2025"]["IS_GROSS_PROFIT"].gia_tri == 16764962136.0
    assert result.fields_by_year["2025"]["IS_INTEREST"].gia_tri == 12131595580.0
    assert result.fields_by_year["2025"]["IS_PBT"].gia_tri == 29084707.0
    assert result.fields_by_year["2025"]["IS_PAT"].gia_tri == 23267766.0


def test_build_canonical_ma_so_20_scoped_by_statement_type():
    # Mã số "20" means "Lợi nhuận gộp" in KQKD but "Lưu chuyển tiền thuần
    # từ HĐKD" in LCTT — the SAME upload commonly carries both sheets.
    # Mixing them up without knowing which statement a sheet is would
    # silently cross-assign a completely different figure.
    doc = ExtractedDocument(
        filename="f.xlsx", doc_type="xlsx", text="",
        tables=[_real_kqkd_table(), _real_lctt_table()],
        extraction_method="spreadsheet", confidence=1.0,
    )
    result = build_canonical([doc])
    assert result.fields_by_year["2025"]["IS_GROSS_PROFIT"].gia_tri == 16764962136.0
    assert result.fields_by_year["2025"]["CFO"].gia_tri == 8624346207.0
    # Never cross-assigned or flagged as a false conflict between the two.
    assert result.consistency.khop is True


def test_build_canonical_ma_so_parses_parenthesized_negative():
    lctt = _real_lctt_table()
    doc = ExtractedDocument(filename="f.xlsx", doc_type="xlsx", text="", tables=[lctt], extraction_method="spreadsheet", confidence=1.0)
    result = build_canonical([doc])
    assert result.fields_by_year["2024"]["CFO"].gia_tri == -68201460796.0
