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


def test_loan_amount_fills_only_the_amount_column_not_total_capital_need():
    # Row 84's header row confirms cell 32 = "Tổng nhu cầu vốn" (a quantity the
    # RB Portal never collects) and cell 47 = "Số tiền cấp tín dụng" (amount_vnd).
    # Writing amount_vnd into both, as an earlier version of this code did,
    # fabricates a "total capital need" figure that was never entered.
    case = {
        "customer": None, "legal": None, "income": None,
        "loan": {"product": "Vay vốn", "purpose": "Bổ sung vốn kinh doanh",
                   "amount_vnd": 200_000_000, "tenor_months": 24},
        "collateral": None, "other": None,
    }
    document = docx.Document(io.BytesIO(build_mb01a_docx(case)))
    t = document.tables[0]
    assert "Vay vốn" in t.rows[85].cells[2].text
    assert "Bổ sung vốn kinh doanh" in t.rows[85].cells[12].text
    assert t.rows[85].cells[32].text == ""  # "Tổng nhu cầu vốn" left blank, never collected
    assert "200000000" in t.rows[85].cells[47].text  # "Số tiền cấp tín dụng"


def test_collateral_rows_filled():
    case = {
        "customer": None, "legal": None, "income": None, "loan": None,
        "collateral": {"items": [
            {"asset_type": "Bất động sản", "estimated_value_vnd": 800_000_000},
            {"asset_type": "Ô tô", "estimated_value_vnd": 500_000_000},
        ]},
        "other": None,
    }
    document = docx.Document(io.BytesIO(build_mb01a_docx(case)))
    t = document.tables[0]
    assert "Bất động sản" in t.rows[124].cells[1].text
    assert "Ô tô" in t.rows[125].cells[1].text


def test_credit_relationships_fill_the_data_rows_without_asserting_msb_status():
    # Row 128's checkbox specifically asks "Quan hệ tín dụng VỚI MSB" — the RB
    # Portal's other-tab data (institution/credit_type/outstanding/monthly_payment)
    # never records whether a given relationship is at MSB specifically, so
    # checking either "Đã/đang có ... tại MSB" or "Chưa có" would assert a fact
    # not actually known — left unchecked (never fabricate). The data rows
    # (131/132, confirmed 2 pre-drawn in the template) still get filled: row
    # 129 explicitly scopes them to "MSB VÀ CÁC TỔ CHỨC TÍN DỤNG KHÁC".
    case = {
        "customer": None, "legal": None, "income": None, "loan": None, "collateral": None,
        "other": {"existing_credit_relationships": [
            {"institution": "Vietcombank", "credit_type": "Vay tiêu dùng", "outstanding_vnd": 50_000_000},
            {"institution": "BIDV", "credit_type": "Vay thế chấp", "outstanding_vnd": 300_000_000},
        ]},
    }
    document = docx.Document(io.BytesIO(build_mb01a_docx(case)))
    t = document.tables[0]
    assert "Vietcombank" in t.rows[131].cells[0].text
    assert "BIDV" in t.rows[132].cells[0].text
    assert "300000000" in t.rows[132].cells[42].text
    xml_msb = t.rows[128].cells[41]._tc.xml
    xml_none = t.rows[128].cells[25]._tc.xml
    assert 'w:default w:val="1"' not in xml_msb
    assert 'w:default w:val="1"' not in xml_none


def test_no_existing_credit_relationship_leaves_msb_checkboxes_unchecked():
    case = {
        "customer": None, "legal": None, "income": None, "loan": None, "collateral": None,
        "other": {"existing_credit_relationships": []},
    }
    document = docx.Document(io.BytesIO(build_mb01a_docx(case)))
    t = document.tables[0]
    xml_msb = t.rows[128].cells[41]._tc.xml
    xml_none = t.rows[128].cells[25]._tc.xml
    assert 'w:default w:val="1"' not in xml_msb
    assert 'w:default w:val="1"' not in xml_none


def test_employment_years_writes_correct_text_without_garbling_the_label():
    # Row 37's run layout differs from row 25's (business years) — reusing
    # row 25's run indices (10/13) here corrupted the label text, since run 10
    # in row 37 is "tại" (part of "làm việc tại cơ quan") and run 13 is a bare
    # space, not the "năm"/"tháng" placeholders (those are runs 18 and 22).
    case = {
        "customer": None, "legal": None,
        "income": {"source_type": "salary", "employment_years": 3.5},
        "loan": None, "collateral": None, "other": None,
    }
    document = docx.Document(io.BytesIO(build_mb01a_docx(case)))
    t = document.tables[0]
    text = t.rows[37].cells[0].text
    assert "tại cơ quan" in text  # label must stay intact, not "tại6  quan"
    assert "3 năm" in text
    assert "6 tháng" in text


def test_business_years_still_writes_correct_text():
    case = {
        "customer": None, "legal": None,
        "income": {"source_type": "business", "business_years": 2.25},
        "loan": None, "collateral": None, "other": None,
    }
    document = docx.Document(io.BytesIO(build_mb01a_docx(case)))
    t = document.tables[0]
    text = t.rows[25].cells[0].text
    assert "2 năm" in text
    assert "3 tháng" in text


def test_customer_nationality_and_phones_and_legal_issue_place_are_exported():
    case = {
        "customer": {
            "nationality": "Việt Nam", "phone_home": "02412345", "phone_mobile": "0912345678",
        },
        "legal": {"id_issue_place": "Cục Cảnh sát QLHC về TTXH"},
        "income": None, "loan": None, "collateral": None, "other": None,
    }
    document = docx.Document(io.BytesIO(build_mb01a_docx(case)))
    t = document.tables[0]
    assert "Việt Nam" in t.rows[4].cells[31].text
    assert "02412345" in t.rows[12].cells[0].text
    assert "0912345678" in t.rows[12].cells[31].text
    assert "Cục Cảnh sát QLHC về TTXH" in t.rows[5].cells[31].text
