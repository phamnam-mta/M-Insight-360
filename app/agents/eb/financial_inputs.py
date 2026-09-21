import re
import unicodedata
from dataclasses import dataclass

from app.extraction.types import ExtractedDocument


@dataclass
class EbFinancialInputs:
    equity_vnd: float | None = None
    current_assets_vnd: float | None = None
    current_liabilities_vnd: float | None = None
    cfo_vnd: float | None = None
    short_term_debt_vnd: float | None = None
    total_liabilities_vnd: float | None = None
    revenue_bctc_vnd: float | None = None
    revenue_dsp_vnd: float | None = None
    cfads_vnd: float | None = None
    principal_due_vnd: float | None = None
    interest_due_vnd: float | None = None
    ebit_vnd: float | None = None
    interest_expense_vnd: float | None = None


def _strip_accents_lower(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(c for c in normalized if not unicodedata.combining(c))
    return ascii_text.lower()


def _to_number(raw: str) -> float:
    cleaned = raw.replace(",", "")
    return float(cleaned)


_FIELD_PATTERNS: dict[str, re.Pattern] = {
    "equity_vnd": re.compile(r"von chu so huu[:\s]*(-?[\d,]+)"),
    "current_assets_vnd": re.compile(r"tai san ngan han[:\s]*(-?[\d,]+)"),
    "current_liabilities_vnd": re.compile(r"no ngan han[:\s]*(-?[\d,]+)"),
    "cfo_vnd": re.compile(r"luu chuyen tien thuan tu hoat dong kinh doanh[:\s]*(-?[\d,]+)"),
    "short_term_debt_vnd": re.compile(r"vay ngan han[:\s]*(-?[\d,]+)"),
    "total_liabilities_vnd": re.compile(r"tong no phai tra[:\s]*(-?[\d,]+)"),
    "revenue_bctc_vnd": re.compile(r"doanh thu thuan[:\s]*(-?[\d,]+)"),
    "revenue_dsp_vnd": re.compile(r"doanh thu (?:digisale|dsp)[:\s]*(-?[\d,]+)"),
    "cfads_vnd": re.compile(r"cfads[:\s]*(-?[\d,]+)"),
    "principal_due_vnd": re.compile(r"goc den han[:\s]*(-?[\d,]+)"),
    "interest_due_vnd": re.compile(r"lai den han[:\s]*(-?[\d,]+)"),
    "ebit_vnd": re.compile(r"ebit\)?[:\s]*(-?[\d,]+)"),
    "interest_expense_vnd": re.compile(r"chi phi lai vay[:\s]*(-?[\d,]+)"),
}


def extract_financial_inputs(documents: list[ExtractedDocument]) -> EbFinancialInputs:
    combined = _strip_accents_lower("\n".join(doc.text for doc in documents))
    values: dict[str, float] = {}
    for field, pattern in _FIELD_PATTERNS.items():
        match = pattern.search(combined)
        if match:
            values[field] = _to_number(match.group(1))
    return EbFinancialInputs(**values)
