"""Alpha Group demo fixture — every value below is transcribed from a
labeled figure in web/public/demo-eb-sample.html (the user's chosen
regression-test data source, kỳ 2025), not invented. See instruction
v2.3's own T1-T21 expected-output table for the acceptance oracle each
value is checked against (Task 18's Ruling covers the one figure where
this codebase's current field mapping cannot reproduce the instruction's
own oracle value — see the plan ledger)."""

from app.agents.eb.financial_inputs import EbFinancialInputs

ALPHA_GROUP_2025 = EbFinancialInputs(
    current_assets_vnd=293_369_838_619.0,        # "A. TAI SAN NGAN HAN"
    current_liabilities_vnd=165_307_940_854.0,   # "I. No ngan han"
    non_current_assets_vnd=576_704_461_430.0,    # "B. TAI SAN DAI HAN"
    total_liabilities_vnd=289_109_192_531.0,     # "C - NO PHAI TRA"
    equity_vnd=580_965_107_518.0,                # "D - VON CHU SO HUU"
    charter_capital_vnd=580_000_000_000.0,       # "1. Von gop cua chu so huu"
    receivables_vnd=1_030_523_666.0,             # "1. Phai thu ngan han cua khach hang (131)"
    inventory_vnd=13_676_836_829.0,              # "IV. Hang ton kho"
    payables_vnd=1_440_085_191.0,                # "1. Phai tra nguoi ban ngan han (331 Co)"
    cash_vnd=624_458_391.0,                      # "I. Tien va cac khoan tuong duong tien"
    short_term_debt_vnd=78_810_636_239.0,        # "10. Vay va no thue tai chinh ngan han"
    # "Nợ dài hạn" (CĐKT mã 330) = 123.801.251.677 — "Vay dài hạn" (mã 338)
    # itself is explicitly "Chưa xác định từ hồ sơ tải lên" in the source.
    # This is exactly the field this codebase's long_term_debt_vnd regex
    # extracts (it matches "no dai han", i.e. mã 330's own label) — see
    # Task 18's ledger ruling for why this value is used here despite the
    # instruction's own T6 oracle assuming mã 338 (true borrowings) is
    # what feeds the leverage ratio.
    long_term_debt_vnd=123_801_251_677.0,
    net_revenue_vnd=90_105_893_754.0,            # "1. Doanh thu ban hang va cung cap dich vu"
    cogs_vnd=73_340_931_618.0,                   # "4. Gia von hang ban"
    pbt_vnd=29_084_707.0,                        # "14. Tong loi nhuan ke toan truoc thue"
    pat_vnd=23_267_766.0,                        # "17. Loi nhuan sau thue TNDN"
    interest_expense_vnd=12_131_595_580.0,       # fallback ①: "Chi phí tài chính" (KQKD mã 22)
    # depreciation_vnd: "Chưa xác định từ hồ sơ tải lên" — left None (T5).
    # principal_due_vnd: only a demo-labeled PROXY/ước tính exists
    # ("Nợ gốc đến hạn 12 tháng" derived from LCTT "Tiền trả nợ gốc vay"
    # cả năm, explicitly NOT nợ gốc đến hạn 12 tháng thật) — left None
    # here since this fixture models the direct-extraction path, not a
    # human-entered proxy; DSCR stays unknown regardless (depreciation
    # alone already forces NEED_MORE_DATA).
)
