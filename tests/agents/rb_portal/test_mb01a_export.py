import io

import docx

from app.agents.rb_portal.mb01a_export import build_mb01a_docx, check_box, write_value_after_label

TEMPLATE_PATH = "docs/templates/MB01A_QT.RR.038_lan_3.docx"


def test_write_value_after_label_appends_to_the_cell():
    document = docx.Document(TEMPLATE_PATH)
    table = document.tables[0]
    write_value_after_label(table, 3, 0, "NGUYEN VAN A")
    assert table.rows[3].cells[0].text == "Họ tên: NGUYEN VAN A"


def test_write_value_after_label_is_noop_for_falsy_value():
    document = docx.Document(TEMPLATE_PATH)
    table = document.tables[0]
    original = table.rows[3].cells[0].text
    write_value_after_label(table, 3, 0, None)
    assert table.rows[3].cells[0].text == original


def test_check_box_sets_default_to_1_for_the_targeted_occurrence_only():
    document = docx.Document(TEMPLATE_PATH)
    table = document.tables[0]
    check_box(table, 4, 0, occurrence=0)  # "Nam"
    xml = table.rows[4].cells[0]._tc.xml
    # exactly one w:default now reads val="1" within this cell (Nữ stays "0")
    assert xml.count('w:default w:val="1"') == 1
    assert xml.count('w:default w:val="0"') == 1


def test_build_mb01a_docx_returns_openable_bytes_with_customer_name():
    case = {
        "customer": {"full_name": "NGUYEN VAN A", "gender": "male", "id_number": "001234567890"},
        "legal": None, "income": None, "loan": None, "collateral": None, "other": None,
    }
    result = build_mb01a_docx(case)
    assert isinstance(result, bytes)
    document = docx.Document(io.BytesIO(result))
    assert "NGUYEN VAN A" in document.tables[0].rows[3].cells[0].text


def test_build_mb01a_docx_leaves_fields_blank_for_empty_case():
    case = {"customer": None, "legal": None, "income": None, "loan": None, "collateral": None, "other": None}
    result = build_mb01a_docx(case)
    document = docx.Document(io.BytesIO(result))
    assert document.tables[0].rows[3].cells[0].text == "Họ tên: "


def test_business_income_case_fills_business_section():
    case = {
        "customer": None, "legal": None,
        "income": {"source_type": "business", "business_name": "Quan Com A",
                     "business_sector": "An uong", "business_address": "123 Le Loi",
                     "income_business_vnd": 30_000_000, "expense_living_vnd": 8_000_000,
                     "dependents_count": 2},
        "loan": None, "collateral": None, "other": None,
    }
    document = docx.Document(io.BytesIO(build_mb01a_docx(case)))
    t = document.tables[0]
    assert "Quan Com A" in t.rows[21].cells[0].text
    assert "An uong" in t.rows[22].cells[0].text
    assert "30000000" in t.rows[70].cells[17].text or "30000000.0" in t.rows[70].cells[17].text
    assert "8000000" in t.rows[68].cells[56].text or "8000000.0" in t.rows[68].cells[56].text
    assert "2" in t.rows[74].cells[0].text


def test_salary_income_case_fills_employment_section_not_business():
    case = {
        "customer": None, "legal": None,
        "income": {"source_type": "salary", "employer_name": "Cong ty B",
                     "position": "Ke toan truong", "income_salary_vnd": 25_000_000},
        "loan": None, "collateral": None, "other": None,
    }
    document = docx.Document(io.BytesIO(build_mb01a_docx(case)))
    t = document.tables[0]
    assert "Cong ty B" in t.rows[33].cells[0].text
    assert "Ke toan truong" in t.rows[36].cells[32].text
    assert t.rows[21].cells[0].text == "Tên cơ sở kinh doanh*: "  # business section untouched


def test_loan_and_collateral_and_credit_relationship_rows_filled():
    case = {
        "customer": None, "legal": None, "income": None,
        "loan": {"product": "Vay vốn", "purpose": "Bổ sung vốn kinh doanh",
                   "amount_vnd": 200_000_000, "tenor_months": 24},
        "collateral": {"items": [
            {"asset_type": "Bất động sản", "estimated_value_vnd": 800_000_000},
            {"asset_type": "Ô tô", "estimated_value_vnd": 500_000_000},
        ]},
        "other": {"existing_credit_relationships": [
            {"institution": "Vietcombank", "credit_type": "Vay tiêu dùng", "outstanding_vnd": 50_000_000},
        ]},
    }
    document = docx.Document(io.BytesIO(build_mb01a_docx(case)))
    t = document.tables[0]
    assert "Vay vốn" in t.rows[85].cells[2].text
    assert "Bổ sung vốn kinh doanh" in t.rows[85].cells[12].text
    assert "Bất động sản" in t.rows[124].cells[1].text
    assert "Ô tô" in t.rows[125].cells[1].text
    assert "Vietcombank" in t.rows[131].cells[0].text
    xml = t.rows[128].cells[41]._tc.xml  # "Đã/đang có" box checked
    assert 'w:default w:val="1"' in xml


def test_no_existing_credit_relationship_checks_the_chua_co_box():
    case = {
        "customer": None, "legal": None, "income": None, "loan": None, "collateral": None,
        "other": {"existing_credit_relationships": []},
    }
    document = docx.Document(io.BytesIO(build_mb01a_docx(case)))
    t = document.tables[0]
    xml = t.rows[128].cells[25]._tc.xml  # "Chưa có" box checked
    assert 'w:default w:val="1"' in xml
