from app.agents.rb.mandatory_check import check_mandatory_documents


def test_all_mandatory_present():
    classified = [("LEGAL_IDENTITY", 0.9), ("BANK_STATEMENT", 0.8), ("LOAN_REQUEST", 0.7)]
    result = check_mandatory_documents(classified)
    assert result["missing"] == []


def test_reports_missing_documents():
    classified = [("LEGAL_IDENTITY", 0.9)]
    result = check_mandatory_documents(classified)
    assert set(result["missing"]) == {"BANK_STATEMENT", "LOAN_REQUEST"}


def test_empty_upload_is_all_missing():
    result = check_mandatory_documents([])
    assert set(result["missing"]) == set(result["required"])
