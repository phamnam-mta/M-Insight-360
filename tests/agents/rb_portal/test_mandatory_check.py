from app.agents.rb_portal.mandatory_check import check_mandatory


def test_all_sections_missing_reports_full_checklist():
    result = check_mandatory(customer=None, legal=None, income=None, loan=None, documents=[])
    assert "legal_identity" in result["legal"]
    assert "loan_request" in result["loan"]
    assert result["tax_declaration_required"] is None
    assert result["tax_declaration_present"] is False
    assert result["missing"]  # non-empty


def test_tax_declaration_required_for_business_income_without_document():
    result = check_mandatory(
        customer={"full_name": "A"}, legal={"id_type": "CCCD"},
        income={"source_type": "business", "tax_declaration_present": False},
        loan={"product": "vay_von", "purpose": "kinh doanh"}, documents=[],
    )
    assert result["tax_declaration_required"] is True
    assert result["tax_declaration_present"] is False
    assert "tax_declaration" in result["income"]
    assert "tax_declaration" in result["missing"]


def test_tax_declaration_not_required_for_salary_income():
    result = check_mandatory(
        customer={"full_name": "A"}, legal={"id_type": "CCCD"},
        income={"source_type": "salary"},
        loan={"product": "vay_von", "purpose": "tieu dung"}, documents=[],
    )
    assert result["tax_declaration_required"] is False
    assert "tax_declaration" not in result["income"]


def test_tax_declaration_satisfied_when_present_flag_true():
    result = check_mandatory(
        customer={"full_name": "A"}, legal={"id_type": "CCCD"},
        income={"source_type": "household_business", "tax_declaration_present": True},
        loan={"product": "vay_von", "purpose": "x"}, documents=[],
    )
    assert result["tax_declaration_required"] is True
    assert result["tax_declaration_present"] is True
    assert "tax_declaration" not in result["income"]
    assert "tax_declaration" not in result["missing"]


def test_fully_filled_case_has_empty_missing_list():
    result = check_mandatory(
        customer={"full_name": "A"}, legal={"id_type": "CCCD"},
        income={"source_type": "salary", "employer_name": "Cong ty B"},
        loan={"product": "vay_von", "purpose": "tieu dung", "amount_vnd": 100_000_000},
        documents=[],
    )
    assert result["missing"] == []
    assert result["legal"] == []
    assert result["income"] == []
    assert result["loan"] == []
