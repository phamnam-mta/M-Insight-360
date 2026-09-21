from app.extraction.types import ExtractedDocument
from app.agents.rb.loan_inputs import extract_loan_inputs


def _doc(text: str) -> ExtractedDocument:
    return ExtractedDocument(
        filename="f.pdf", doc_type="pdf", text=text, tables=[],
        extraction_method="text_layer", confidence=1.0,
    )


def test_extracts_loan_amount():
    docs = [_doc("So tien de nghi vay: 450,000,000 VND")]
    inputs = extract_loan_inputs(docs)
    assert inputs.loan_amount_vnd == 450_000_000


def test_extracts_revenue():
    docs = [_doc("Doanh thu binh quan 6 thang: 2,919,000,000 VND/thang")]
    inputs = extract_loan_inputs(docs)
    assert inputs.avg_monthly_revenue_vnd == 2_919_000_000


def test_extracts_tenor_months():
    docs = [_doc("Thoi han vay: 48 thang")]
    inputs = extract_loan_inputs(docs)
    assert inputs.tenor_months == 48


def test_extracts_annual_rate_percent():
    docs = [_doc("Lai suat: 22.5%/nam")]
    inputs = extract_loan_inputs(docs)
    assert inputs.annual_rate == 0.225


def test_extracts_existing_monthly_obligation():
    docs = [_doc("Nghia vu tra no hien tai hang thang: 35,000,000 VND")]
    inputs = extract_loan_inputs(docs)
    assert inputs.existing_monthly_obligation_vnd == 35_000_000


def test_missing_fields_are_none_not_zero():
    docs = [_doc("Tai lieu khong lien quan gi den vay von")]
    inputs = extract_loan_inputs(docs)
    assert inputs.loan_amount_vnd is None
    assert inputs.avg_monthly_revenue_vnd is None
    assert inputs.tenor_months is None
    assert inputs.annual_rate is None
    assert inputs.existing_monthly_obligation_vnd is None


def test_extracts_loan_amount_with_vn_locale_thousands_separator():
    # Regression: "450.000.000" (VN locale, "." as thousands separator) used to
    # raise ValueError out of _to_number, surfacing as an HTTP 500 on
    # POST /api/rb/assess for an entirely ordinary Vietnamese loan request.
    docs = [_doc("So tien de nghi vay: 450.000.000 VND")]
    inputs = extract_loan_inputs(docs)
    assert inputs.loan_amount_vnd == 450_000_000


def test_extracts_revenue_with_vn_locale_thousands_separator():
    docs = [_doc("Doanh thu binh quan 6 thang: 2.919.000.000 VND/thang")]
    inputs = extract_loan_inputs(docs)
    assert inputs.avg_monthly_revenue_vnd == 2_919_000_000
