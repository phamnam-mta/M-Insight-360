from app.extraction.types import ExtractedTable
from app.agents.eb.canonical import classify_sheet


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
