import re
import unicodedata
from dataclasses import dataclass, field
from typing import Literal

from app.engine.core.numbers import parse_vn_number
from app.engine.core.types import EvidenceRef
from app.extraction.evidence_search import find_all_matches, find_all_matches_by_period
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
    principal_due_vnd: float | None = None
    interest_due_vnd: float | None = None
    ebit_vnd: float | None = None
    interest_expense_vnd: float | None = None
    net_revenue_vnd: float | None = None
    pbt_vnd: float | None = None
    pat_vnd: float | None = None
    depreciation_vnd: float | None = None
    non_current_assets_vnd: float | None = None
    long_term_debt_vnd: float | None = None
    finance_lease_debt_vnd: float | None = None
    receivables_vnd: float | None = None
    inventory_vnd: float | None = None
    payables_vnd: float | None = None
    cash_vnd: float | None = None
    total_principal_due_vnd: float | None = None
    cogs_vnd: float | None = None
    charter_capital_vnd: float | None = None


@dataclass
class FieldEvidence:
    status: Literal["COMPUTED", "PENDING_REVIEW", "MISSING_DATA"]
    evidence: list[EvidenceRef] = field(default_factory=list)


def _strip_accents_lower(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(c for c in normalized if not unicodedata.combining(c))
    return ascii_text.lower()


def _to_number(raw: str) -> float:
    """Parse a balance-sheet figure via the shared VN-locale parser."""
    return parse_vn_number(raw)


_FIELD_PATTERNS: dict[str, re.Pattern] = {
    "equity_vnd": re.compile(r"von chu so huu[:\s]*(-?[\d.,]+)"),
    "current_assets_vnd": re.compile(r"tai san ngan han[:\s]*(-?[\d.,]+)"),
    "current_liabilities_vnd": re.compile(r"no ngan han[:\s]*(-?[\d.,]+)"),
    "cfo_vnd": re.compile(r"luu chuyen tien thuan tu hoat dong kinh doanh[:\s]*(-?[\d.,]+)"),
    "short_term_debt_vnd": re.compile(r"vay ngan han[:\s]*(-?[\d.,]+)"),
    "total_liabilities_vnd": re.compile(r"tong no phai tra[:\s]*(-?[\d.,]+)"),
    "revenue_bctc_vnd": re.compile(r"doanh thu thuan[:\s]*(-?[\d.,]+)"),
    "revenue_dsp_vnd": re.compile(r"doanh thu (?:digisale|dsp)[:\s]*(-?[\d.,]+)"),
    "principal_due_vnd": re.compile(r"goc den han[:\s]*(-?[\d.,]+)"),
    "interest_due_vnd": re.compile(r"lai den han[:\s]*(-?[\d.,]+)"),
    "ebit_vnd": re.compile(r"ebit\)?[:\s]*(-?[\d.,]+)"),
    "interest_expense_vnd": re.compile(r"chi phi lai vay[:\s]*(-?[\d.,]+)"),
    "net_revenue_vnd": re.compile(r"doanh thu thuan[:\s]*(-?[\d.,]+)"),
    "pbt_vnd": re.compile(r"loi nhuan truoc thue[:\s]*(-?[\d.,]+)"),
    "pat_vnd": re.compile(r"loi nhuan sau thue[:\s]*(-?[\d.,]+)"),
    "depreciation_vnd": re.compile(r"khau hao[:\s]*(-?[\d.,]+)"),
    "non_current_assets_vnd": re.compile(r"tai san dai han[:\s]*(-?[\d.,]+)"),
    "long_term_debt_vnd": re.compile(r"no dai han[:\s]*(-?[\d.,]+)"),
    "finance_lease_debt_vnd": re.compile(r"no thue tai chinh[:\s]*(-?[\d.,]+)"),
    "receivables_vnd": re.compile(r"phai thu khach hang[:\s]*(-?[\d.,]+)"),
    "inventory_vnd": re.compile(r"hang ton kho[:\s]*(-?[\d.,]+)"),
    "payables_vnd": re.compile(r"phai tra nguoi ban[:\s]*(-?[\d.,]+)"),
    "cash_vnd": re.compile(r"tien va tuong duong tien[:\s]*(-?[\d.,]+)"),
    "total_principal_due_vnd": re.compile(r"no goc den han[:\s]*(-?[\d.,]+)"),
    "cogs_vnd": re.compile(r"gia von hang ban[:\s]*(-?[\d.,]+)"),
    "charter_capital_vnd": re.compile(r"von dieu le[:\s]*(-?[\d.,]+)"),
}


def extract_financial_inputs(
    documents: list[ExtractedDocument],
) -> tuple[EbFinancialInputs, dict[str, FieldEvidence]]:
    values: dict[str, float] = {}
    evidence: dict[str, FieldEvidence] = {}
    for field_name, pattern in _FIELD_PATTERNS.items():
        matches = find_all_matches(documents, pattern)
        if not matches:
            evidence[field_name] = FieldEvidence(status="MISSING_DATA", evidence=[])
            continue
        distinct_values = {round(_to_number(raw), 6) for _, raw in matches}
        refs = [ref for ref, _ in matches]
        if len(distinct_values) == 1:
            values[field_name] = _to_number(matches[0][1])
            evidence[field_name] = FieldEvidence(status="COMPUTED", evidence=refs)
        else:
            evidence[field_name] = FieldEvidence(status="PENDING_REVIEW", evidence=refs)
    return EbFinancialInputs(**values), evidence


@dataclass
class PeriodExtraction:
    year: str
    inputs: EbFinancialInputs
    field_evidence: dict[str, FieldEvidence]


def extract_period_aware_financial_inputs(
    documents: list[ExtractedDocument],
) -> dict[str, PeriodExtraction]:
    by_year_values: dict[str, dict[str, float]] = {}
    by_year_evidence: dict[str, dict[str, FieldEvidence]] = {}

    for field_name, pattern in _FIELD_PATTERNS.items():
        matches = find_all_matches_by_period(documents, pattern)
        by_year_raw: dict[str, list[tuple]] = {}
        for ref, raw, year, _confidence in matches:
            by_year_raw.setdefault(year, []).append((ref, raw))

        for year, refs_and_raw in by_year_raw.items():
            values = {round(_to_number(raw), 6) for _, raw in refs_and_raw}
            refs = [ref for ref, _ in refs_and_raw]
            year_evidence = by_year_evidence.setdefault(year, {})
            year_values = by_year_values.setdefault(year, {})
            if len(values) == 1:
                year_values[field_name] = _to_number(refs_and_raw[0][1])
                year_evidence[field_name] = FieldEvidence(status="COMPUTED", evidence=refs)
            else:
                year_evidence[field_name] = FieldEvidence(status="PENDING_REVIEW", evidence=refs)

    result: dict[str, PeriodExtraction] = {}
    for year in by_year_values:
        for field_name in _FIELD_PATTERNS:
            by_year_evidence[year].setdefault(field_name, FieldEvidence(status="MISSING_DATA", evidence=[]))
        result[year] = PeriodExtraction(
            year=year,
            inputs=EbFinancialInputs(**by_year_values[year]),
            field_evidence=by_year_evidence[year],
        )
    return result
