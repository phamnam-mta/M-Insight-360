"""Bước 0C — the single place a BCTC-field regex search is ever run against
extracted tables. Every other module (financial_inputs.py, the overview
condition evaluators) reads a CanonicalField already built here, never
re-extracts from raw documents. See docs/superpowers/specs/
2026-09-23-eb-agent-v2.4-canonical-design.md."""

import re
import unicodedata
from dataclasses import dataclass, field

from app.engine.core.numbers import parse_vn_number
from app.engine.core.types import EvidenceRef
from app.extraction.evidence_search import find_all_matches_by_period
from app.extraction.types import ExtractedDocument, ExtractedTable

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
    # Internal fields (no H4 instruction code): ported verbatim from the old
    # financial_inputs.py._FIELD_PATTERNS so repayment_capacity.py,
    # profitability.py, stress_test.py, dsp_reconciliation.py and
    # capital_structure.py keep receiving real values through
    # financial_inputs_by_period instead of silently going to None.
    "_REVENUE_BCTC": re.compile(r"doanh thu thuan[:\s]*(-?[\d.,]+)"),
    "_REVENUE_DSP": re.compile(r"doanh thu (?:digisale|dsp)[:\s]*(-?[\d.,]+)"),
    "_INTEREST_DUE": re.compile(r"lai den han[:\s]*(-?[\d.,]+)"),
    "_EBIT": re.compile(r"ebit\)?[:\s]*(-?[\d.,]+)"),
    "_FINANCE_LEASE_DEBT": re.compile(r"no thue tai chinh[:\s]*(-?[\d.,]+)"),
    "_TOTAL_PRINCIPAL_DUE": re.compile(r"no goc den han[:\s]*(-?[\d.,]+)"),
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
    "_REVENUE_BCTC": "revenue_bctc_vnd",
    "_REVENUE_DSP": "revenue_dsp_vnd",
    "_INTEREST_DUE": "interest_due_vnd",
    "_EBIT": "ebit_vnd",
    "_FINANCE_LEASE_DEBT": "finance_lease_debt_vnd",
    "_TOTAL_PRINCIPAL_DUE": "total_principal_due_vnd",
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


_LABELS_VN: dict[str, str] = {
    "IS_REVENUE": "Doanh thu thuần",
    "IS_COGS": "Giá vốn hàng bán",
    "IS_GROSS_PROFIT": "Lợi nhuận gộp",
    "IS_PBT": "Lợi nhuận trước thuế",
    "IS_PAT": "Lợi nhuận sau thuế",
    "IS_INTEREST": "Chi phí lãi vay",
    "IS_DEPRECIATION": "Khấu hao",
    "BS_CURRENT_ASSETS": "Tài sản ngắn hạn",
    "BS_CURRENT_LIABILITIES": "Nợ ngắn hạn",
    "BS_NON_CURRENT_ASSETS": "Tài sản dài hạn",
    "BS_EQUITY": "Vốn chủ sở hữu",
    "BS_CHARTER_CAPITAL": "Vốn điều lệ",
    "BS_LT_BORROWINGS": "Vay & nợ thuê TC dài hạn",
    "BS_ST_BORROWINGS": "Vay & nợ thuê TC ngắn hạn",
    "BS_TOTAL_LIABILITIES": "Tổng nợ phải trả",
    "BS_AR_CUSTOMER": "Phải thu khách hàng",
    "BS_INVENTORY": "Hàng tồn kho",
    "BS_AP_SUPPLIER": "Phải trả người bán",
    "BS_CASH": "Tiền và tương đương tiền",
    "DEBT_PRINCIPAL_DUE": "Nợ gốc đến hạn",
    "CFO": "Lưu chuyển tiền thuần từ HĐKD",
}


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


def _filtered_document(doc: ExtractedDocument, included_tables: list[ExtractedTable]) -> ExtractedDocument:
    """A copy of doc carrying only its BCTC-included sheets/tables — so
    find_all_matches_by_period never sees a bundled sao-kê/notes sheet."""
    text = "\n".join(" | ".join(row) for table in included_tables for row in table.rows)
    return ExtractedDocument(
        filename=doc.filename,
        doc_type=doc.doc_type,
        text=text,
        tables=included_tables,
        extraction_method=doc.extraction_method,
        confidence=doc.confidence,
        warnings=doc.warnings,
        file_id=getattr(doc, "file_id", ""),
        pages=getattr(doc, "pages", None),
    )


def build_canonical(
    documents: list[ExtractedDocument], *, include_all_sheets: bool = False
) -> CanonicalResult:
    """Bước 0C: scan every sheet in every document, classify each one as a
    BCTC source or not, then extract every field exactly once from only the
    included sheets. This is the only place a BCTC-field regex is run —
    financial_inputs.py and the overview condition evaluators read the
    CanonicalField values this produces, never re-search raw documents."""
    sheet_scan: list[SheetScanResult] = []
    included_tables_by_doc: list[tuple[ExtractedDocument, list[ExtractedTable]]] = []

    for doc in documents:
        included_tables: list[ExtractedTable] = []
        for table in doc.tables:
            included, reason = classify_sheet(table)
            if include_all_sheets:
                included, reason = True, "sheets=all — quét toàn bộ theo yêu cầu người dùng"
            sheet_scan.append(SheetScanResult(sheet=table.sheet_or_page, included=included, reason=reason))
            if included:
                included_tables.append(table)
        included_tables_by_doc.append((doc, included_tables))

    # classify_sheet only has sheets to classify when a document HAS tables.
    # A pure-text upload (a PDF/docx BCTC with no table structure at all —
    # e.g. the existing tests' PDF fixtures) has nothing to scan and must
    # pass through unfiltered; only a document whose OWN tables were all
    # classified as non-BCTC (a real bank-statement-only upload) is dropped.
    filtered_documents = []
    for doc, tables in included_tables_by_doc:
        if not doc.tables:
            filtered_documents.append(doc)
        elif tables:
            filtered_documents.append(_filtered_document(doc, tables))

    fields_by_year: dict[str, dict[str, CanonicalField]] = {}
    conflicts: list[dict] = []

    for ma, pattern in _FIELD_PATTERNS.items():
        matches = find_all_matches_by_period(filtered_documents, pattern)
        by_year_raw: dict[str, list[tuple]] = {}
        for ref, raw, year, confidence in matches:
            by_year_raw.setdefault(year, []).append((ref, raw, confidence))

        for year, refs_and_raw in by_year_raw.items():
            distinct_values = {round(parse_vn_number(raw), 6) for _, raw, _ in refs_and_raw}
            refs = [ref for ref, _, _ in refs_and_raw]
            year_fields = fields_by_year.setdefault(year, {})
            if len(distinct_values) > 1:
                conflicts.append({
                    "chi_tieu": _LABELS_VN.get(ma, ma),
                    "gia_tri": sorted(distinct_values),
                    "nam": year,
                })
                year_fields[ma] = CanonicalField(
                    ma=ma,
                    nhan=_LABELS_VN.get(ma, ma),
                    gia_tri=None,
                    don_vi="VND",
                    nam=year,
                    nguon=None,
                    sheet=None,
                    loai="chua_co",
                    co_gia_tri=False,
                    evidence=refs,
                )
            else:
                value = parse_vn_number(refs_and_raw[0][1])
                sheet = refs[0].location.split("'")[1] if "'" in refs[0].location else None
                year_fields[ma] = CanonicalField(
                    ma=ma,
                    nhan=_LABELS_VN.get(ma, ma),
                    gia_tri=value,
                    don_vi="VND",
                    nam=year,
                    nguon=refs[0].original_text,
                    sheet=sheet,
                    loai="trich_xuat" if refs_and_raw[0][2] == "explicit" else "uoc_tinh",
                    co_gia_tri=True,
                    evidence=refs,
                )

    consistency = ConsistencyResult(khop=len(conflicts) == 0, danh_sach_lech=conflicts)
    return CanonicalResult(fields_by_year=fields_by_year, sheet_scan=sheet_scan, consistency=consistency)
