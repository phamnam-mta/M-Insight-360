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


def test_ignores_non_statement_tables():
    other = ExtractedDocument(
        filename="unrelated.xlsx", doc_type="xlsx", text="", tables=[ExtractedTable(rows=[["A", "B"], ["1", "2"]], sheet_or_page="s")],
        extraction_method="spreadsheet", confidence=1.0,
    )
    assert parse_statement_documents([other]) == []


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
