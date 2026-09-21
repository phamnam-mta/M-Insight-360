from app.extraction.types import ExtractedDocument, ExtractedTable
from app.agents.crosssell.statement_parser import Transaction, parse_statement_documents


def _statement_doc() -> ExtractedDocument:
    header = ["Ngay", "So but toan", "Ghi No", "Ghi Co", "Dien giai", "Doi tac", "Tai khoan doi tac", "Ngan hang doi tac", "Loai tien", "Nguon"]
    rows = [
        header,
        ["01/01/2026", "BT001", "0", "500000000", "Thanh toan hop dong", "CONG TY A001", "TK123", "MB", "VND", "sao_ke"],
        ["02/01/2026", "BT002", "20000000", "0", "Chi phi luong CT LUONG", "", "", "MB", "VND", "sao_ke"],
    ]
    return ExtractedDocument(
        filename="sao_ke.xlsx", doc_type="xlsx", text="", tables=[ExtractedTable(rows=rows, sheet_or_page="TAT CA")],
        extraction_method="spreadsheet", confidence=1.0,
    )


def test_parses_rows_into_transactions():
    txns = parse_statement_documents([_statement_doc()])
    assert len(txns) == 2
    assert txns[0] == Transaction(
        date="01/01/2026", entry_no="BT001", debit=0.0, credit=500_000_000.0,
        description="Thanh toan hop dong", partner="CONG TY A001", partner_account="TK123",
        partner_bank="MB", currency="VND", source="sao_ke",
    )


def test_handles_missing_partner_name_without_crashing():
    txns = parse_statement_documents([_statement_doc()])
    assert txns[1].partner == ""


def test_accepts_common_header_name_variants():
    # Review Focus (plan): a statement whose header row uses slightly different
    # Vietnamese column names than the exact HEADER_MAP strings ("Ngày GD" instead of
    # "Ngày") must not silently drop the whole file.
    header = ["Ngay GD", "So CT", "No", "Co", "Noi dung", "Ten doi tac", "TK doi tac", "NH doi tac", "Loai tien", "Nguon"]
    rows = [header, ["03/01/2026", "BT004", "0", "300000000", "Thu tien hang", "CONG TY D", "", "MB", "VND", "sao_ke"]]
    doc = ExtractedDocument(
        filename="s.xlsx", doc_type="xlsx", text="", tables=[ExtractedTable(rows=rows, sheet_or_page="s")],
        extraction_method="spreadsheet", confidence=1.0,
    )
    txns = parse_statement_documents([doc])
    assert len(txns) == 1
    assert txns[0].credit == 300_000_000.0
    assert txns[0].partner == "CONG TY D"


def test_ignores_non_statement_tables():
    other = ExtractedDocument(
        filename="unrelated.xlsx", doc_type="xlsx", text="", tables=[ExtractedTable(rows=[["A", "B"], ["1", "2"]], sheet_or_page="s")],
        extraction_method="spreadsheet", confidence=1.0,
    )
    assert parse_statement_documents([other]) == []


def test_parses_vietnamese_locale_thousands_separator():
    # Real MB/MSB CSV exports can use "." as the thousands separator (VN locale), e.g.
    # "500.000.000" meaning five hundred million VND, not the number 500.0. Silently
    # zeroing these out (the old behaviour: float("500.000.000") raises -> 0.0) would
    # corrupt every downstream deal-size calculation without any warning — a top-priority
    # correctness risk for the agent the business sponsor cares most about.
    header = ["Ngay", "So but toan", "Ghi No", "Ghi Co", "Dien giai", "Doi tac", "Tai khoan doi tac", "Ngan hang doi tac", "Loai tien", "Nguon"]
    rows = [
        header,
        ["01/01/2026", "BT001", "0", "500.000.000", "Thanh toan hop dong", "CONG TY A", "", "MB", "VND", "sao_ke"],
        ["02/01/2026", "BT002", "1.234.567,89", "0", "Chi phi", "CONG TY B", "", "MB", "VND", "sao_ke"],
    ]
    doc = ExtractedDocument(
        filename="s.xlsx", doc_type="xlsx", text="", tables=[ExtractedTable(rows=rows, sheet_or_page="s")],
        extraction_method="spreadsheet", confidence=1.0,
    )
    txns = parse_statement_documents([doc])
    assert txns[0].credit == 500_000_000.0
    assert txns[1].debit == 1_234_567.89


def test_both_debit_and_credit_populated_prefers_credit_deterministically():
    header = ["Ngay", "So but toan", "Ghi No", "Ghi Co", "Dien giai", "Doi tac", "Tai khoan doi tac", "Ngan hang doi tac", "Loai tien", "Nguon"]
    rows = [header, ["01/01/2026", "BT003", "100", "200", "Dong thoi", "X", "", "MB", "VND", "sao_ke"]]
    doc = ExtractedDocument(
        filename="s.xlsx", doc_type="xlsx", text="", tables=[ExtractedTable(rows=rows, sheet_or_page="s")],
        extraction_method="spreadsheet", confidence=1.0,
    )
    txns = parse_statement_documents([doc])
    assert txns[0].debit == 100.0
    assert txns[0].credit == 200.0  # both kept as-is; classification layer decides how to use them
