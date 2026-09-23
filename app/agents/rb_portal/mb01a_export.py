import io

import docx

_TEMPLATE_PATH = "docs/templates/MB01A_QT.RR.038_lan_3.docx"
_W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def write_value_after_label(table, row_idx: int, cell_idx: int, value) -> None:
    if not value:
        return
    cell = table.rows[row_idx].cells[cell_idx]
    cell.paragraphs[0].add_run(str(value))


def check_box(table, row_idx: int, cell_idx: int, occurrence: int = 0) -> None:
    cell = table.rows[row_idx].cells[cell_idx]
    checkboxes = cell._tc.findall(f".//{_W_NS}checkBox")
    box = checkboxes[occurrence]
    default = box.find(f"{_W_NS}default")
    default.set(f"{_W_NS}val", "1")


_GENDER_ROW = 4
_MARITAL_ROW = 14
# Unlike the gender checkboxes (row 4), the 4 marital-status boxes each live
# in their OWN cell (verified: cells 9/26/40/53 each contain exactly one
# w:checkBox) rather than 4 occurrences within one cell — map to cell index,
# occurrence is always 0.
_MARITAL_CELL = {"single": 9, "married": 26, "divorced": 40, "widowed": 53}


def build_mb01a_docx(case: dict) -> bytes:
    document = docx.Document(_TEMPLATE_PATH)
    table = document.tables[0]

    customer = case.get("customer") or {}
    write_value_after_label(table, 3, 0, customer.get("full_name"))
    if customer.get("gender") == "male":
        check_box(table, _GENDER_ROW, 0, occurrence=0)
    elif customer.get("gender") == "female":
        check_box(table, _GENDER_ROW, 0, occurrence=1)
    write_value_after_label(table, 5, 0, customer.get("id_number"))
    write_value_after_label(table, 9, 0, customer.get("permanent_address"))
    write_value_after_label(table, 10, 0, customer.get("temporary_address"))
    write_value_after_label(table, 11, 0, customer.get("contact_address"))
    write_value_after_label(table, 13, 0, customer.get("email"))
    marital_cell = _MARITAL_CELL.get(customer.get("marital_status"))
    if marital_cell is not None:
        check_box(table, _MARITAL_ROW, marital_cell, occurrence=0)

    income = case.get("income")
    if income:
        _fill_business_or_employment(table, income)
        _fill_financial(table, income)
    if case.get("loan"):
        _fill_loan(table, case["loan"])
    if case.get("collateral"):
        _fill_collateral(table, case["collateral"])
    _fill_credit_relationships(table, case.get("other"))

    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def insert_run_before(paragraph, run_index: int, text: str) -> None:
    target = paragraph.runs[run_index]
    new_run = paragraph.add_run(text)
    new_elem = new_run._element
    new_elem.getparent().remove(new_elem)
    target._element.addprevious(new_elem)


def _write_years_months(table, row_idx: int, cell_idx: int, years_run_idx: int, months_run_idx: int, years_value) -> None:
    if not years_value:
        return
    whole_years = int(years_value)
    months = round((years_value - whole_years) * 12)
    para = table.rows[row_idx].cells[cell_idx].paragraphs[0]
    insert_run_before(para, months_run_idx, f"{months} ")
    insert_run_before(para, years_run_idx, f"{whole_years} ")


def _fill_business_or_employment(table, income: dict) -> None:
    source_type = income.get("source_type")
    if source_type in ("business", "self_employed", "household_business"):
        write_value_after_label(table, 21, 0, income.get("business_name"))
        write_value_after_label(table, 22, 0, income.get("business_sector"))
        write_value_after_label(table, 29, 0, income.get("business_address"))
        _write_years_months(table, 25, 0, years_run_idx=10, months_run_idx=13, years_value=income.get("business_years"))
    elif source_type == "salary":
        write_value_after_label(table, 33, 0, income.get("employer_name"))
        write_value_after_label(table, 34, 0, income.get("employer_address"))
        write_value_after_label(table, 36, 32, income.get("position"))
        _write_years_months(table, 37, 0, years_run_idx=10, months_run_idx=13, years_value=income.get("employment_years"))


def _fill_financial(table, income: dict) -> None:
    write_value_after_label(table, 68, 17, income.get("income_salary_vnd"))
    write_value_after_label(table, 69, 17, income.get("income_rental_vnd"))
    write_value_after_label(table, 70, 17, income.get("income_business_vnd"))
    write_value_after_label(table, 71, 17, income.get("income_guarantor_vnd"))
    write_value_after_label(table, 68, 56, income.get("expense_living_vnd"))
    write_value_after_label(table, 69, 56, income.get("expense_other_debt_vnd"))
    # (70, 56) "Nghĩa vụ khoản tín dụng lần này" intentionally left blank — see Task 9 notes.
    write_value_after_label(table, 71, 56, income.get("expense_other_vnd"))
    write_value_after_label(table, 74, 0, income.get("dependents_count"))


def _fill_loan(table, loan: dict) -> None:
    write_value_after_label(table, 85, 2, loan.get("product"))
    write_value_after_label(table, 85, 12, loan.get("purpose"))
    write_value_after_label(table, 85, 32, loan.get("amount_vnd"))
    write_value_after_label(table, 85, 47, loan.get("amount_vnd"))
    write_value_after_label(table, 85, 63, loan.get("tenor_months"))


_COLLATERAL_ROWS = (124, 125)  # template pre-draws exactly 2 asset rows


def _fill_collateral(table, collateral: dict) -> None:
    items = (collateral or {}).get("items") or []
    for row_idx, item in zip(_COLLATERAL_ROWS, items):
        write_value_after_label(table, row_idx, 1, item.get("asset_type"))
        write_value_after_label(table, row_idx, 62, item.get("estimated_value_vnd"))
    # items beyond len(_COLLATERAL_ROWS) are not exported — the legal form has no more rows.


def _fill_credit_relationships(table, other: dict) -> None:
    relationships = (other or {}).get("existing_credit_relationships")
    if relationships:
        check_box(table, 128, 41, occurrence=0)  # "Đã/đang có khoản tín dụng tại MSB"
        first = relationships[0]
        write_value_after_label(table, 131, 0, first.get("institution"))
        write_value_after_label(table, 131, 3, first.get("credit_type"))
        write_value_after_label(table, 131, 42, first.get("outstanding_vnd"))
        write_value_after_label(table, 131, 57, first.get("monthly_payment_vnd"))
        # entries beyond the first are not exported — the legal form has only 1 pre-drawn row.
    elif other is not None:
        check_box(table, 128, 25, occurrence=0)  # "Chưa có"
