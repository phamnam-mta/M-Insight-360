_BUSINESS_SOURCE_TYPES = {"business", "self_employed", "household_business"}


def check_mandatory(
    customer: dict | None, legal: dict | None, income: dict | None,
    loan: dict | None, documents: list[dict],
) -> dict:
    legal_missing: list[str] = []
    if not customer or not customer.get("full_name"):
        legal_missing.append("legal_identity")
    if not legal or not legal.get("id_type"):
        legal_missing.append("id_document")

    income_missing: list[str] = []
    tax_declaration_required: bool | None
    tax_declaration_present = bool(income and income.get("tax_declaration_present"))
    if income is None:
        income_missing.append("income_section")
        tax_declaration_required = None
    else:
        source_type = income.get("source_type")
        if not source_type:
            income_missing.append("income_source_type")
        tax_declaration_required = source_type in _BUSINESS_SOURCE_TYPES
        if tax_declaration_required and not tax_declaration_present:
            income_missing.append("tax_declaration")

    loan_missing: list[str] = []
    if not loan or not loan.get("product"):
        loan_missing.append("loan_request")
    if not loan or not loan.get("purpose"):
        loan_missing.append("loan_purpose")

    other_missing: list[str] = []

    missing = legal_missing + income_missing + loan_missing + other_missing
    return {
        "legal": legal_missing,
        "income": income_missing,
        "loan": loan_missing,
        "other": other_missing,
        "tax_declaration_required": tax_declaration_required,
        "tax_declaration_present": tax_declaration_present,
        "missing": missing,
    }
