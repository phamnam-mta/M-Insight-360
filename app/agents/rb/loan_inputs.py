import re
from dataclasses import dataclass

from app.extraction.types import ExtractedDocument


@dataclass
class RbLoanInputs:
    avg_monthly_revenue_vnd: float | None = None
    eligible_income_margin: float = 0.08  # demo default per spec §5 worked example
    gross_monthly_income_vnd: float | None = None
    existing_monthly_obligation_vnd: float | None = None
    loan_amount_vnd: float | None = None
    tenor_months: int | None = None
    annual_rate: float | None = None
    collateral_value_vnd: float | None = None


def _to_number(raw: str) -> float:
    """Parse a US-style formatted number: ',' as thousands separator,
    '.' (if present, with no comma before it) as the decimal point.
    e.g. "450,000,000" -> 450000000.0 ; "22.5" -> 22.5
    """
    cleaned = raw.strip().replace(",", "")
    return float(cleaned)


_LOAN_AMOUNT_RE = re.compile(
    r"(?:so tien de nghi vay|de nghi vay|so tien vay)[:\s]*([\d.,]+)", re.IGNORECASE
)
# Require a colon before the number so leading digits in surrounding text
# (e.g. "binh quan 6 thang:") aren't mistaken for the revenue figure itself.
_REVENUE_RE = re.compile(
    r"doanh thu[^:\n]{0,60}:\s*([\d.,]+)\s*(?:vnd|vn[dđ]|đồng)?", re.IGNORECASE
)
_TENOR_RE = re.compile(r"(?:thoi han vay|thời hạn vay|ky han)[:\s]*(\d+)\s*th[aá]ng", re.IGNORECASE)
_RATE_RE = re.compile(r"lai suat[:\s]*([\d.,]+)\s*%", re.IGNORECASE)
_EXISTING_OBLIGATION_RE = re.compile(
    r"nghia vu tra no hien tai[^\d]{0,20}([\d.,]+)", re.IGNORECASE
)


def _strip_accents_lower(text: str) -> str:
    import unicodedata

    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(c for c in normalized if not unicodedata.combining(c))
    return ascii_text.lower()


def extract_loan_inputs(documents: list[ExtractedDocument]) -> RbLoanInputs:
    combined = "\n".join(doc.text for doc in documents)
    haystack = _strip_accents_lower(combined)
    inputs = RbLoanInputs()

    m = _LOAN_AMOUNT_RE.search(haystack)
    if m:
        inputs.loan_amount_vnd = _to_number(m.group(1))

    m = _REVENUE_RE.search(haystack)
    if m:
        inputs.avg_monthly_revenue_vnd = _to_number(m.group(1))

    m = _TENOR_RE.search(haystack)
    if m:
        inputs.tenor_months = int(m.group(1))

    m = _RATE_RE.search(haystack)
    if m:
        inputs.annual_rate = _to_number(m.group(1)) / 100.0

    m = _EXISTING_OBLIGATION_RE.search(haystack)
    if m:
        inputs.existing_monthly_obligation_vnd = _to_number(m.group(1))

    return inputs
