"""Bước 0C — the single place a BCTC-field regex search is ever run against
extracted tables. Every other module (financial_inputs.py, the overview
condition evaluators) reads a CanonicalField already built here, never
re-extracts from raw documents. See docs/superpowers/specs/
2026-09-23-eb-agent-v2.4-canonical-design.md."""

import re
import unicodedata
from dataclasses import dataclass, field

from app.engine.core.types import EvidenceRef
from app.extraction.types import ExtractedTable

# Moved here from financial_inputs.py (was duplicated independently by every
# overview/*.py BCTC-numeric condition before this refactor — H4).
_FIELD_PATTERNS: dict[str, re.Pattern] = {
    "IS_REVENUE": re.compile(r"doanh thu thuan[:\s]*(-?[\d.,]+)"),
    "IS_COGS": re.compile(r"gia von hang ban[:\s]*(-?[\d.,]+)"),
    "IS_GROSS_PROFIT": re.compile(r"loi nhuan gop[:\s]*(-?[\d.,]+)"),
    "IS_PBT": re.compile(r"loi nhuan truoc thue[:\s]*(-?[\d.,]+)"),
    "IS_PAT": re.compile(r"loi nhuan sau thue[:\s]*(-?[\d.,]+)"),
    "IS_INTEREST": re.compile(r"chi phi lai vay[:\s]*(-?[\d.,]+)"),
    "IS_DEPRECIATION": re.compile(r"khau hao[:\s]*(-?[\d.,]+)"),
    "BS_CURRENT_ASSETS": re.compile(r"tai san ngan han[:\s]*(-?[\d.,]+)"),
    "BS_CURRENT_LIABILITIES": re.compile(r"no ngan han[:\s]*(-?[\d.,]+)"),
    "BS_NON_CURRENT_ASSETS": re.compile(r"tai san dai han[:\s]*(-?[\d.,]+)"),
    "BS_EQUITY": re.compile(r"von chu so huu[:\s]*(-?[\d.,]+)"),
    "BS_CHARTER_CAPITAL": re.compile(r"von dieu le[:\s]*(-?[\d.,]+)"),
    "BS_LT_BORROWINGS": re.compile(r"no dai han[:\s]*(-?[\d.,]+)"),
    "BS_ST_BORROWINGS": re.compile(r"vay ngan han[:\s]*(-?[\d.,]+)"),
    "BS_TOTAL_LIABILITIES": re.compile(r"tong no phai tra[:\s]*(-?[\d.,]+)"),
    "BS_AR_CUSTOMER": re.compile(r"phai thu khach hang[:\s]*(-?[\d.,]+)"),
    "BS_INVENTORY": re.compile(r"hang ton kho[:\s]*(-?[\d.,]+)"),
    "BS_AP_SUPPLIER": re.compile(r"phai tra nguoi ban[:\s]*(-?[\d.,]+)"),
    "BS_CASH": re.compile(r"tien va tuong duong tien[:\s]*(-?[\d.,]+)"),
    "DEBT_PRINCIPAL_DUE": re.compile(r"no goc den han[:\s]*(-?[\d.,]+)"),
    "CFO": re.compile(r"luu chuyen tien thuan tu hoat dong kinh doanh[:\s]*(-?[\d.,]+)"),
}

# ma -> EbFinancialInputs attribute name (or None when the field has no
# direct dataclass counterpart, e.g. purely-computed CALC_* codes).
FIELD_CODE_MAP: dict[str, str | None] = {
    "IS_REVENUE": "net_revenue_vnd",
    "IS_COGS": "cogs_vnd",
    "IS_GROSS_PROFIT": "gross_profit_vnd",
    "IS_PBT": "pbt_vnd",
    "IS_PAT": "pat_vnd",
    "IS_INTEREST": "interest_expense_vnd",
    "IS_DEPRECIATION": "depreciation_vnd",
    "BS_CURRENT_ASSETS": "current_assets_vnd",
    "BS_CURRENT_LIABILITIES": "current_liabilities_vnd",
    "BS_NON_CURRENT_ASSETS": "non_current_assets_vnd",
    "BS_TOTAL_ASSETS": None,
    "BS_EQUITY": "equity_vnd",
    "BS_CHARTER_CAPITAL": "charter_capital_vnd",
    "BS_LT_LIABILITIES": None,
    "BS_LT_BORROWINGS": "long_term_debt_vnd",
    "BS_ST_BORROWINGS": "short_term_debt_vnd",
    "BS_TOTAL_LIABILITIES": "total_liabilities_vnd",
    "BS_AR_CUSTOMER": "receivables_vnd",
    "BS_INVENTORY": "inventory_vnd",
    "BS_AP_SUPPLIER": "payables_vnd",
    "BS_CASH": "cash_vnd",
    "DEBT_PRINCIPAL_DUE": "principal_due_vnd",
    "CFO": "cfo_vnd",
}

LEGACY_ALIAS: dict[str, str] = {
    "BS003": "BS_AR_CUSTOMER",
    "BS004": "BS_INVENTORY",
    "BS005": "BS_AP_SUPPLIER",
    "BS008": "BS_EQUITY",
    "DEBT_LT_PRINCIPAL_DUE": "DEBT_PRINCIPAL_DUE",
}

_BCTC_SHEET_NAME_MARKERS = (
    "bctc", "cdkt", "kqkd", "lctt", "can doi ke toan", "ket qua kinh doanh",
    "luu chuyen tien te", "tom tat",
)
_MIN_CONTENT_HITS_FOR_INCLUSION = 3


@dataclass
class CanonicalField:
    ma: str
    nhan: str
    gia_tri: float | None
    don_vi: str
    nam: str | None
    nguon: str | None
    sheet: str | None
    loai: str  # "trich_xuat" | "fallback" | "uoc_tinh" | "tinh_toan" | "chua_co"
    co_gia_tri: bool
    evidence: list[EvidenceRef] = field(default_factory=list)


@dataclass
class SheetScanResult:
    sheet: str
    included: bool
    reason: str


@dataclass
class ConsistencyResult:
    khop: bool = True
    danh_sach_lech: list[dict] = field(default_factory=list)


@dataclass
class CanonicalResult:
    fields_by_year: dict[str, dict[str, CanonicalField]] = field(default_factory=dict)
    sheet_scan: list[SheetScanResult] = field(default_factory=list)
    consistency: ConsistencyResult = field(default_factory=ConsistencyResult)


def _strip_accents_lower(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(c for c in normalized if not unicodedata.combining(c)).lower()


def classify_sheet(table: ExtractedTable) -> tuple[bool, str]:
    """(included, reason). A sheet is included as a BCTC source if its own
    name matches a known BCTC naming pattern, OR its own content clears a
    keyword-density threshold against _FIELD_PATTERNS — content wins when
    the name is inconclusive (a terse, unusually-named real BCTC sheet
    must not be excluded just because its title doesn't say "BCTC")."""
    name_stripped = _strip_accents_lower(table.sheet_or_page)
    if any(marker in name_stripped for marker in _BCTC_SHEET_NAME_MARKERS):
        return True, f"Tên sheet khớp mẫu BCTC ({table.sheet_or_page})"

    haystack = _strip_accents_lower(" ".join(" ".join(row) for row in table.rows))
    hits = sum(1 for pattern in _FIELD_PATTERNS.values() if pattern.search(haystack))
    if hits >= _MIN_CONTENT_HITS_FOR_INCLUSION:
        return True, f"Nội dung khớp {hits} chỉ tiêu BCTC chuẩn"

    return False, "Không khớp tên sheet BCTC và nội dung không đạt ngưỡng chỉ tiêu tài chính"
