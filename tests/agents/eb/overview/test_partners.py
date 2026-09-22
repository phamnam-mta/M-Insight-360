from app.agents.eb.overview.partners import evaluate_top_partners
from app.extraction.types import ExtractedDocument, ExtractedTable


def _statement_doc(rows, filename="so_chi_tiet.xlsx"):
    doc = ExtractedDocument(
        filename=filename, doc_type="xlsx", text="", tables=[
            ExtractedTable(rows=rows, sheet_or_page="Sheet1")
        ], extraction_method="spreadsheet", confidence=1.0,
    )
    doc.file_id = filename
    return doc


HEADER = ["Ngay", "So but toan", "Ghi No", "Ghi Co", "Dien giai", "Doi tac", "TK doi tac", "NH doi tac", "Loai tien", "Nguon"]


def test_insufficient_data_without_any_partner_records():
    row = evaluate_top_partners([])
    assert row.result == "INSUFFICIENT_DATA"
    assert row.observed.value is None


def test_insufficient_data_even_with_partner_data_due_to_open_policy_question():
    rows = [
        HEADER,
        ["01/01/2026", "1", "0", "100000000", "thu tien", "Cong ty A", "", "", "VND", ""],
        ["02/01/2026", "2", "50000000", "0", "tra tien", "Cong ty B", "", "", "VND", ""],
    ]
    row = evaluate_top_partners([_statement_doc(rows)])
    assert row.result == "INSUFFICIENT_DATA"
    assert row.observed.status == "COMPUTED"
    assert "Cong ty A" in str(row.observed.value) or "1" in str(row.observed.value)
    assert row.reason_if_incomplete is not None
    assert "đầu ra" in row.reason_if_incomplete or "đầu vào" in row.reason_if_incomplete
