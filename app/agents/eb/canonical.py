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
from app.extraction.period_columns import detect_table_primary_year, detect_year_columns
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
    # No "no" (Nợ) prefix required, matching the pre-refactor
    # financial_inputs.py._FIELD_PATTERNS["principal_due_vnd"] pattern
    # exactly — "no goc den han" is a strict superset match of "goc den
    # han", so this only ever adds matches, never removes any.
    "DEBT_PRINCIPAL_DUE": re.compile(r"goc den han[:\s]*(-?[\d.,]+)"),
    "CFO": re.compile(r"luu chuyen tien thuan tu hoat dong kinh doanh[:\s]*(-?[\d.,]+)"),
    # Internal fields (no H4 instruction code): ported verbatim from the old
    # financial_inputs.py._FIELD_PATTERNS so repayment_capacity.py,
    # profitability.py, stress_test.py, dsp_reconciliation.py and
    # capital_structure.py keep receiving real values through
    # financial_inputs_by_period instead of silently going to None.
    # revenue_bctc_vnd is NOT a separate pattern here — its regex was
    # byte-identical to IS_REVENUE's; a duplicate pattern would double
    # count as two conflicting-value entries for one real disagreement and
    # inflate classify_sheet's content-hit tally. financial_inputs_by_period
    # mirrors IS_REVENUE's value into revenue_bctc_vnd instead.
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
    "bctc", "cdkt", "kqkd", "kqhdkd", "lctt", "can doi ke toan", "ket qua kinh doanh",
    "ket qua hoat dong kinh doanh", "luu chuyen tien te", "tom tat",
    "bao cao tai chinh", "balance sheet", "income statement",
)

# Mã số → field code, scoped per statement type — verified against a real
# uploaded BCTC (Mẫu B01-DN/B02-DN/B03-DN, Thông tư 200/2014/TT-BTC) this
# session. Mã số is NOT a global key: mã "20" means "Lợi nhuận gộp" in
# KQKD but "Lưu chuyển tiền thuần từ HĐKD" in LCTT, so a table's statement
# type must be known before its Mã số column is trusted. Only fields
# confirmed exact against that real file are listed — mã số varies more
# than commonly assumed between accounting software packages (the same
# file used mã 25/26 for "Chi phí bán hàng"/"Chi phí quản lý doanh
# nghiệp" instead of the more commonly cited 24/25), so an unconfirmed
# guess is worse than falling back to label matching.
_MA_SO_MAP: dict[str, dict[str, str]] = {
    "cdkt": {
        "100": "BS_CURRENT_ASSETS",
        "110": "BS_CASH",
        "131": "BS_AR_CUSTOMER",
        "141": "BS_INVENTORY",
        "200": "BS_NON_CURRENT_ASSETS",
        "300": "BS_TOTAL_LIABILITIES",
        "310": "BS_CURRENT_LIABILITIES",
        "320": "BS_ST_BORROWINGS",
        "338": "BS_LT_BORROWINGS",
        "400": "BS_EQUITY",
        "411": "BS_CHARTER_CAPITAL",
    },
    "kqkd": {
        "10": "IS_REVENUE",
        "11": "IS_COGS",
        "20": "IS_GROSS_PROFIT",
        "23": "IS_INTEREST",
        "50": "IS_PBT",
        "60": "IS_PAT",
    },
    "lctt": {
        "20": "CFO",
    },
}

_STATEMENT_NAME_MARKERS: dict[str, tuple[str, ...]] = {
    "cdkt": ("cdkt", "can doi ke toan", "b01", "bang can doi ke toan", "balance sheet"),
    "kqkd": ("kqkd", "kqhdkd", "ket qua kinh doanh", "ket qua hoat dong kinh doanh", "b02", "income statement"),
    "lctt": ("lctt", "luu chuyen tien te", "b03", "cash flow"),
}
_STATEMENT_CONTENT_MARKERS: dict[str, str] = {
    "cdkt": "tai san ngan han",
    "kqkd": "doanh thu ban hang va cung cap dich vu",
    "lctt": "luu chuyen tien thuan tu hoat dong kinh doanh",
}
_MA_SO_HEADER_LABEL = "ma so"
# 2, not 3 — a real BCTC sheet with a terse, unusually-named title can
# legitimately carry only a couple of the standard line items (Review
# Focus #2); requiring 3 excluded real single-purpose sheets (e.g. a CDKT
# with only 2 populated rows) entirely from canonical extraction.
_MIN_CONTENT_HITS_FOR_INCLUSION = 2


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
    # NFKD has no decomposition for Đ/đ (it isn't a base-letter-plus-
    # combining-mark in Unicode) — without this, sheet names like "CĐKT"
    # or "Bảng cân đối kế toán" never match any BCTC name marker.
    text = text.replace("Đ", "D").replace("đ", "d")
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
    "_REVENUE_DSP": "Doanh thu DigiSale",
    "_INTEREST_DUE": "Lãi đến hạn",
    "_EBIT": "EBIT",
    "_FINANCE_LEASE_DEBT": "Nợ thuê tài chính",
    "_TOTAL_PRINCIPAL_DUE": "Tổng nợ gốc đến hạn",
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


def _detect_statement_type(table: ExtractedTable) -> str | None:
    """Which of CĐKT / KQKD / LCTT a table is — Mã số is only unambiguous
    once this is known (see _MA_SO_MAP's own comment)."""
    name_stripped = _strip_accents_lower(table.sheet_or_page)
    for statement_type, markers in _STATEMENT_NAME_MARKERS.items():
        if any(marker in name_stripped for marker in markers):
            return statement_type

    haystack = _strip_accents_lower(" ".join(" ".join(row) for row in table.rows))
    for statement_type, marker in _STATEMENT_CONTENT_MARKERS.items():
        if marker in haystack:
            return statement_type
    return None


def _find_ma_so_column(header_row: list[str]) -> int | None:
    for i, cell in enumerate(header_row):
        if _strip_accents_lower(cell).strip() == _MA_SO_HEADER_LABEL:
            return i
    return None


def _normalize_ma_so(raw: str) -> str:
    """"10", "10.0" (a numeric xlsx cell stringified with a trailing
    ".0") and " 10 " must all key the same way into _MA_SO_MAP."""
    stripped = raw.strip()
    try:
        return str(int(float(stripped)))
    except ValueError:
        return stripped


def _extract_by_ma_so(
    table: ExtractedTable, statement_type: str, file_id: str, filename: str,
) -> list[tuple[str, EvidenceRef, str, str, str]]:
    """Reads a table's own "Mã số" column to identify each row's field
    code directly — exact and unambiguous, unlike a label regex, which
    can match several different real line items sharing a substring
    (T31/C1: "Hàng tồn kho" mã 141 vs "Dự phòng giảm giá hàng tồn kho" mã
    149 both contain "hàng tồn kho"). Falls back to nothing (never
    raises) when the table has no recognizable header — build_canonical's
    existing label-regex path still covers those tables."""
    ma_so_map = _MA_SO_MAP.get(statement_type)
    if not ma_so_map or not table.rows:
        return []

    header_idx: int | None = None
    ma_so_col: int | None = None
    year_columns: dict[int, str] = {}
    primary_year = detect_table_primary_year(table)
    for idx, row in enumerate(table.rows):
        col = _find_ma_so_column(row)
        if col is None:
            continue
        candidate_years = detect_year_columns(row, primary_year)
        if len(candidate_years) >= 2:
            header_idx, ma_so_col, year_columns = idx, col, candidate_years
            break

    if header_idx is None or ma_so_col is None or not year_columns:
        return []

    results: list[tuple[str, EvidenceRef, str, str, str]] = []
    for row_idx, row in enumerate(table.rows[header_idx + 1 :], start=header_idx + 1):
        if ma_so_col >= len(row):
            continue
        field_code = ma_so_map.get(_normalize_ma_so(row[ma_so_col]))
        if field_code is None:
            continue
        joined = " | ".join(row)
        for col_idx, year in year_columns.items():
            if col_idx >= len(row):
                continue
            cell = row[col_idx]
            if not cell or (parse_vn_number(cell) == 0.0 and not any(ch.isdigit() for ch in cell)):
                continue
            results.append((
                field_code,
                EvidenceRef(
                    file_id=file_id, filename=filename,
                    location=f"Sheet '{table.sheet_or_page}', dòng {row_idx + 1}",
                    original_text=joined, period=year,
                ),
                cell, year, "ma_so",
            ))
    return results


_LOCATION_SHEET_RE = re.compile(r"^Sheet '(.*)', dòng \d+$")


def _sheet_of(ref: EvidenceRef) -> str | None:
    match = _LOCATION_SHEET_RE.match(ref.location)
    return match.group(1) if match else None


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
            if doc.doc_type == "xlsx":
                included, reason = classify_sheet(table)
                if include_all_sheets:
                    included, reason = True, "sheets=all — quét toàn bộ theo yêu cầu người dùng"
            else:
                # The multi-sheet "which sheet is BCTC" question only makes
                # sense for a real xlsx workbook. A CSV always parses into
                # exactly one line-per-row pseudo-table (see xlsx_csv_parser
                # .extract_csv), and a PDF/docx table is part of a single
                # narrative document — there is no "other sheet" to filter
                # against, so classify_sheet's content-density bar (tuned
                # for genuine multi-column BCTC tables) would only silently
                # drop a terse but real upload.
                included, reason = True, "Định dạng tệp không phải workbook nhiều sheet — không áp dụng phân loại sheet"
            sheet_scan.append(SheetScanResult(sheet=table.sheet_or_page, included=included, reason=reason))
            if included:
                included_tables.append(table)
        included_tables_by_doc.append((doc, included_tables))

    # Mã số extraction runs first, directly against each included xlsx
    # table's own rows — exact and unambiguous once a table's statement
    # type (CĐKT/KQKD/LCTT) is known. A field code it resolves for a given
    # sheet is recorded so the label-regex pass below never re-reads that
    # same sheet for that same field — running both on the same sheet
    # would reintroduce exactly the same-sheet-ambiguity problem Mã số
    # extraction exists to avoid (T31/C1).
    ma_so_matches: dict[str, list[tuple]] = {}
    ma_so_resolved_sheets: dict[str, set[str]] = {}
    for doc, tables in included_tables_by_doc:
        if doc.doc_type != "xlsx":
            continue
        file_id = getattr(doc, "file_id", doc.filename)
        for table in tables:
            statement_type = _detect_statement_type(table)
            if statement_type is None:
                continue
            for field_code, ref, raw, year, confidence in _extract_by_ma_so(
                table, statement_type, file_id, doc.filename
            ):
                ma_so_matches.setdefault(field_code, []).append((ref, raw, year, confidence))
                ma_so_resolved_sheets.setdefault(field_code, set()).add(table.sheet_or_page)

    # classify_sheet only has sheets to classify when a document HAS tables.
    # A pure-text upload (a PDF/docx BCTC with no table structure at all —
    # e.g. the existing tests' PDF fixtures) has nothing to scan and must
    # pass through unfiltered; only a document whose OWN tables were all
    # classified as non-BCTC (a real bank-statement-only xlsx upload) is
    # dropped.
    filtered_documents = []
    for doc, tables in included_tables_by_doc:
        if doc.doc_type != "xlsx":
            # Every table in a non-xlsx document is already included
            # unconditionally above — rebuilding `text` from just its
            # tables (via _filtered_document) would silently drop real
            # narrative prose alongside a docx's own tables (a docx BCTC
            # can carry its own figures as text, not only in a table).
            # Pass it through completely unchanged.
            filtered_documents.append(doc)
        elif tables:
            filtered_documents.append(_filtered_document(doc, tables))

    fields_by_year: dict[str, dict[str, CanonicalField]] = {}
    conflicts: list[dict] = []

    for ma, pattern in _FIELD_PATTERNS.items():
        resolved_sheets = ma_so_resolved_sheets.get(ma, set())
        regex_matches = find_all_matches_by_period(filtered_documents, pattern)
        by_year_raw: dict[str, list[tuple]] = {}
        for ref, raw, year, confidence in regex_matches:
            if _sheet_of(ref) in resolved_sheets:
                continue
            by_year_raw.setdefault(year, []).append((ref, raw, confidence))
        for ref, raw, year, confidence in ma_so_matches.get(ma, []):
            by_year_raw.setdefault(year, []).append((ref, raw, confidence))

        for year, refs_and_raw in by_year_raw.items():
            distinct_values = {round(parse_vn_number(raw), 6) for _, raw, _ in refs_and_raw}
            refs = [ref for ref, _, _ in refs_and_raw]
            year_fields = fields_by_year.setdefault(year, {})
            if len(distinct_values) > 1:
                # A field-pattern regex is a label substring match, so two
                # DIFFERENT real line items in the SAME sheet can both hit
                # the same pattern (e.g. "Hàng tồn kho" and "Dự phòng giảm
                # giá hàng tồn kho" both match "hang ton kho") — that is
                # noise from one sheet's own layout, not a real
                # cross-source disagreement, and must never hard-block
                # export. Only flag a genuine LECH_DU_LIEU conflict when
                # the differing values trace back to more than one sheet.
                distinct_sheets = {_sheet_of(ref) for ref in refs}
                if len(distinct_sheets) > 1:
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
                sheet = _sheet_of(refs[0])
                year_fields[ma] = CanonicalField(
                    ma=ma,
                    nhan=_LABELS_VN.get(ma, ma),
                    gia_tri=value,
                    don_vi="VND",
                    nam=year,
                    nguon=refs[0].original_text,
                    sheet=sheet,
                    loai="trich_xuat" if refs_and_raw[0][2] in ("explicit", "ma_so") else "uoc_tinh",
                    co_gia_tri=True,
                    evidence=refs,
                )

    consistency = ConsistencyResult(khop=len(conflicts) == 0, danh_sach_lech=conflicts)
    return CanonicalResult(fields_by_year=fields_by_year, sheet_scan=sheet_scan, consistency=consistency)
