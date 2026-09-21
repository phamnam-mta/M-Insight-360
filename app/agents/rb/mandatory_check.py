MANDATORY_DOC_TYPES = ["LEGAL_IDENTITY", "BANK_STATEMENT", "LOAN_REQUEST"]


def check_mandatory_documents(classified: list[tuple[str, float]]) -> dict:
    present_types = {doc_type for doc_type, _ in classified}
    present_mandatory = sorted(present_types & set(MANDATORY_DOC_TYPES))
    missing = [t for t in MANDATORY_DOC_TYPES if t not in present_types]
    return {
        "required": list(MANDATORY_DOC_TYPES),
        "present": present_mandatory,
        "missing": missing,
    }
