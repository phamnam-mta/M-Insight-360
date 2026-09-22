# EB Screen Redesign + Stress Test v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the EB result screen into a 3-column layout showing a
company's real financial substance (period-aware BCTC data, new metrics,
red flags, QĐ 039 card), and build a full Stress Test v2 module with
scenario persistence.

**Architecture:** Two additive layers on top of the existing EB pipeline.
(1) Period-aware extraction detects which BCTC table column is which
fiscal year and builds one `EbFinancialInputs` per year — every existing
metric/rule function keeps its current flat-dataclass signature, so the
router just picks which year's dataclass to feed them. (2) Stress Test v2
replaces the stateless single-endpoint today with a richer contract plus a
new SQLite table for named scenarios. Frontend gets a 3-column
`EbResultPanel.tsx` and a new `StressTestDrawer.tsx`.

**Tech Stack:** FastAPI + dataclasses (backend), Next.js 14 static export +
Tailwind + lucide-react (frontend), SQLite (`app/storage/db.py`), pytest.
No frontend test runner exists in this repo — frontend tasks verify via
`npx tsc --noEmit`, `npm run build`, and a final Playwright pass instead of
unit tests, matching this repo's established pattern for `web/`.

**Spec:** `docs/superpowers/specs/2026-09-22-eb-screen-redesign-stress-test-design.md`

## Global Constraints

- AI extracts figures only from uploaded BCTC files; never fabricate. A
  missing field renders `"Chưa xác định từ hồ sơ tải lên"` and names the
  missing field.
- Every figure group shows source: filename, kỳ dữ liệu, "AI đã trích
  xuất"/"Người dùng điều chỉnh" provenance.
- Selecting kỳ báo cáo switches all figures/metrics/comments/warnings to
  that year — no year-over-year comparison numbers shown.
- "Nợ thuế", "Mua sắm công", "Trinh sát dữ liệu công khai" are out of
  scope — do not build them.
- "Cơ hội bán chéo" keeps using the existing `crosssell_adapter.py` (4
  rules, no deal size) — only labeling/empty-state changes.
- Every AI-derived result carries "Khuyến nghị sơ bộ từ dữ liệu BCTC — cần
  phê duyệt theo quy trình tín dụng MSB" and is never a final decision.
- MSB visual language: light background, MSB orange for CTAs, green/amber/red
  for good/watch/risk. New thresholds not yet MSB-confirmed keep the
  existing `*_POLICY_VERSION = "policy_mode=DEMO_UAT (...)"` convention.
- Run `/usr/local/bin/python -m pytest -q` (never bare `pytest`) after every
  backend task.

## Review Focus

- BCTC with only one column (no prior-year comparison printed) — year
  detection must not crash or mislabel; falls back to
  `period_confidence: "suy_doan"` tagged to the document's detected primary
  year. Covered in Task 2.
- A document mixing 2024 and 2025 figures with conflicting values for the
  same (field, year) pair — must surface as `PENDING_REVIEW`, never
  silently pick one. Covered in Task 3.
- RM selects a `report_period` no uploaded document actually contains —
  must fall back to the most recent detected year with a visible note, not
  an empty/broken panel. Covered in Task 4.
- Stress preset pushes a field into a nonsensical range (EBIT after stress
  ≤ 0, so ICR is undefined) — must return `NEED_MORE_DATA`, never a
  misleading huge/negative ratio. Covered in Task 12.
- DSCR comprehensive-mode toggle flipped without comprehensive-mode fields
  present in this document — must show `NEED_MORE_DATA` for that metric,
  never silently fall back to non-comprehensive numbers under the
  comprehensive label. Covered in Task 7.

---

## Part A — Period-aware extraction

### Task 1: Year-column detection module

**Files:**
- Create: `app/extraction/period_columns.py`
- Test: `tests/extraction/test_period_columns.py`

**Interfaces:**
- Produces: `detect_document_primary_year(doc: ExtractedDocument) -> int | None`,
  `detect_year_columns(header_row: list[str], primary_year: int | None) -> dict[int, str]`

- [ ] **Step 1: Write the failing tests**

```python
# tests/extraction/test_period_columns.py
from app.extraction.period_columns import detect_document_primary_year, detect_year_columns
from app.extraction.types import ExtractedDocument


def _doc(text: str) -> ExtractedDocument:
    return ExtractedDocument(filename="f.pdf", doc_type="pdf", text=text, tables=[], extraction_method="text_layer", confidence=1.0)


def test_detects_primary_year_from_reporting_date():
    doc = _doc("BANG CAN DOI KE TOAN\nTai ngay 31/12/2025\n...")
    assert detect_document_primary_year(doc) == 2025


def test_detects_primary_year_picks_newest_when_multiple_years_present():
    doc = _doc("Nam tai chinh ket thuc ngay 31/12/2025, so sanh voi 2024")
    assert detect_document_primary_year(doc) == 2025


def test_no_year_found_returns_none():
    doc = _doc("Khong co thong tin nam nao trong van ban nay")
    assert detect_document_primary_year(doc) is None


def test_year_columns_explicit_year_in_header():
    mapping = detect_year_columns(["Chi tieu", "31/12/2025", "31/12/2024"], primary_year=2025)
    assert mapping == {1: "2025", 2: "2024"}


def test_year_columns_relative_labels_resolved_against_primary_year():
    mapping = detect_year_columns(["Chi tieu", "So cuoi nam", "So dau nam"], primary_year=2025)
    assert mapping == {1: "2025", 2: "2024"}


def test_year_columns_no_signal_column_omitted():
    mapping = detect_year_columns(["Chi tieu", "Ghi chu"], primary_year=2025)
    assert mapping == {}


def test_year_columns_without_primary_year_relative_labels_unresolved():
    mapping = detect_year_columns(["Chi tieu", "So cuoi nam"], primary_year=None)
    assert mapping == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/local/bin/python -m pytest tests/extraction/test_period_columns.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.extraction.period_columns'`

- [ ] **Step 3: Write the implementation**

```python
# app/extraction/period_columns.py
"""Detects which BCTC table column belongs to which fiscal year.

Vietnamese BCTC tables show the current and prior year side by side, either
with an explicit date/year in the header ("31/12/2025") or a relative label
("So cuoi nam"/"So dau nam"). This resolves both forms against the
document's own detected primary reporting year so a value never gets
silently attributed to the wrong year.
"""

import re
import unicodedata

from .types import ExtractedDocument

_YEAR_RE = re.compile(r"\b(20\d{2})\b")
_CURRENT_LABELS = ("so cuoi nam", "cuoi ky", "cuoi nam", "nam nay")
_PRIOR_LABELS = ("so dau nam", "dau ky", "dau nam", "nam truoc")


def _strip_accents_lower(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(c for c in normalized if not unicodedata.combining(c)).lower()


def detect_document_primary_year(doc: ExtractedDocument) -> int | None:
    haystacks = [doc.text] if doc.text else []
    haystacks.extend(" ".join(row) for table in doc.tables for row in table.rows[:1])
    years: list[int] = []
    for text in haystacks:
        years.extend(int(y) for y in _YEAR_RE.findall(text))
    return max(years) if years else None


def detect_year_columns(header_row: list[str], primary_year: int | None) -> dict[int, str]:
    mapping: dict[int, str] = {}
    for i, cell in enumerate(header_row):
        stripped = _strip_accents_lower(cell)
        explicit = _YEAR_RE.findall(cell)
        if explicit:
            mapping[i] = explicit[0]
            continue
        if primary_year is None:
            continue
        if any(label in stripped for label in _CURRENT_LABELS):
            mapping[i] = str(primary_year)
        elif any(label in stripped for label in _PRIOR_LABELS):
            mapping[i] = str(primary_year - 1)
    return mapping
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/usr/local/bin/python -m pytest tests/extraction/test_period_columns.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add app/extraction/period_columns.py tests/extraction/test_period_columns.py
git commit -m "feat(eb): add BCTC year-column detection"
```

---

### Task 2: Multi-value, period-aware row extraction

**Files:**
- Modify: `app/extraction/evidence_search.py`
- Test: `tests/test_extraction_evidence_search.py`

**Interfaces:**
- Consumes: `detect_document_primary_year`, `detect_year_columns` (Task 1)
- Produces: `find_all_matches_by_period(documents: list[ExtractedDocument], pattern: re.Pattern) -> list[tuple[EvidenceRef, str, str, str]]`
  — each tuple is `(ref, raw_value, year, confidence)`, `confidence ∈ {"explicit", "suy_doan"}`.

- [ ] **Step 1: Write the failing tests**

```python
# appended to tests/test_extraction_evidence_search.py
import re
from app.extraction.evidence_search import find_all_matches_by_period
from app.extraction.types import ExtractedDocument, ExtractedTable

_PATTERN = re.compile(r"tai san ngan han[:\s]*(-?[\d.,]+)")


def test_find_all_matches_by_period_splits_current_and_prior_year_columns():
    table = ExtractedTable(
        rows=[
            ["Chi tieu", "31/12/2025", "31/12/2024"],
            ["Tai san ngan han", "100.000.000", "90.000.000"],
        ],
        sheet_or_page="BCDKT",
    )
    doc = ExtractedDocument(filename="bctc.xlsx", doc_type="xlsx", text="", tables=[table], extraction_method="spreadsheet", confidence=1.0)
    results = find_all_matches_by_period([doc], _PATTERN)
    by_year = {year: raw for _, raw, year, _ in results}
    assert by_year["2025"] == "100.000.000"
    assert by_year["2024"] == "90.000.000"
    assert all(conf == "explicit" for *_, conf in results)


def test_find_all_matches_by_period_single_column_falls_back_to_primary_year_guessed():
    table = ExtractedTable(rows=[["Chi tieu", "Gia tri"], ["Tai san ngan han", "50.000.000"]], sheet_or_page="S1")
    doc = ExtractedDocument(
        filename="bctc.xlsx", doc_type="xlsx", text="Tai ngay 31/12/2025",
        tables=[table], extraction_method="spreadsheet", confidence=1.0,
    )
    results = find_all_matches_by_period([doc], _PATTERN)
    assert len(results) == 1
    _, raw, year, confidence = results[0]
    assert raw == "50.000.000"
    assert year == "2025"
    assert confidence == "suy_doan"


def test_find_all_matches_by_period_no_primary_year_found_yields_khong_xac_dinh():
    table = ExtractedTable(rows=[["Chi tieu", "Gia tri"], ["Tai san ngan han", "50.000.000"]], sheet_or_page="S1")
    doc = ExtractedDocument(filename="bctc.xlsx", doc_type="xlsx", text="", tables=[table], extraction_method="spreadsheet", confidence=1.0)
    results = find_all_matches_by_period([doc], _PATTERN)
    assert results[0][2] == "khong_xac_dinh"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/local/bin/python -m pytest tests/test_extraction_evidence_search.py -k by_period -v`
Expected: FAIL — `find_all_matches_by_period` does not exist

- [ ] **Step 3: Write the implementation**

Add to `app/extraction/evidence_search.py` (keep `find_all_matches` exactly
as-is — this is a new, additional function):

```python
from app.engine.core.numbers import parse_vn_number
from .period_columns import detect_document_primary_year, detect_year_columns


def find_all_matches_by_period(
    documents: list[ExtractedDocument], pattern: re.Pattern
) -> list[tuple[EvidenceRef, str, str, str]]:
    """Like find_all_matches, but for each matching TABLE row it extracts
    every numeric cell (not just the first capture) and tags each one with
    its fiscal year, resolved from the table's header row. Non-tabular
    matches (plain paragraph text) keep single-value behavior, tagged to
    the document's detected primary year with confidence "suy_doan" —
    real BCTC figures are overwhelmingly tabular, so multi-column fidelity
    concentrates where it matters instead of guessing at prose structure.
    """
    results: list[tuple[EvidenceRef, str, str, str]] = []
    for doc in documents:
        file_id = getattr(doc, "file_id", doc.filename)
        primary_year = detect_document_primary_year(doc)

        matched_in_tables = False
        for table in doc.tables:
            if not table.rows:
                continue
            year_columns = detect_year_columns(table.rows[0], primary_year)
            for row_idx, row in enumerate(table.rows[1:], start=1):
                joined = " | ".join(row)
                haystack = _strip_accents_lower(joined).replace("|", " ")
                if not pattern.search(haystack):
                    continue
                matched_in_tables = True
                for col_idx, cell in enumerate(row):
                    if col_idx not in year_columns:
                        continue
                    if not cell or parse_vn_number(cell) == 0.0 and not any(ch.isdigit() for ch in cell):
                        continue
                    results.append((
                        EvidenceRef(
                            file_id=file_id, filename=doc.filename,
                            location=f"Sheet '{table.sheet_or_page}', dòng {row_idx + 1}",
                            original_text=joined, period=year_columns[col_idx],
                        ),
                        cell, year_columns[col_idx], "explicit",
                    ))
                if not year_columns:
                    # No year signal in this table's header at all — keep the
                    # first captured value as a single best-effort guess
                    # rather than silently discarding a real match.
                    match = pattern.search(haystack)
                    year = str(primary_year) if primary_year else "khong_xac_dinh"
                    results.append((
                        EvidenceRef(
                            file_id=file_id, filename=doc.filename,
                            location=f"Sheet '{table.sheet_or_page}', dòng {row_idx + 1}",
                            original_text=joined, period=year,
                        ),
                        _extract_value(joined, match), year, "suy_doan",
                    ))

        if not matched_in_tables and doc.text:
            haystack = _strip_accents_lower(doc.text)
            match = pattern.search(haystack)
            if match:
                line = next(
                    (l for l in doc.text.splitlines() if pattern.search(_strip_accents_lower(l))),
                    doc.text,
                )
                year = str(primary_year) if primary_year else "khong_xac_dinh"
                results.append((
                    EvidenceRef(
                        file_id=file_id, filename=doc.filename,
                        location="Toàn văn bản", original_text=line.strip(), period=year,
                    ),
                    _extract_value(doc.text, match), year, "suy_doan",
                ))
    return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/usr/local/bin/python -m pytest tests/test_extraction_evidence_search.py -v`
Expected: all pass (existing `find_all_matches` tests unaffected + 3 new ones pass)

- [ ] **Step 5: Commit**

```bash
git add app/extraction/evidence_search.py tests/test_extraction_evidence_search.py
git commit -m "feat(eb): add period-aware multi-column BCTC field extraction"
```

---

### Task 3: New `EbFinancialInputs` fields and patterns

**Files:**
- Modify: `app/agents/eb/financial_inputs.py`
- Test: `tests/agents/eb/test_financial_inputs.py`

**Interfaces:**
- Produces: 12 new optional fields on `EbFinancialInputs` (see table below) and
  matching entries in `_FIELD_PATTERNS`.

New fields (all `float | None = None`, appended after `interest_expense_vnd`):
`net_revenue_vnd`, `pbt_vnd`, `pat_vnd`, `depreciation_vnd`,
`non_current_assets_vnd`, `long_term_debt_vnd`, `finance_lease_debt_vnd`,
`receivables_vnd`, `inventory_vnd`, `payables_vnd`, `cash_vnd`,
`total_principal_due_vnd`.

- [ ] **Step 1: Write the failing tests**

```python
# appended to tests/agents/eb/test_financial_inputs.py
import re
from app.agents.eb.financial_inputs import _FIELD_PATTERNS, EbFinancialInputs


def test_new_fields_exist_on_dataclass():
    inputs = EbFinancialInputs()
    for f in (
        "net_revenue_vnd", "pbt_vnd", "pat_vnd", "depreciation_vnd",
        "non_current_assets_vnd", "long_term_debt_vnd", "finance_lease_debt_vnd",
        "receivables_vnd", "inventory_vnd", "payables_vnd", "cash_vnd",
        "total_principal_due_vnd",
    ):
        assert hasattr(inputs, f)
        assert getattr(inputs, f) is None


def test_new_field_patterns_match_expected_labels():
    cases = {
        "net_revenue_vnd": "doanh thu thuan: 100.000.000",
        "pbt_vnd": "loi nhuan truoc thue: 50.000.000",
        "pat_vnd": "loi nhuan sau thue: 40.000.000",
        "depreciation_vnd": "khau hao: 10.000.000",
        "non_current_assets_vnd": "tai san dai han: 200.000.000",
        "long_term_debt_vnd": "no dai han: 30.000.000",
        "finance_lease_debt_vnd": "no thue tai chinh: 5.000.000",
        "receivables_vnd": "phai thu khach hang: 20.000.000",
        "inventory_vnd": "hang ton kho: 15.000.000",
        "payables_vnd": "phai tra nguoi ban: 12.000.000",
        "cash_vnd": "tien va tuong duong tien: 8.000.000",
        "total_principal_due_vnd": "no goc den han: 25.000.000",
    }
    for field, text in cases.items():
        assert _FIELD_PATTERNS[field].search(text), f"{field} pattern did not match {text!r}"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/local/bin/python -m pytest tests/agents/eb/test_financial_inputs.py -v`
Expected: FAIL — `AttributeError`/`KeyError` on the new fields/patterns

- [ ] **Step 3: Write the implementation**

In `app/agents/eb/financial_inputs.py`, extend the dataclass and pattern dict:

```python
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
```

This task keeps `cfads_vnd` exactly as it is today (existing field, existing
pattern, untouched) — purely additive, zero risk to the still-passing
`cfads_vnd`-based DSCR tests. Task 7 is the one that changes the DSCR
formula and removes `cfads_vnd` (dataclass field + its regex pattern
together, since it becomes that task's only obsolete consumer), keeping
that formula-change diff self-contained. Add matching patterns for the new
fields only:

```python
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
```

The existing `"cfads_vnd": re.compile(...)` entry stays untouched in this
task — leave it exactly where it already is in `_FIELD_PATTERNS`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `/usr/local/bin/python -m pytest tests/agents/eb/test_financial_inputs.py -v`
Expected: all pass

Run: `/usr/local/bin/python -m pytest -q` (full suite)
Expected: all pass — this task is purely additive, so nothing existing
should break yet.

- [ ] **Step 5: Commit**

```bash
git add app/agents/eb/financial_inputs.py tests/agents/eb/test_financial_inputs.py
git commit -m "feat(eb): add new BCTC fields (revenue, PBT/PAT, depreciation, balance-sheet detail)"
```

---

### Task 4: Period-aware extraction entry point + router wiring

**Files:**
- Modify: `app/agents/eb/financial_inputs.py`
- Modify: `app/agents/eb/router.py:52-62` (form params), `:96` (extraction call)
- Test: `tests/agents/eb/test_financial_inputs.py`, `tests/agents/eb/test_router.py`

**Interfaces:**
- Consumes: `find_all_matches_by_period` (Task 2)
- Produces:
  ```python
  @dataclass
  class PeriodExtraction:
      year: str
      inputs: EbFinancialInputs
      field_evidence: dict[str, FieldEvidence]

  def extract_period_aware_financial_inputs(
      documents: list[ExtractedDocument],
  ) -> dict[str, PeriodExtraction]: ...
  ```
  Response gains `computed["ho_so_period"] = {"selected": str, "available": list[str]}`.

- [ ] **Step 1: Write the failing tests**

```python
# appended to tests/agents/eb/test_financial_inputs.py
from app.agents.eb.financial_inputs import extract_period_aware_financial_inputs
from app.extraction.types import ExtractedDocument, ExtractedTable


def test_extract_period_aware_splits_two_years():
    table = ExtractedTable(
        rows=[
            ["Chi tieu", "31/12/2025", "31/12/2024"],
            ["Von chu so huu", "500.000.000", "400.000.000"],
        ],
        sheet_or_page="BCDKT",
    )
    doc = ExtractedDocument(filename="bctc.xlsx", doc_type="xlsx", text="", tables=[table], extraction_method="spreadsheet", confidence=1.0)
    by_year = extract_period_aware_financial_inputs([doc])
    assert by_year["2025"].inputs.equity_vnd == 500_000_000
    assert by_year["2024"].inputs.equity_vnd == 400_000_000


def test_extract_period_aware_conflicting_values_same_year_is_pending_review():
    table1 = ExtractedTable(rows=[["Chi tieu", "31/12/2025"], ["Von chu so huu", "500.000.000"]], sheet_or_page="S1")
    table2 = ExtractedTable(rows=[["Chi tieu", "31/12/2025"], ["Von chu so huu", "600.000.000"]], sheet_or_page="S2")
    doc = ExtractedDocument(filename="bctc.xlsx", doc_type="xlsx", text="", tables=[table1, table2], extraction_method="spreadsheet", confidence=1.0)
    by_year = extract_period_aware_financial_inputs([doc])
    assert by_year["2025"].field_evidence["equity_vnd"].status == "PENDING_REVIEW"
    assert by_year["2025"].inputs.equity_vnd is None
```

```python
# appended to tests/agents/eb/test_router.py — same monkeypatch/TestClient
# pattern as this file's existing tests, but with a real comma-separated
# CSV (app/extraction/xlsx_csv_parser.py parses this into a genuine
# multi-column ExtractedTable, unlike the file's older prose-style
# "Label: value\n" fixtures which yield single-column rows).
def test_assess_endpoint_reports_available_and_selected_period(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test_period.db"))
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(eb_router, "generate_narrative", lambda computed: {"why": [], "credit_memo": ""})

    client = TestClient(app)
    csv_text = (
        b"Chi tieu,31/12/2025,31/12/2024\n"
        b"Von chu so huu,500000000,400000000\n"
        b"Tai san ngan han,1000000000,900000000\n"
        b"No ngan han,600000000,550000000\n"
    )
    files = {"files": ("bctc.csv", io.BytesIO(csv_text), "text/csv")}
    resp = client.post(
        "/api/eb/assess",
        data={"customer_name": "CONG TY TNHH TEST", "tax_id": "0100000001"},
        files=files,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ho_so_period"]["selected"] == "2025"
    assert "2024" in body["ho_so_period"]["available"]


def test_assess_endpoint_honors_explicit_report_period(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test_period2.db"))
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(eb_router, "generate_narrative", lambda computed: {"why": [], "credit_memo": ""})

    client = TestClient(app)
    csv_text = (
        b"Chi tieu,31/12/2025,31/12/2024\n"
        b"Von chu so huu,500000000,400000000\n"
    )
    files = {"files": ("bctc.csv", io.BytesIO(csv_text), "text/csv")}
    resp = client.post(
        "/api/eb/assess",
        data={"customer_name": "CONG TY TNHH TEST", "tax_id": "0100000001", "report_period": "2024"},
        files=files,
    )
    body = resp.json()
    assert body["ho_so_period"]["selected"] == "2024"
    # NWC is NEED_MORE_DATA here (no current_assets/current_liabilities rows in
    # this fixture), so RF01 falls back to reporting equity_vnd directly —
    # proving the 2024 column (400M), not the 2025 column (500M), was selected.
    rf01 = next(f for f in body["risk_flags"] if f["rule_id"] == "RF01")
    assert rf01["observed_value"] == 400_000_000
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/local/bin/python -m pytest tests/agents/eb/test_financial_inputs.py -k period_aware -v`
Expected: FAIL — `extract_period_aware_financial_inputs` does not exist

- [ ] **Step 3: Write the implementation**

In `financial_inputs.py`:

```python
from app.extraction.evidence_search import find_all_matches, find_all_matches_by_period


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
```

In `router.py`, add the form field and replace the extraction call:

```python
async def assess(
    customer_name: str = Form(...),
    tax_id: str = Form(...),
    files: list[UploadFile] = File(...),
    proposed_limit_vnd: float | None = Form(default=None),
    eligible_contract_value_vnd: float | None = Form(default=None),
    qd_eb_039_method: str | None = Form(default=None),
    report_period: str | None = Form(default=None),
) -> dict:
    ...
    from .financial_inputs import extract_period_aware_financial_inputs

    period_extractions = extract_period_aware_financial_inputs(documents)
    available_periods = sorted(period_extractions.keys(), reverse=True)
    selected_period = (
        report_period if report_period in period_extractions
        else (available_periods[0] if available_periods else None)
    )
    if selected_period and selected_period in period_extractions:
        financial_inputs = period_extractions[selected_period].inputs
        field_evidence = period_extractions[selected_period].field_evidence
    else:
        financial_inputs, field_evidence = EbFinancialInputs(), {}
    ...
    computed["ho_so_period"] = {"selected": selected_period, "available": available_periods}
```

(`from .financial_inputs import extract_financial_inputs` import at the top
of `router.py` is removed since it's no longer called; `EbFinancialInputs`
needs importing for the empty-fallback branch.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `/usr/local/bin/python -m pytest tests/agents/eb/test_financial_inputs.py tests/agents/eb/test_router.py -v`
Expected: all pass (write the router test's multipart body concretely
against this file's existing helper before running — copy the exact xlsx/csv
upload pattern already used by e.g. `test_assess_endpoint_runs_...` in that
file, replacing its financial rows with the 3-column header shown above)

- [ ] **Step 5: Commit**

```bash
git add app/agents/eb/financial_inputs.py app/agents/eb/router.py tests/agents/eb/test_financial_inputs.py tests/agents/eb/test_router.py
git commit -m "feat(eb): wire period-aware extraction into /api/eb/assess"
```

---

## Part B — New/changed metrics

### Task 5: EBIT fallback + EBITDA

**Files:**
- Create: `app/agents/eb/profitability.py`
- Modify: `app/agents/eb/repayment_capacity.py` (ICR uses the fallback)
- Test: `tests/agents/eb/test_profitability.py`, `tests/agents/eb/test_repayment_capacity.py`

**Interfaces:**
- Produces: `resolve_ebit_vnd(inputs: EbFinancialInputs) -> float | None`,
  `compute_ebitda(inputs, field_evidence=None) -> Metric`

- [ ] **Step 1: Write the failing tests**

```python
# tests/agents/eb/test_profitability.py
from app.agents.eb.financial_inputs import EbFinancialInputs
from app.agents.eb.profitability import compute_ebitda, resolve_ebit_vnd


def test_resolve_ebit_prefers_directly_extracted_value():
    inputs = EbFinancialInputs(ebit_vnd=999_000_000, pbt_vnd=100_000_000, interest_expense_vnd=50_000_000)
    assert resolve_ebit_vnd(inputs) == 999_000_000


def test_resolve_ebit_computed_from_pbt_plus_interest_when_not_extracted():
    inputs = EbFinancialInputs(pbt_vnd=100_000_000, interest_expense_vnd=50_000_000)
    assert resolve_ebit_vnd(inputs) == 150_000_000


def test_resolve_ebit_none_when_neither_available():
    assert resolve_ebit_vnd(EbFinancialInputs(pbt_vnd=100_000_000)) is None


def test_ebitda_computed():
    inputs = EbFinancialInputs(pbt_vnd=100_000_000, interest_expense_vnd=50_000_000, depreciation_vnd=20_000_000)
    metric = compute_ebitda(inputs)
    assert metric.value == 170_000_000
    assert metric.status == "OK"


def test_ebitda_need_more_data_when_depreciation_missing():
    inputs = EbFinancialInputs(pbt_vnd=100_000_000, interest_expense_vnd=50_000_000)
    metric = compute_ebitda(inputs)
    assert metric.status == "NEED_MORE_DATA"
```

```python
# appended to tests/agents/eb/test_repayment_capacity.py
def test_icr_uses_ebit_fallback_when_ebit_vnd_not_directly_extracted():
    inputs = EbFinancialInputs(pbt_vnd=600_000_000, interest_expense_vnd=200_000_000)
    metric = compute_icr(inputs)
    assert metric.value == 4.0  # (600M + 200M) / 200M
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/local/bin/python -m pytest tests/agents/eb/test_profitability.py -v`
Expected: FAIL — module does not exist

- [ ] **Step 3: Write the implementation**

```python
# app/agents/eb/profitability.py
from app.engine.core.types import Metric

from .financial_inputs import EbFinancialInputs


def _evidence_for(field_evidence: dict | None, *keys: str) -> dict:
    if not field_evidence:
        return {}
    return {k: field_evidence[k].evidence for k in keys if k in field_evidence}


def resolve_ebit_vnd(inputs: EbFinancialInputs) -> float | None:
    """Prefer a directly extracted EBIT line (rare in VN BCTC); else compute
    PBT + interest expense from real extracted figures — this is the spec's
    own CALC_EBIT formula, not a suy diễn, since VN BCTC almost never has a
    literal "EBIT" line item."""
    if inputs.ebit_vnd is not None:
        return inputs.ebit_vnd
    if inputs.pbt_vnd is not None and inputs.interest_expense_vnd is not None:
        return inputs.pbt_vnd + inputs.interest_expense_vnd
    return None


def compute_ebitda(inputs: EbFinancialInputs, field_evidence: dict | None = None) -> Metric:
    ebit = resolve_ebit_vnd(inputs)
    if ebit is None or inputs.depreciation_vnd is None:
        return Metric.need_more_data("ebitda", "EBIT + khau_hao")
    value = ebit + inputs.depreciation_vnd
    return Metric(
        metric="ebitda", value=value, formula="EBIT + khau_hao",
        input_values={"ebit_vnd": ebit, "depreciation_vnd": inputs.depreciation_vnd},
        input_sources={"ebit_vnd": "bctc", "depreciation_vnd": "bctc"},
        evidence=_evidence_for(field_evidence, "pbt_vnd", "interest_expense_vnd", "depreciation_vnd"),
    )
```

In `repayment_capacity.py`, change `compute_icr` to use the fallback:

```python
from .profitability import resolve_ebit_vnd

def compute_icr(inputs: EbFinancialInputs, field_evidence: dict | None = None) -> Metric:
    ebit = resolve_ebit_vnd(inputs)
    if ebit is None or not inputs.interest_expense_vnd:
        return Metric.need_more_data("icr", "EBIT / chi_phi_lai_vay")
    value = round(ebit / inputs.interest_expense_vnd, 4)
    return Metric(
        metric="icr", value=value, formula="EBIT / chi_phi_lai_vay",
        input_values={"ebit_vnd": ebit, "interest_expense_vnd": inputs.interest_expense_vnd},
        input_sources={"ebit_vnd": "bctc", "interest_expense_vnd": "bctc"},
        evidence=_evidence_for(field_evidence, "ebit_vnd", "pbt_vnd", "interest_expense_vnd"),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/usr/local/bin/python -m pytest tests/agents/eb/test_profitability.py tests/agents/eb/test_repayment_capacity.py -v`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add app/agents/eb/profitability.py app/agents/eb/repayment_capacity.py tests/agents/eb/test_profitability.py tests/agents/eb/test_repayment_capacity.py
git commit -m "feat(eb): compute EBIT fallback and EBITDA"
```

---

### Task 6: Capital-structure metrics (Liquidity Balance, Nguồn vốn dài hạn, Tổng nợ vay, Cân đối tài chính)

**Files:**
- Create: `app/agents/eb/capital_structure.py`
- Test: `tests/agents/eb/test_capital_structure.py`

**Interfaces:**
- Consumes: `EbFinancialInputs` (Task 3), `Metric` from `compute_nwc` (existing `liquidity.py`)
- Produces:
  ```python
  def compute_liquidity_balance(inputs, field_evidence=None) -> Metric
  def compute_long_term_capital(inputs, field_evidence=None) -> Metric
  def compute_total_borrowings(inputs, field_evidence=None) -> Metric
  def compute_capital_balance_check(inputs, nwc: Metric, long_term_capital: Metric) -> dict
  ```
  `compute_capital_balance_check` returns
  `{"trai": float|None, "phai": float|None, "trang_thai": str, "nhan_xet": str}`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/agents/eb/test_capital_structure.py
from app.agents.eb.capital_structure import (
    compute_capital_balance_check, compute_liquidity_balance,
    compute_long_term_capital, compute_total_borrowings,
)
from app.agents.eb.financial_inputs import EbFinancialInputs
from app.agents.eb.liquidity import compute_nwc


def test_liquidity_balance_positive():
    inputs = EbFinancialInputs(current_assets_vnd=300_000_000, current_liabilities_vnd=100_000_000, net_revenue_vnd=1_000_000_000)
    metric = compute_liquidity_balance(inputs)
    assert metric.value == 0.2


def test_liquidity_balance_need_more_data_without_revenue():
    inputs = EbFinancialInputs(current_assets_vnd=300_000_000, current_liabilities_vnd=100_000_000)
    assert compute_liquidity_balance(inputs).status == "NEED_MORE_DATA"


def test_long_term_capital():
    inputs = EbFinancialInputs(equity_vnd=500_000_000, long_term_debt_vnd=200_000_000)
    metric = compute_long_term_capital(inputs)
    assert metric.value == 700_000_000


def test_total_borrowings_includes_finance_lease_when_present():
    inputs = EbFinancialInputs(short_term_debt_vnd=100_000_000, long_term_debt_vnd=200_000_000, finance_lease_debt_vnd=30_000_000)
    metric = compute_total_borrowings(inputs)
    assert metric.value == 330_000_000


def test_total_borrowings_without_finance_lease_defaults_to_zero_for_that_component():
    inputs = EbFinancialInputs(short_term_debt_vnd=100_000_000, long_term_debt_vnd=200_000_000)
    metric = compute_total_borrowings(inputs)
    assert metric.value == 300_000_000


def test_capital_balance_check_balanced():
    inputs = EbFinancialInputs(
        current_assets_vnd=300_000_000, current_liabilities_vnd=100_000_000,
        equity_vnd=500_000_000, long_term_debt_vnd=100_000_000, non_current_assets_vnd=400_000_000,
    )
    nwc = compute_nwc(inputs)
    long_term_capital = compute_long_term_capital(inputs)
    check = compute_capital_balance_check(inputs, nwc, long_term_capital)
    assert check["trai"] == 200_000_000
    assert check["phai"] == 200_000_000
    assert check["trang_thai"] == "Can bang"


def test_capital_balance_check_mismatched():
    inputs = EbFinancialInputs(
        current_assets_vnd=300_000_000, current_liabilities_vnd=100_000_000,
        equity_vnd=500_000_000, long_term_debt_vnd=100_000_000, non_current_assets_vnd=550_000_000,
    )
    nwc = compute_nwc(inputs)
    long_term_capital = compute_long_term_capital(inputs)
    check = compute_capital_balance_check(inputs, nwc, long_term_capital)
    assert check["trang_thai"] == "Can ra soat phan loai nguon von"


def test_capital_balance_check_need_more_data():
    check = compute_capital_balance_check(EbFinancialInputs(), compute_nwc(EbFinancialInputs()), compute_long_term_capital(EbFinancialInputs()))
    assert check["trang_thai"] == "Chua xac dinh tu ho so tai len"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/local/bin/python -m pytest tests/agents/eb/test_capital_structure.py -v`
Expected: FAIL — module does not exist

- [ ] **Step 3: Write the implementation**

```python
# app/agents/eb/capital_structure.py
from app.engine.core.types import Metric

from .financial_inputs import EbFinancialInputs

_BALANCE_TOLERANCE_VND = 1


def _evidence_for(field_evidence: dict | None, *keys: str) -> dict:
    if not field_evidence:
        return {}
    return {k: field_evidence[k].evidence for k in keys if k in field_evidence}


def compute_liquidity_balance(inputs: EbFinancialInputs, field_evidence: dict | None = None) -> Metric:
    if inputs.current_assets_vnd is None or inputs.current_liabilities_vnd is None or not inputs.net_revenue_vnd:
        return Metric.need_more_data("liquidity_balance", "(tai_san_ngan_han - no_ngan_han) / doanh_thu_thuan")
    value = round((inputs.current_assets_vnd - inputs.current_liabilities_vnd) / inputs.net_revenue_vnd, 4)
    return Metric(
        metric="liquidity_balance", value=value,
        formula="(tai_san_ngan_han - no_ngan_han) / doanh_thu_thuan",
        input_values={
            "current_assets_vnd": inputs.current_assets_vnd,
            "current_liabilities_vnd": inputs.current_liabilities_vnd,
            "net_revenue_vnd": inputs.net_revenue_vnd,
        },
        input_sources={"current_assets_vnd": "bctc", "current_liabilities_vnd": "bctc", "net_revenue_vnd": "bctc"},
        evidence=_evidence_for(field_evidence, "current_assets_vnd", "current_liabilities_vnd", "net_revenue_vnd"),
    )


def compute_long_term_capital(inputs: EbFinancialInputs, field_evidence: dict | None = None) -> Metric:
    if inputs.equity_vnd is None or inputs.long_term_debt_vnd is None:
        return Metric.need_more_data("long_term_capital", "von_chu_so_huu + no_dai_han")
    value = inputs.equity_vnd + inputs.long_term_debt_vnd
    return Metric(
        metric="long_term_capital", value=value, formula="von_chu_so_huu + no_dai_han",
        input_values={"equity_vnd": inputs.equity_vnd, "long_term_debt_vnd": inputs.long_term_debt_vnd},
        input_sources={"equity_vnd": "bctc", "long_term_debt_vnd": "bctc"},
        evidence=_evidence_for(field_evidence, "equity_vnd", "long_term_debt_vnd"),
    )


def compute_total_borrowings(inputs: EbFinancialInputs, field_evidence: dict | None = None) -> Metric:
    if inputs.short_term_debt_vnd is None or inputs.long_term_debt_vnd is None:
        return Metric.need_more_data("total_borrowings", "vay_ngan_han + vay_dai_han + no_thue_tai_chinh")
    value = inputs.short_term_debt_vnd + inputs.long_term_debt_vnd + (inputs.finance_lease_debt_vnd or 0)
    return Metric(
        metric="total_borrowings", value=value,
        formula="vay_ngan_han + vay_dai_han + no_thue_tai_chinh",
        input_values={
            "short_term_debt_vnd": inputs.short_term_debt_vnd, "long_term_debt_vnd": inputs.long_term_debt_vnd,
            "finance_lease_debt_vnd": inputs.finance_lease_debt_vnd or 0,
        },
        input_sources={"short_term_debt_vnd": "bctc", "long_term_debt_vnd": "bctc"},
        evidence=_evidence_for(field_evidence, "short_term_debt_vnd", "long_term_debt_vnd", "finance_lease_debt_vnd"),
    )


def compute_capital_balance_check(inputs: EbFinancialInputs, nwc: Metric, long_term_capital: Metric) -> dict:
    if nwc.status == "NEED_MORE_DATA" or long_term_capital.status == "NEED_MORE_DATA" or inputs.non_current_assets_vnd is None:
        return {
            "trai": None, "phai": None, "trang_thai": "Chua xac dinh tu ho so tai len",
            "nhan_xet": "Thiếu tài sản ngắn/dài hạn, nợ ngắn/dài hạn hoặc vốn chủ sở hữu để đối chiếu cân đối tài chính.",
        }
    trai = nwc.value
    phai = long_term_capital.value - inputs.non_current_assets_vnd
    balanced = abs(trai - phai) <= _BALANCE_TOLERANCE_VND
    return {
        "trai": trai, "phai": phai,
        "trang_thai": "Can bang" if balanced else "Can ra soat phan loai nguon von",
        "nhan_xet": (
            "Tài sản dài hạn nên được tài trợ bằng nguồn vốn dài hạn; mất cân đối là tín hiệu rủi ro kỳ hạn."
        ),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/usr/local/bin/python -m pytest tests/agents/eb/test_capital_structure.py -v`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add app/agents/eb/capital_structure.py tests/agents/eb/test_capital_structure.py
git commit -m "feat(eb): add liquidity balance, long-term capital, total borrowings, balance-sheet check"
```

---

### Task 7: DSCR formula rewrite (PAT+Depreciation basis, comprehensive mode)

**Files:**
- Modify: `app/agents/eb/repayment_capacity.py`
- Modify: `app/agents/eb/financial_inputs.py` (remove the now-obsolete `cfads_vnd` field and pattern)
- Modify: `tests/agents/eb/test_repayment_capacity.py` (rewrite the DSCR-related
  tests that reference the old `cfads_vnd`-based formula)
- Modify: `tests/agents/eb/test_financial_inputs.py` (drop the `cfads_vnd` case
  from `test_new_field_patterns_match_expected_labels`'s dict if present —
  it is not, since Task 3 only added new-field cases — and delete any
  pre-existing standalone `cfads_vnd` pattern test in this file, if any)

**Interfaces:**
- Produces: `compute_dscr(inputs, field_evidence=None, comprehensive: bool = False) -> Metric`
  (signature adds one optional parameter; `evaluate_rf05_weak_repayment_capacity`
  keeps its exact current signature, unaffected).

This **replaces the default DSCR formula** — the spec's "công thức chuẩn" is
`(LNST + Khấu hao + Lãi vay dài hạn) / (Nợ gốc dài hạn đến hạn + Lãi vay dài
hạn)`, not the old `CFADS / (gốc + lãi đến hạn)`. `cfads_vnd` is removed
from `EbFinancialInputs` as part of this task (its only consumer).

- [ ] **Step 1: Update the failing/changed tests**

Replace every `cfads_vnd=` usage in `tests/agents/eb/test_repayment_capacity.py`
with the new inputs. Full replacement file content for the DSCR-related tests:

```python
from app.agents.eb.financial_inputs import EbFinancialInputs
from app.agents.eb.repayment_capacity import compute_dscr, compute_icr, evaluate_rf05_weak_repayment_capacity


def test_dscr_computed():
    inputs = EbFinancialInputs(pat_vnd=1_000_000_000, depreciation_vnd=200_000_000, interest_due_vnd=200_000_000, principal_due_vnd=1_000_000_000)
    metric = compute_dscr(inputs)
    assert round(metric.value, 4) == round(1_400_000_000 / 1_200_000_000, 4)


def test_dscr_missing_data_is_not_zero():
    metric = compute_dscr(EbFinancialInputs())
    assert metric.status == "NEED_MORE_DATA"
    assert metric.value is None


def test_dscr_comprehensive_mode_uses_total_principal_and_total_interest():
    inputs = EbFinancialInputs(
        pat_vnd=1_000_000_000, depreciation_vnd=200_000_000,
        interest_expense_vnd=250_000_000, total_principal_due_vnd=1_200_000_000,
    )
    metric = compute_dscr(inputs, comprehensive=True)
    assert round(metric.value, 4) == round(1_450_000_000 / 1_450_000_000, 4)


def test_dscr_comprehensive_mode_need_more_data_without_comprehensive_fields():
    # total_principal_due_vnd absent — must NOT silently fall back to
    # principal_due_vnd under the comprehensive label.
    inputs = EbFinancialInputs(pat_vnd=1_000_000_000, depreciation_vnd=200_000_000, interest_due_vnd=200_000_000, principal_due_vnd=1_000_000_000)
    metric = compute_dscr(inputs, comprehensive=True)
    assert metric.status == "NEED_MORE_DATA"


def test_icr_computed():
    inputs = EbFinancialInputs(pbt_vnd=600_000_000, interest_expense_vnd=200_000_000)
    metric = compute_icr(inputs)
    assert metric.value == 4.0


def test_icr_zero_interest_expense_is_need_more_data_not_infinity():
    inputs = EbFinancialInputs(pbt_vnd=600_000_000, interest_expense_vnd=0)
    metric = compute_icr(inputs)
    assert metric.status == "NEED_MORE_DATA"


def test_rf05_activates_when_dscr_below_1():
    dscr = compute_dscr(EbFinancialInputs(pat_vnd=100_000_000, depreciation_vnd=0, principal_due_vnd=1_000_000_000, interest_due_vnd=0))
    icr = compute_icr(EbFinancialInputs(pbt_vnd=600_000_000, interest_expense_vnd=200_000_000))
    result = evaluate_rf05_weak_repayment_capacity(dscr, icr)
    assert result.status == "KÍCH HOẠT"
    assert result.severity == "CRITICAL"


def test_rf05_not_evaluated_when_both_metrics_missing():
    dscr = compute_dscr(EbFinancialInputs())
    icr = compute_icr(EbFinancialInputs())
    result = evaluate_rf05_weak_repayment_capacity(dscr, icr)
    assert result.status == "CHƯA ĐÁNH GIÁ"


def test_rf05_not_activated_when_both_metrics_healthy():
    dscr = compute_dscr(EbFinancialInputs(pat_vnd=1_000_000_000, depreciation_vnd=0, principal_due_vnd=1_000_000_000, interest_due_vnd=0))
    icr = compute_icr(EbFinancialInputs(pbt_vnd=600_000_000, interest_expense_vnd=200_000_000))
    result = evaluate_rf05_weak_repayment_capacity(dscr, icr)
    assert result.status == "KHÔNG KÍCH HOẠT"


def test_rf05_activates_when_one_metric_missing_and_other_weak():
    dscr = compute_dscr(EbFinancialInputs())
    icr = compute_icr(EbFinancialInputs(pbt_vnd=-100_000_000, interest_expense_vnd=200_000_000))
    result = evaluate_rf05_weak_repayment_capacity(dscr, icr)
    assert result.status == "KÍCH HOẠT"
    assert result.severity == "CRITICAL"


def test_rf05_missing_dscr_with_healthy_icr_is_not_a_clean_pass():
    dscr = compute_dscr(EbFinancialInputs())
    icr = compute_icr(EbFinancialInputs(pbt_vnd=600_000_000, interest_expense_vnd=200_000_000))
    result = evaluate_rf05_weak_repayment_capacity(dscr, icr)
    assert result.status == "CHƯA ĐÁNH GIÁ"
    assert result.observed_value == "KHÔNG ĐỦ DỮ LIỆU"


def test_rf05_missing_icr_with_healthy_dscr_is_not_a_clean_pass():
    dscr = compute_dscr(EbFinancialInputs(pat_vnd=1_000_000_000, depreciation_vnd=0, principal_due_vnd=1_000_000_000, interest_due_vnd=0))
    icr = compute_icr(EbFinancialInputs())
    result = evaluate_rf05_weak_repayment_capacity(dscr, icr)
    assert result.status == "CHƯA ĐÁNH GIÁ"


def test_dscr_and_rf05_carry_evidence_refs():
    from app.agents.eb.financial_inputs import FieldEvidence
    from app.engine.core.types import EvidenceRef

    ref = EvidenceRef(file_id="f1", filename="pakd.pdf", location="Trang 1", original_text="Loi nhuan sau thue: 1.000.000.000")
    field_evidence = {"pat_vnd": FieldEvidence(status="COMPUTED", evidence=[ref])}
    inputs = EbFinancialInputs(pat_vnd=1_000_000_000, depreciation_vnd=200_000_000, interest_due_vnd=200_000_000, principal_due_vnd=1_000_000_000)
    dscr = compute_dscr(inputs, field_evidence)
    assert dscr.evidence["pat_vnd"] == [ref]
    icr = compute_icr(EbFinancialInputs(pbt_vnd=600_000_000, interest_expense_vnd=200_000_000))
    result = evaluate_rf05_weak_repayment_capacity(dscr, icr)
    assert result.evidence_refs.get("pat_vnd") == [ref]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/local/bin/python -m pytest tests/agents/eb/test_repayment_capacity.py -v`
Expected: FAIL — `compute_dscr` still uses the old `cfads_vnd` formula

- [ ] **Step 3: Write the implementation**

Replace `compute_dscr` in `repayment_capacity.py`:

```python
def compute_dscr(
    inputs: EbFinancialInputs, field_evidence: dict | None = None, comprehensive: bool = False
) -> Metric:
    if comprehensive:
        numerator_fields = ("pat_vnd", "depreciation_vnd", "interest_expense_vnd")
        principal = inputs.total_principal_due_vnd
        interest = inputs.interest_expense_vnd
        formula = "(LNST + khau_hao + tong_chi_phi_lai_vay) / (tong_no_goc_den_han + tong_chi_phi_lai_vay)"
    else:
        numerator_fields = ("pat_vnd", "depreciation_vnd", "interest_due_vnd")
        principal = inputs.principal_due_vnd
        interest = inputs.interest_due_vnd
        formula = "(LNST + khau_hao + lai_vay_dai_han) / (no_goc_dai_han_den_han + lai_vay_dai_han)"

    if inputs.pat_vnd is None or inputs.depreciation_vnd is None or interest is None or principal is None:
        return Metric.need_more_data("dscr", formula)
    debt_service = principal + interest
    if debt_service <= 0:
        return Metric.need_more_data("dscr", formula)

    numerator = inputs.pat_vnd + inputs.depreciation_vnd + interest
    value = round(numerator / debt_service, 4)
    return Metric(
        metric="dscr", value=value, formula=formula,
        input_values={"pat_vnd": inputs.pat_vnd, "depreciation_vnd": inputs.depreciation_vnd, "interest": interest, "principal": principal},
        input_sources={"pat_vnd": "bctc", "depreciation_vnd": "bctc"},
        evidence=_evidence_for(field_evidence, *numerator_fields, "principal_due_vnd", "total_principal_due_vnd"),
    )
```

In `app/agents/eb/financial_inputs.py`, remove the now-obsolete field and
pattern (this formula change was `cfads_vnd`'s only consumer):

```python
# Delete this line from the EbFinancialInputs dataclass:
#     cfads_vnd: float | None = None
#
# Delete this entry from _FIELD_PATTERNS:
#     "cfads_vnd": re.compile(r"cfads[:\s]*(-?[\d.,]+)"),
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/usr/local/bin/python -m pytest tests/agents/eb/test_repayment_capacity.py -v`
Expected: all pass

Run: `/usr/local/bin/python -m pytest -q` — expect the remaining failure to
be only `tests/agents/eb/test_stress_test.py` (it builds `EbFinancialInputs`
with `cfads_vnd=`/calls `run_stress_test` with the old `margin_pct=`
contract; fixed in Task 12). `test_router.py` does not reference
`cfads_vnd` anywhere, so it is unaffected by this task.

- [ ] **Step 5: Commit**

```bash
git add app/agents/eb/repayment_capacity.py app/agents/eb/financial_inputs.py tests/agents/eb/test_repayment_capacity.py
git commit -m "feat(eb): rewrite DSCR to PAT+depreciation basis with comprehensive-mode toggle"
```

---

### Task 8: QĐ 039 receivables-financing limit (BS003 × LTV)

**Files:**
- Modify: `app/agents/eb/contract_financing.py`
- Test: `tests/agents/eb/test_contract_financing.py`

**Interfaces:**
- Produces: `compute_receivables_financing_limit(receivables_vnd: float | None, ltv: float) -> Metric`

- [ ] **Step 1: Write the failing tests**

```python
# appended to tests/agents/eb/test_contract_financing.py
from app.agents.eb.contract_financing import compute_receivables_financing_limit


def test_receivables_financing_limit_80_pct():
    metric = compute_receivables_financing_limit(1_000_000_000, ltv=0.80)
    assert metric.value == 800_000_000
    assert metric.policy_version is None or "85" not in (metric.policy_version or "")


def test_receivables_financing_limit_85_pct_carries_priority_note():
    metric = compute_receivables_financing_limit(1_000_000_000, ltv=0.85)
    assert metric.value == 850_000_000
    assert "VNR500/FDI" in metric.policy_version


def test_receivables_financing_limit_need_more_data_without_receivables():
    metric = compute_receivables_financing_limit(None, ltv=0.80)
    assert metric.status == "NEED_MORE_DATA"


def test_receivables_financing_limit_rejects_invalid_ltv():
    import pytest
    with pytest.raises(ValueError):
        compute_receivables_financing_limit(1_000_000_000, ltv=0.90)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/local/bin/python -m pytest tests/agents/eb/test_contract_financing.py -k receivables_financing -v`
Expected: FAIL — function does not exist

- [ ] **Step 3: Write the implementation**

Append to `contract_financing.py`:

```python
_VALID_LTV = (0.80, 0.85)


def compute_receivables_financing_limit(receivables_vnd: float | None, ltv: float) -> Metric:
    if ltv not in _VALID_LTV:
        raise ValueError(f"ltv phải là 0.80 hoặc 0.85, nhận {ltv}")
    if receivables_vnd is None:
        return Metric.need_more_data("receivables_financing_limit", "phai_thu_khach_hang * ltv")
    value = round(receivables_vnd * ltv, 2)
    policy_version = (
        "Điều kiện ưu tiên — cần xác minh bên mua thuộc VNR500/FDI và phê duyệt theo quy định"
        if ltv == 0.85 else None
    )
    return Metric(
        metric="receivables_financing_limit", value=value,
        formula="phai_thu_khach_hang * ltv",
        input_values={"receivables_vnd": receivables_vnd, "ltv": ltv},
        input_sources={"receivables_vnd": "bctc"},
        policy_version=policy_version,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/usr/local/bin/python -m pytest tests/agents/eb/test_contract_financing.py -v`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add app/agents/eb/contract_financing.py tests/agents/eb/test_contract_financing.py
git commit -m "feat(eb): compute QĐ 039 receivables-financing limit from BS003 with LTV toggle"
```

---

### Task 9: RF06 and RF07 new red flags

**Files:**
- Modify: `app/agents/eb/leverage.py` (RF06)
- Modify: `app/agents/eb/repayment_capacity.py` (RF07)
- Test: `tests/agents/eb/test_leverage.py`, `tests/agents/eb/test_repayment_capacity.py`

**Interfaces:**
- Produces: `evaluate_rf06_receivables_inventory_concentration(inputs, field_evidence=None) -> RuleResult`,
  `evaluate_rf07_high_interest_burden(inputs, field_evidence=None) -> RuleResult`

- [ ] **Step 1: Write the failing tests**

```python
# appended to tests/agents/eb/test_leverage.py
from app.agents.eb.financial_inputs import EbFinancialInputs
from app.agents.eb.leverage import evaluate_rf06_receivables_inventory_concentration


def test_rf06_activates_above_70_pct_concentration():
    inputs = EbFinancialInputs(receivables_vnd=500_000_000, inventory_vnd=300_000_000, current_assets_vnd=1_000_000_000)
    result = evaluate_rf06_receivables_inventory_concentration(inputs)
    assert result.status == "KÍCH HOẠT"
    assert result.severity == "MEDIUM"


def test_rf06_not_activated_below_threshold():
    inputs = EbFinancialInputs(receivables_vnd=100_000_000, inventory_vnd=100_000_000, current_assets_vnd=1_000_000_000)
    result = evaluate_rf06_receivables_inventory_concentration(inputs)
    assert result.status == "KHÔNG KÍCH HOẠT"


def test_rf06_not_evaluated_without_data():
    result = evaluate_rf06_receivables_inventory_concentration(EbFinancialInputs())
    assert result.status == "CHƯA ĐÁNH GIÁ"
```

```python
# appended to tests/agents/eb/test_repayment_capacity.py
from app.agents.eb.repayment_capacity import evaluate_rf07_high_interest_burden


def test_rf07_activates_when_interest_exceeds_30pct_of_ebit():
    inputs = EbFinancialInputs(pbt_vnd=600_000_000, interest_expense_vnd=300_000_000)  # EBIT = 900M, 300/900=33%
    result = evaluate_rf07_high_interest_burden(inputs)
    assert result.status == "KÍCH HOẠT"
    assert result.severity == "MEDIUM"


def test_rf07_not_activated_below_threshold():
    inputs = EbFinancialInputs(pbt_vnd=600_000_000, interest_expense_vnd=100_000_000)  # EBIT=700M, 100/700=14%
    result = evaluate_rf07_high_interest_burden(inputs)
    assert result.status == "KHÔNG KÍCH HOẠT"


def test_rf07_not_evaluated_without_data():
    result = evaluate_rf07_high_interest_burden(EbFinancialInputs())
    assert result.status == "CHƯA ĐÁNH GIÁ"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/local/bin/python -m pytest tests/agents/eb/test_leverage.py tests/agents/eb/test_repayment_capacity.py -k "rf06 or rf07" -v`
Expected: FAIL — functions do not exist

- [ ] **Step 3: Write the implementation**

Append to `leverage.py`:

```python
RF06_THRESHOLD = 0.70
RF06_POLICY_VERSION = "policy_mode=DEMO_UAT (ngưỡng demo, chưa xác nhận chuẩn MSB chính thức)"


def evaluate_rf06_receivables_inventory_concentration(
    inputs: EbFinancialInputs, field_evidence: dict | None = None
) -> RuleResult:
    if inputs.receivables_vnd is None or inputs.inventory_vnd is None or not inputs.current_assets_vnd:
        return RuleResult(
            rule_id="RF06", rule_name="Phải thu/tồn kho chiếm tỷ trọng lớn", status="CHƯA ĐÁNH GIÁ",
            comment="Thiếu phải thu khách hàng, hàng tồn kho hoặc tài sản ngắn hạn để tính tỷ trọng.",
            verification_question="Hồ sơ có chi tiết phải thu khách hàng và hàng tồn kho không?",
            recommended_action="Bổ sung thuyết minh phải thu/tồn kho trước khi đánh giá cơ cấu tài sản ngắn hạn.",
            evidence_refs=_evidence_for(field_evidence, "receivables_vnd", "inventory_vnd", "current_assets_vnd"),
        )
    ratio = round((inputs.receivables_vnd + inputs.inventory_vnd) / inputs.current_assets_vnd, 4)
    if ratio > RF06_THRESHOLD:
        return RuleResult(
            rule_id="RF06", rule_name="Phải thu/tồn kho chiếm tỷ trọng lớn", status="KÍCH HOẠT", severity="MEDIUM",
            evidence=[f"Tỷ trọng = {ratio} (> {RF06_THRESHOLD})"],
            threshold=f"quy tắc demo: > {RF06_THRESHOLD * 100:.0f}% tài sản ngắn hạn",
            comment="Chất lượng tài sản ngắn hạn phụ thuộc lớn vào thu hồi công nợ/luân chuyển hàng tồn.",
            observed_value=ratio, policy_version=RF06_POLICY_VERSION,
            verification_question="Tuổi nợ phải thu và vòng quay hàng tồn kho thế nào?",
            recommended_action="Yêu cầu bảng tuổi nợ phải thu và đánh giá vòng quay hàng tồn kho.",
            evidence_refs=_evidence_for(field_evidence, "receivables_vnd", "inventory_vnd", "current_assets_vnd"),
        )
    return RuleResult(
        rule_id="RF06", rule_name="Phải thu/tồn kho chiếm tỷ trọng lớn", status="KHÔNG KÍCH HOẠT",
        observed_value=ratio, policy_version=RF06_POLICY_VERSION,
        evidence_refs=_evidence_for(field_evidence, "receivables_vnd", "inventory_vnd", "current_assets_vnd"),
    )
```

Append to `repayment_capacity.py`:

```python
RF07_THRESHOLD = 0.30
RF07_POLICY_VERSION = "policy_mode=DEMO_UAT (ngưỡng demo, chưa xác nhận chuẩn MSB chính thức)"


def evaluate_rf07_high_interest_burden(inputs: EbFinancialInputs, field_evidence: dict | None = None) -> RuleResult:
    from .profitability import resolve_ebit_vnd

    ebit = resolve_ebit_vnd(inputs)
    if ebit is None or not inputs.interest_expense_vnd or ebit <= 0:
        return RuleResult(
            rule_id="RF07", rule_name="Chi phí lãi vay lớn bất thường so với EBIT", status="CHƯA ĐÁNH GIÁ",
            comment="Thiếu EBIT hoặc chi phí lãi vay để đánh giá.",
            verification_question="Hồ sơ có LNTT, chi phí lãi vay đầy đủ để tính EBIT không?",
            recommended_action="Bổ sung báo cáo kết quả kinh doanh chi tiết.",
        )
    ratio = round(inputs.interest_expense_vnd / ebit, 4)
    if ratio > RF07_THRESHOLD:
        return RuleResult(
            rule_id="RF07", rule_name="Chi phí lãi vay lớn bất thường so với EBIT", status="KÍCH HOẠT", severity="MEDIUM",
            evidence=[f"Chi phí lãi vay / EBIT = {ratio} (> {RF07_THRESHOLD})"],
            threshold=f"quy tắc demo: > {RF07_THRESHOLD * 100:.0f}% EBIT",
            comment="Cảnh báo sớm trước khi ICR chạm ngưỡng 1.5x — cấu trúc chi phí lãi vay đã cao.",
            observed_value=ratio, policy_version=RF07_POLICY_VERSION,
            verification_question="Cơ cấu kỳ hạn nợ và khả năng đàm phán lãi suất hiện tại thế nào?",
            recommended_action="Xem xét cơ cấu kỳ hạn nợ hoặc bổ sung nguồn trả nợ.",
        )
    return RuleResult(
        rule_id="RF07", rule_name="Chi phí lãi vay lớn bất thường so với EBIT", status="KHÔNG KÍCH HOẠT",
        observed_value=ratio, policy_version=RF07_POLICY_VERSION,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/usr/local/bin/python -m pytest tests/agents/eb/test_leverage.py tests/agents/eb/test_repayment_capacity.py -v`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add app/agents/eb/leverage.py app/agents/eb/repayment_capacity.py tests/agents/eb/test_leverage.py tests/agents/eb/test_repayment_capacity.py
git commit -m "feat(eb): add RF06 (receivables/inventory concentration) and RF07 (high interest burden)"
```

---

### Task 10: Router wiring for all new metrics and flags

**Files:**
- Modify: `app/agents/eb/router.py`
- Test: `tests/agents/eb/test_router.py`

**Interfaces:**
- Consumes: every function from Tasks 5, 6, 8, 9

- [ ] **Step 1: Write the failing test**

```python
# appended to tests/agents/eb/test_router.py
def test_assess_endpoint_includes_new_metrics_and_flags(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test_new_metrics.db"))
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(eb_router, "generate_narrative", lambda computed: {"why": [], "credit_memo": ""})

    client = TestClient(app)
    csv_text = (
        b"Chi tieu,31/12/2025\n"
        b"Von chu so huu,500000000\n"
        b"Tai san ngan han,300000000\n"
        b"No ngan han,100000000\n"
        b"Tai san dai han,400000000\n"
        b"No dai han,100000000\n"
        b"Phai thu khach hang,150000000\n"
        b"Hang ton kho,100000000\n"
        b"Loi nhuan truoc thue,200000000\n"
        b"Loi nhuan sau thue,160000000\n"
        b"Chi phi lai vay,50000000\n"
        b"Khau hao,20000000\n"
    )
    files = {"files": ("bctc.csv", io.BytesIO(csv_text), "text/csv")}
    resp = client.post(
        "/api/eb/assess",
        data={"customer_name": "CONG TY TNHH TEST", "tax_id": "0100000001"},
        files=files,
    )
    assert resp.status_code == 200
    body = resp.json()
    for key in ("ebitda", "liquidity_balance", "long_term_capital", "total_borrowings", "receivables_financing_limit_80", "receivables_financing_limit_85"):
        assert key in body["credit_engine"], f"{key} missing from credit_engine"
    assert "capital_balance_check" in body
    rule_ids = {f["rule_id"] for f in body["risk_flags"]}
    assert {"RF06", "RF07"}.issubset(rule_ids)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/usr/local/bin/python -m pytest tests/agents/eb/test_router.py -k new_metrics -v`
Expected: FAIL — new keys absent from response

- [ ] **Step 3: Write the implementation**

In `router.py`, add imports and wire into `metrics_by_name`/`risk_flags`:

```python
from .capital_structure import (
    compute_capital_balance_check, compute_liquidity_balance,
    compute_long_term_capital, compute_total_borrowings,
)
from .contract_financing import compute_output_contract_financing_ratio, compute_receivables_financing_limit
from .leverage import evaluate_rf06_receivables_inventory_concentration
from .profitability import compute_ebitda
from .repayment_capacity import evaluate_rf07_high_interest_burden
```

Inside `assess()`, after the existing metric computations:

```python
        ebitda = compute_ebitda(financial_inputs, field_evidence)
        liquidity_balance = compute_liquidity_balance(financial_inputs, field_evidence)
        long_term_capital = compute_long_term_capital(financial_inputs, field_evidence)
        total_borrowings = compute_total_borrowings(financial_inputs, field_evidence)
        capital_balance_check = compute_capital_balance_check(financial_inputs, nwc, long_term_capital)
        receivables_financing_limit_80 = compute_receivables_financing_limit(financial_inputs.receivables_vnd, ltv=0.80)
        receivables_financing_limit_85 = compute_receivables_financing_limit(financial_inputs.receivables_vnd, ltv=0.85)

        risk_flags.append(evaluate_rf06_receivables_inventory_concentration(financial_inputs, field_evidence))
        risk_flags.append(evaluate_rf07_high_interest_burden(financial_inputs, field_evidence))
        activated_flags = [f for f in risk_flags if f.status == "KÍCH HOẠT"]  # recomputed after RF06/RF07 append
```

Extend `metrics_by_name`:

```python
        metrics_by_name = {
            "nwc": nwc, "current_ratio": current_ratio,
            "short_term_debt_ratio": short_term_debt_ratio, "dscr": dscr, "icr": icr,
            "output_contract_financing_ratio": output_contract_ratio,
            "ebitda": ebitda, "liquidity_balance": liquidity_balance,
            "long_term_capital": long_term_capital, "total_borrowings": total_borrowings,
            "receivables_financing_limit_80": receivables_financing_limit_80,
            "receivables_financing_limit_85": receivables_financing_limit_85,
        }
```

Add to `computed`:

```python
            "capital_balance_check": capital_balance_check,
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/usr/local/bin/python -m pytest tests/agents/eb/test_router.py -v`
Expected: all pass

Run: `/usr/local/bin/python -m pytest -q` (full suite) — expect all green
except `test_stress_test.py` (Task 12 fixes it).

- [ ] **Step 5: Commit**

```bash
git add app/agents/eb/router.py tests/agents/eb/test_router.py
git commit -m "feat(eb): wire new metrics and RF06/RF07 into /api/eb/assess response"
```

---

## Part C — Stress Test v2 backend

### Task 11: Deterministic stress-test conclusions/actions

**Files:**
- Create: `app/agents/eb/stress_conclusions.py`
- Test: `tests/agents/eb/test_stress_conclusions.py`

**Interfaces:**
- Produces:
  ```python
  def generate_conclusions(before: dict, after: dict, comprehensive: bool) -> list[str]
  def generate_recommended_actions(before: dict, after: dict) -> list[str]
  ```
  `before`/`after` are `{"dscr": Metric, "icr": Metric, ...}` dicts (as
  already produced by `compute_dscr`/`compute_icr`, `asdict`-friendly).

- [ ] **Step 1: Write the failing tests**

```python
# tests/agents/eb/test_stress_conclusions.py
from app.engine.core.types import Metric
from app.agents.eb.stress_conclusions import generate_conclusions, generate_recommended_actions


def _metric(value, status="OK"):
    return Metric(metric="m", value=value, formula="f", input_values={}, input_sources={}, status=status)


def test_conclusion_cites_dscr_crossing_below_threshold():
    before = {"dscr": _metric(1.28), "icr": _metric(2.0)}
    after = {"dscr": _metric(0.94), "icr": _metric(1.8)}
    conclusions = generate_conclusions(before, after, comprehensive=False)
    assert any("1.28" in c and "0.94" in c and "1.0" in c for c in conclusions)


def test_conclusion_cites_icr_degradation():
    before = {"dscr": _metric(1.5), "icr": _metric(1.8)}
    after = {"dscr": _metric(1.4), "icr": _metric(1.42)}
    conclusions = generate_conclusions(before, after, comprehensive=False)
    assert any("1.42" in c for c in conclusions)


def test_conclusions_capped_at_three():
    before = {"dscr": _metric(2.0), "icr": _metric(3.0)}
    after = {"dscr": _metric(0.5), "icr": _metric(0.5)}
    conclusions = generate_conclusions(before, after, comprehensive=False)
    assert len(conclusions) <= 3


def test_no_conclusions_when_nothing_crosses_a_threshold():
    before = {"dscr": _metric(2.0), "icr": _metric(3.0)}
    after = {"dscr": _metric(1.9), "icr": _metric(2.9)}
    assert generate_conclusions(before, after, comprehensive=False) == []


def test_recommended_actions_ordered_when_dscr_weak_after_stress():
    before = {"dscr": _metric(1.3), "icr": _metric(2.0)}
    after = {"dscr": _metric(0.9), "icr": _metric(1.6)}
    actions = generate_recommended_actions(before, after)
    assert actions[0].startswith("Yêu cầu bảng tuổi nợ")


def test_no_recommended_actions_when_nothing_degrades_past_threshold():
    before = {"dscr": _metric(2.0), "icr": _metric(3.0)}
    after = {"dscr": _metric(1.9), "icr": _metric(2.9)}
    assert generate_recommended_actions(before, after) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/local/bin/python -m pytest tests/agents/eb/test_stress_conclusions.py -v`
Expected: FAIL — module does not exist

- [ ] **Step 3: Write the implementation**

```python
# app/agents/eb/stress_conclusions.py
"""Deterministic template-filled conclusions/actions for Stress Test v2 —
no LLM call, same reasoning as the Cross-sell agent's scenario_templates.py:
filling a fixed template from already-computed numbers rules out both
hallucination and latency risk for a synchronous endpoint."""

DSCR_THRESHOLD = 1.0
ICR_THRESHOLD = 1.5

_ACTIONS_IN_ORDER = [
    "Yêu cầu bảng tuổi nợ phải thu và xác minh chất lượng bên mua.",
    "Rà soát dòng tiền trả nợ và lịch trả nợ chi tiết.",
    "Xem xét điều chỉnh kỳ hạn, điều kiện giải ngân hoặc cơ chế kiểm soát dòng tiền.",
    "Với QĐ 039: chỉ đề xuất hạn mức trên phần phải thu đủ điều kiện sau thẩm định bên mua/hóa đơn.",
]


def _ok(metric) -> bool:
    return metric.status == "OK" and metric.value is not None


def generate_conclusions(before: dict, after: dict, comprehensive: bool) -> list[str]:
    conclusions: list[str] = []
    dscr_before, dscr_after = before.get("dscr"), after.get("dscr")
    icr_before, icr_after = before.get("icr"), after.get("icr")

    if dscr_before and dscr_after and _ok(dscr_before) and _ok(dscr_after) and dscr_after.value < DSCR_THRESHOLD <= dscr_before.value:
        conclusions.append(
            f"Trong kịch bản này, DSCR giảm từ {dscr_before.value:.2f}x xuống {dscr_after.value:.2f}x, "
            f"dưới ngưỡng {DSCR_THRESHOLD:.1f}x."
        )
    if icr_before and icr_after and _ok(icr_before) and _ok(icr_after) and icr_after.value < ICR_THRESHOLD:
        conclusions.append(
            f"Chi phí lãi vay tăng khiến ICR giảm xuống {icr_after.value:.2f}x, cần xem xét cơ cấu kỳ hạn nợ "
            "hoặc bổ sung nguồn trả nợ."
        )
    if dscr_before and dscr_after and _ok(dscr_before) and _ok(dscr_after) and dscr_after.value < dscr_before.value and dscr_after.value >= DSCR_THRESHOLD:
        conclusions.append(
            f"DSCR giảm từ {dscr_before.value:.2f}x xuống {dscr_after.value:.2f}x nhưng vẫn trên ngưỡng "
            f"{DSCR_THRESHOLD:.1f}x — vùng đệm mỏng hơn."
        )
    return conclusions[:3]


def generate_recommended_actions(before: dict, after: dict) -> list[str]:
    dscr_after, icr_after = after.get("dscr"), after.get("icr")
    dscr_weak = dscr_after and _ok(dscr_after) and dscr_after.value < DSCR_THRESHOLD
    icr_weak = icr_after and _ok(icr_after) and icr_after.value < ICR_THRESHOLD
    if not (dscr_weak or icr_weak):
        return []
    return list(_ACTIONS_IN_ORDER)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/usr/local/bin/python -m pytest tests/agents/eb/test_stress_conclusions.py -v`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add app/agents/eb/stress_conclusions.py tests/agents/eb/test_stress_conclusions.py
git commit -m "feat(eb): add deterministic stress-test conclusions and RM action templates"
```

---

### Task 12: Stress Test v2 core rewrite

**Files:**
- Modify: `app/agents/eb/stress_test.py`
- Modify: `tests/agents/eb/test_stress_test.py` (full rewrite — old file used `cfads_vnd`/`margin_pct` contract)

**Interfaces:**
- Consumes: `compute_dscr(..., comprehensive=...)` (Task 7), `compute_nwc`
  (existing), `generate_conclusions`/`generate_recommended_actions` (Task 11)
- Produces:
  ```python
  def run_stress_test(
      inputs: EbFinancialInputs,
      revenue_pct: float = 0.0, ebit_pct: float = 0.0, interest_pct: float = 0.0,
      receivable_days_add: float = 0.0, inventory_pct: float = 0.0,
      principal_due_pct: float = 0.0, comprehensive: bool = False,
  ) -> dict
  ```

- [ ] **Step 1: Write the failing tests**

```python
# tests/agents/eb/test_stress_test.py (full replacement)
from app.agents.eb.financial_inputs import EbFinancialInputs
from app.agents.eb.stress_test import run_stress_test


def _base_inputs():
    return EbFinancialInputs(
        net_revenue_vnd=1_000_000_000, pbt_vnd=200_000_000, pat_vnd=160_000_000,
        interest_expense_vnd=50_000_000, interest_due_vnd=50_000_000, principal_due_vnd=100_000_000,
        depreciation_vnd=20_000_000, current_assets_vnd=400_000_000, current_liabilities_vnd=200_000_000,
        receivables_vnd=150_000_000, inventory_vnd=100_000_000,
    )


def test_revenue_and_ebit_deltas_apply_independently():
    result = run_stress_test(_base_inputs(), revenue_pct=-10, ebit_pct=-15)
    assert result["after"]["revenue"] == 900_000_000
    ebit_before = 200_000_000 + 50_000_000  # PBT + interest
    assert result["after"]["ebit"] == round(ebit_before * 0.85, 2)


def test_interest_pct_scales_interest_expense_and_debt_service():
    result = run_stress_test(_base_inputs(), interest_pct=15)
    assert result["after"]["interest_expense"] == round(50_000_000 * 1.15, 2)


def test_nwc_impact_quantifiable_true_when_all_inputs_present():
    result = run_stress_test(_base_inputs(), receivable_days_add=15, inventory_pct=10)
    assert result["nwc_impact_quantifiable"] is True


def test_nwc_impact_not_quantifiable_without_revenue():
    inputs = _base_inputs()
    inputs.net_revenue_vnd = None
    result = run_stress_test(inputs, receivable_days_add=15)
    assert result["nwc_impact_quantifiable"] is False


def test_comprehensive_mode_uses_total_principal_due():
    inputs = _base_inputs()
    inputs.total_principal_due_vnd = 120_000_000
    result = run_stress_test(inputs, comprehensive=True)
    assert "Tổng nghĩa vụ nợ" in result["before"]["debt_service_label"]


def test_buffers_computed_when_metrics_ok():
    result = run_stress_test(_base_inputs())
    assert "dscr_buffer" in result["buffers"]
    assert "icr_buffer" in result["buffers"]


def test_disclaimer_present():
    result = run_stress_test(_base_inputs())
    assert result["disclaimer"] == "Mô phỏng theo giả định — không thay thế thẩm định tín dụng và phê duyệt MSB."


def test_conclusions_and_actions_lists_present():
    result = run_stress_test(_base_inputs(), revenue_pct=-20, ebit_pct=-30, interest_pct=30)
    assert isinstance(result["conclusions"], list)
    assert isinstance(result["recommended_actions"], list)


def test_ebit_forced_non_positive_after_stress_keeps_icr_need_more_data_not_negative_ratio():
    inputs = _base_inputs()
    inputs.pbt_vnd = 10_000_000  # EBIT before = 60M
    result = run_stress_test(inputs, ebit_pct=-200)  # after EBIT <= 0
    assert result["after"]["icr"]["status"] == "NEED_MORE_DATA"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/local/bin/python -m pytest tests/agents/eb/test_stress_test.py -v`
Expected: FAIL — old contract, `revenue`/`ebit` keys absent

- [ ] **Step 3: Write the implementation**

```python
# app/agents/eb/stress_test.py
from dataclasses import replace

from .financial_inputs import EbFinancialInputs
from .liquidity import compute_nwc
from .profitability import resolve_ebit_vnd
from .repayment_capacity import compute_dscr, compute_icr
from .stress_conclusions import generate_conclusions, generate_recommended_actions

DISCLAIMER = "Mô phỏng theo giả định — không thay thế thẩm định tín dụng và phê duyệt MSB."


def _metric_dict(metric) -> dict:
    from dataclasses import asdict
    return asdict(metric)


def run_stress_test(
    inputs: EbFinancialInputs,
    revenue_pct: float = 0.0,
    ebit_pct: float = 0.0,
    interest_pct: float = 0.0,
    receivable_days_add: float = 0.0,
    inventory_pct: float = 0.0,
    principal_due_pct: float = 0.0,
    comprehensive: bool = False,
) -> dict:
    ebit_before = resolve_ebit_vnd(inputs)
    dscr_before = compute_dscr(inputs, comprehensive=comprehensive)
    icr_before = compute_icr(inputs)

    stressed = replace(inputs)
    if stressed.net_revenue_vnd is not None:
        stressed.net_revenue_vnd = round(stressed.net_revenue_vnd * (1 + revenue_pct / 100), 2)
    if stressed.pbt_vnd is not None:
        stressed.pbt_vnd = round(stressed.pbt_vnd * (1 + ebit_pct / 100), 2)
    if stressed.pat_vnd is not None:
        stressed.pat_vnd = round(stressed.pat_vnd * (1 + ebit_pct / 100), 2)
    if stressed.interest_expense_vnd is not None:
        stressed.interest_expense_vnd = round(stressed.interest_expense_vnd * (1 + interest_pct / 100), 2)
    if stressed.interest_due_vnd is not None:
        stressed.interest_due_vnd = round(stressed.interest_due_vnd * (1 + interest_pct / 100), 2)
    if comprehensive and stressed.total_principal_due_vnd is not None:
        stressed.total_principal_due_vnd = round(stressed.total_principal_due_vnd * (1 + principal_due_pct / 100), 2)
    elif stressed.principal_due_vnd is not None:
        stressed.principal_due_vnd = round(stressed.principal_due_vnd * (1 + principal_due_pct / 100), 2)

    ebit_after = resolve_ebit_vnd(stressed)
    if ebit_after is not None and ebit_after <= 0:
        stressed.pbt_vnd = None  # forces ICR/DSCR's EBIT-dependent paths to NEED_MORE_DATA below

    dscr_after = compute_dscr(stressed, comprehensive=comprehensive)
    icr_after = compute_icr(stressed)

    nwc_impact_quantifiable = all(
        v is not None for v in (inputs.receivables_vnd, inputs.inventory_vnd, inputs.net_revenue_vnd)
    )
    nwc_before = compute_nwc(inputs)
    if nwc_impact_quantifiable:
        daily_revenue = inputs.net_revenue_vnd / 365
        receivable_delta = daily_revenue * receivable_days_add
        inventory_delta = inputs.inventory_vnd * (inventory_pct / 100)
        stressed_assets = (
            inputs.current_assets_vnd + receivable_delta + inventory_delta
            if inputs.current_assets_vnd is not None else None
        )
        nwc_after = compute_nwc(replace(inputs, current_assets_vnd=stressed_assets)) if stressed_assets is not None else nwc_before
    else:
        nwc_after = nwc_before

    debt_service_label = "Tổng nghĩa vụ nợ" if comprehensive else "Nghĩa vụ nợ dài hạn đến hạn"
    principal_before = inputs.total_principal_due_vnd if comprehensive else inputs.principal_due_vnd
    interest_before = inputs.interest_expense_vnd if comprehensive else inputs.interest_due_vnd
    principal_after = stressed.total_principal_due_vnd if comprehensive else stressed.principal_due_vnd
    interest_after = stressed.interest_expense_vnd if comprehensive else stressed.interest_due_vnd

    before = {
        "revenue": inputs.net_revenue_vnd, "ebit": ebit_before,
        "interest_expense": inputs.interest_expense_vnd,
        "nwc": nwc_before, "dscr": dscr_before, "icr": icr_before,
        "debt_service_label": debt_service_label,
        "principal_due": principal_before, "debt_service_total": (
            (principal_before or 0) + (interest_before or 0) if principal_before is not None and interest_before is not None else None
        ),
    }
    after = {
        "revenue": stressed.net_revenue_vnd, "ebit": ebit_after,
        "interest_expense": stressed.interest_expense_vnd,
        "nwc": nwc_after, "dscr": dscr_after, "icr": icr_after,
        "debt_service_label": debt_service_label,
        "principal_due": principal_after, "debt_service_total": (
            (principal_after or 0) + (interest_after or 0) if principal_after is not None and interest_after is not None else None
        ),
    }

    buffers = {}
    if dscr_after.status == "OK":
        buffers["dscr_buffer"] = round(dscr_after.value - 1.0, 4)
    if icr_after.status == "OK":
        buffers["icr_buffer"] = round(icr_after.value - 1.5, 4)

    conclusions = generate_conclusions({"dscr": dscr_before, "icr": icr_before}, {"dscr": dscr_after, "icr": icr_after}, comprehensive)
    recommended_actions = generate_recommended_actions({"dscr": dscr_before, "icr": icr_before}, {"dscr": dscr_after, "icr": icr_after})

    return {
        "assumptions": {
            "human_readable": (
                f"Doanh thu thay đổi {revenue_pct:g}%, EBIT thay đổi {ebit_pct:g}%, "
                f"chi phí lãi vay thay đổi {interest_pct:g}%."
            ),
            "deltas": {
                "revenue_pct": revenue_pct, "ebit_pct": ebit_pct, "interest_pct": interest_pct,
                "receivable_days_add": receivable_days_add, "inventory_pct": inventory_pct,
                "principal_due_pct": principal_due_pct,
            },
            "comprehensive_mode": comprehensive,
        },
        "before": {**before, "nwc": _metric_dict(before["nwc"]), "dscr": _metric_dict(before["dscr"]), "icr": _metric_dict(before["icr"])},
        "after": {**after, "nwc": _metric_dict(after["nwc"]), "dscr": _metric_dict(after["dscr"]), "icr": _metric_dict(after["icr"])},
        "nwc_impact_quantifiable": nwc_impact_quantifiable,
        "buffers": buffers,
        "conclusions": conclusions,
        "recommended_actions": recommended_actions,
        "disclaimer": DISCLAIMER,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/usr/local/bin/python -m pytest tests/agents/eb/test_stress_test.py -v`
Expected: all pass

Run: `/usr/local/bin/python -m pytest -q` (full suite) — expect all green now.

- [ ] **Step 5: Commit**

```bash
git add app/agents/eb/stress_test.py tests/agents/eb/test_stress_test.py
git commit -m "feat(eb): rewrite stress test with independent revenue/EBIT deltas, NWC impact, buffers, conclusions"
```

---

### Task 13: Scenario persistence (DB table + save/list)

**Files:**
- Modify: `app/storage/db.py`
- Create: `app/agents/eb/stress_scenarios.py`
- Test: `tests/storage/test_db.py` (or wherever existing db tests live — check
  with `ls tests/storage/` first; if none, create `tests/storage/test_db.py`
  following the pattern of `app/storage/repository.py`'s own tests), `tests/agents/eb/test_stress_scenarios.py`

**Interfaces:**
- Produces:
  ```python
  def save_scenario(db_path, case_id, name, created_by, report_period, request, response) -> int
  def list_scenarios(db_path, case_id) -> list[dict]
  ```

- [ ] **Step 1: Write the failing tests**

```python
# tests/agents/eb/test_stress_scenarios.py
from app.storage.db import init_db
from app.agents.eb.stress_scenarios import list_scenarios, save_scenario


def test_save_and_list_scenario(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    scenario_id = save_scenario(
        db_path, case_id="EB-123", name="Thận trọng", created_by="RM Nam",
        report_period="2025", request={"preset": "than_trong"}, response={"after": {}},
    )
    assert scenario_id > 0
    scenarios = list_scenarios(db_path, "EB-123")
    assert len(scenarios) == 1
    assert scenarios[0]["name"] == "Thận trọng"
    assert scenarios[0]["created_by"] == "RM Nam"
    assert scenarios[0]["request"] == {"preset": "than_trong"}


def test_list_scenarios_newest_first(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    save_scenario(db_path, "EB-123", "A", "RM", "2025", {}, {})
    save_scenario(db_path, "EB-123", "B", "RM", "2025", {}, {})
    scenarios = list_scenarios(db_path, "EB-123")
    assert [s["name"] for s in scenarios] == ["B", "A"]


def test_list_scenarios_scoped_to_case_id(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    save_scenario(db_path, "EB-123", "A", "RM", "2025", {}, {})
    save_scenario(db_path, "EB-456", "B", "RM", "2025", {}, {})
    assert len(list_scenarios(db_path, "EB-123")) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/local/bin/python -m pytest tests/agents/eb/test_stress_scenarios.py -v`
Expected: FAIL — module/table does not exist

- [ ] **Step 3: Write the implementation**

In `app/storage/db.py`, add to `SCHEMA`:

```python
CREATE TABLE IF NOT EXISTS eb_stress_scenarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id TEXT NOT NULL,
    name TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    report_period TEXT,
    request_json TEXT NOT NULL,
    response_json TEXT NOT NULL
);
```

```python
# app/agents/eb/stress_scenarios.py
import json

from app.storage.db import get_connection


def save_scenario(
    db_path: str, case_id: str, name: str, created_by: str,
    report_period: str | None, request: dict, response: dict,
) -> int:
    conn = get_connection(db_path)
    try:
        cur = conn.execute(
            "INSERT INTO eb_stress_scenarios (case_id, name, created_by, report_period, request_json, response_json) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (case_id, name, created_by, report_period, json.dumps(request, ensure_ascii=False), json.dumps(response, ensure_ascii=False)),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def list_scenarios(db_path: str, case_id: str) -> list[dict]:
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM eb_stress_scenarios WHERE case_id = ? ORDER BY id DESC", (case_id,),
        ).fetchall()
        return [
            {
                "id": row["id"], "case_id": row["case_id"], "name": row["name"],
                "created_by": row["created_by"], "created_at": row["created_at"],
                "report_period": row["report_period"],
                "request": json.loads(row["request_json"]), "response": json.loads(row["response_json"]),
            }
            for row in rows
        ]
    finally:
        conn.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/usr/local/bin/python -m pytest tests/agents/eb/test_stress_scenarios.py -v`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add app/storage/db.py app/agents/eb/stress_scenarios.py tests/agents/eb/test_stress_scenarios.py
git commit -m "feat(eb): persist named stress-test scenarios"
```

---

### Task 14: Router endpoints — Stress Test v2 + scenarios

**Files:**
- Modify: `app/agents/eb/router.py`
- Test: `tests/agents/eb/test_router.py`

**Interfaces:**
- Consumes: `run_stress_test` (Task 12), `save_scenario`/`list_scenarios` (Task 13)

- [ ] **Step 1: Write the failing tests**

```python
# appended to tests/agents/eb/test_router.py
from fastapi.testclient import TestClient
from app.main import app


def test_stress_test_v2_endpoint_returns_new_contract():
    with TestClient(app) as client:
        resp = client.post(
            "/api/eb/stress-test",
            json={
                "inputs": {"net_revenue_vnd": 1_000_000_000, "pbt_vnd": 200_000_000, "pat_vnd": 160_000_000,
                           "interest_expense_vnd": 50_000_000, "interest_due_vnd": 50_000_000, "principal_due_vnd": 100_000_000,
                           "depreciation_vnd": 20_000_000},
                "deltas": {"revenue_pct": -10, "ebit_pct": -15, "interest_pct": 15},
            },
        )
    assert resp.status_code == 200
    body = resp.json()
    assert "conclusions" in body
    assert "buffers" in body
    assert body["disclaimer"]


def test_save_and_list_stress_scenario_endpoints(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "scenario_test.db"))
    from app.config import get_settings
    get_settings.cache_clear()
    with TestClient(app) as client:
        save_resp = client.post(
            "/api/eb/stress-test/scenarios",
            json={"case_id": "EB-123", "name": "Bất lợi", "created_by": "RM", "report_period": "2025",
                  "request": {"preset": "bat_loi"}, "response": {"after": {}}},
        )
        assert save_resp.status_code == 200
        list_resp = client.get("/api/eb/stress-test/scenarios", params={"case_id": "EB-123"})
    assert list_resp.status_code == 200
    assert list_resp.json()["scenarios"][0]["name"] == "Bất lợi"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/local/bin/python -m pytest tests/agents/eb/test_router.py -k "stress_test_v2 or scenario" -v`
Expected: FAIL — old `/stress-test` contract, no `/stress-test/scenarios` routes

- [ ] **Step 3: Write the implementation**

Replace the existing `/stress-test` handler in `router.py` and add two new ones:

```python
from .stress_scenarios import list_scenarios, save_scenario


@router.post("/stress-test")
async def stress_test(payload: dict) -> dict:
    from .financial_inputs import EbFinancialInputs

    raw_inputs = payload.get("inputs", {})
    valid_fields = set(EbFinancialInputs.__dataclass_fields__)
    inputs = EbFinancialInputs(**{k: v for k, v in raw_inputs.items() if k in valid_fields})
    deltas = payload.get("deltas", {})
    return run_stress_test(
        inputs,
        revenue_pct=deltas.get("revenue_pct", 0.0),
        ebit_pct=deltas.get("ebit_pct", 0.0),
        interest_pct=deltas.get("interest_pct", 0.0),
        receivable_days_add=deltas.get("receivable_days_add", 0.0),
        inventory_pct=deltas.get("inventory_pct", 0.0),
        principal_due_pct=deltas.get("principal_due_pct", 0.0),
        comprehensive=payload.get("comprehensive_mode", False),
    )


@router.post("/stress-test/scenarios")
async def save_stress_scenario(payload: dict) -> dict:
    settings = get_settings()
    init_db(settings.db_path)
    scenario_id = save_scenario(
        settings.db_path,
        case_id=payload["case_id"], name=payload["name"], created_by=payload.get("created_by", "RM"),
        report_period=payload.get("report_period"), request=payload.get("request", {}), response=payload.get("response", {}),
    )
    return {"id": scenario_id}


@router.get("/stress-test/scenarios")
async def get_stress_scenarios(case_id: str) -> dict:
    settings = get_settings()
    init_db(settings.db_path)
    return {"scenarios": list_scenarios(settings.db_path, case_id)}
```

Update the `from .stress_test import run_stress_test` import (unchanged name,
new signature already handled by Task 12).

- [ ] **Step 4: Run tests to verify they pass**

Run: `/usr/local/bin/python -m pytest tests/agents/eb/test_router.py -v`
Expected: all pass

Run: `/usr/local/bin/python -m pytest -q` — full suite green.

- [ ] **Step 5: Commit**

```bash
git add app/agents/eb/router.py tests/agents/eb/test_router.py
git commit -m "feat(eb): expose stress test v2 and scenario save/list endpoints"
```

---

### Task 15: MB02a export — attach selected stress scenario

**Files:**
- Modify: `app/agents/eb/mb02_export.py`
- Modify: `app/agents/eb/router.py` (`/export` endpoint)
- Test: `tests/agents/eb/test_mb02_export.py`

**Interfaces:**
- Produces: `build_mb02_docx(computed: dict, stress_scenario: dict | None = None) -> bytes`

- [ ] **Step 1: Write the failing test**

```python
# appended to tests/agents/eb/test_mb02_export.py
import docx
import io
from app.agents.eb.mb02_export import build_mb02_docx


def test_export_includes_stress_scenario_section_when_provided():
    scenario = {
        "name": "Thận trọng",
        "request": {"deltas": {"revenue_pct": -10, "ebit_pct": -15, "interest_pct": 15}},
        "response": {"before": {"dscr": {"value": 1.3}}, "after": {"dscr": {"value": 0.95}}},
    }
    docx_bytes = build_mb02_docx({"customer_profile": {"customer_name": "X", "tax_id": "1"}}, stress_scenario=scenario)
    document = docx.Document(io.BytesIO(docx_bytes))
    full_text = "\n".join(p.text for p in document.paragraphs)
    assert "Thận trọng" in full_text
    assert "0.95" in full_text


def test_export_without_stress_scenario_is_unaffected():
    docx_bytes = build_mb02_docx({"customer_profile": {"customer_name": "X", "tax_id": "1"}})
    assert len(docx_bytes) > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/usr/local/bin/python -m pytest tests/agents/eb/test_mb02_export.py -k stress_scenario -v`
Expected: FAIL — `build_mb02_docx` has no `stress_scenario` parameter

- [ ] **Step 3: Write the implementation**

In `mb02_export.py`, change the signature and append a section near the end
(before the document is saved to bytes):

```python
def build_mb02_docx(computed: dict, stress_scenario: dict | None = None) -> bytes:
    ...  # existing body unchanged up to the final save
    if stress_scenario:
        document.add_heading("F. Kịch bản Stress Test đính kèm", level=2)
        document.add_paragraph(f"Tên kịch bản: {stress_scenario.get('name', '[chưa có]')}")
        response = stress_scenario.get("response", {})
        before_dscr = _format_metric_value(response.get("before", {}).get("dscr"))
        after_dscr = _format_metric_value(response.get("after", {}).get("dscr"))
        document.add_paragraph(f"DSCR trước stress: {before_dscr} → sau stress: {after_dscr}")
        document.add_paragraph(
            "Mô phỏng theo giả định — không thay thế thẩm định tín dụng và phê duyệt MSB."
        )
    buf = io.BytesIO()
    document.save(buf)
    return buf.getvalue()
```

(Adjust to match this file's actual existing tail — read the last ~15 lines
of `mb02_export.py` before editing to place this block correctly relative
to the existing `document.save(...)` call.)

In `router.py`'s `/export` handler, accept the optional key:

```python
@router.post("/export")
async def export(payload: dict) -> Response:
    docx_bytes = build_mb02_docx(payload.get("computed", payload), payload.get("stress_scenario"))
    ...
```

(Check the current `/export` handler's exact body-parsing first — it
currently takes `computed: dict` directly as the whole body per the file
already read in this plan's research; adjust so existing callers that POST
the bare `computed` dict with no `stress_scenario` key keep working
unchanged — i.e. if `payload` has no `"computed"` key, treat the whole
payload as `computed` and `stress_scenario` as absent.)

- [ ] **Step 4: Run test to verify it passes**

Run: `/usr/local/bin/python -m pytest tests/agents/eb/test_mb02_export.py -v`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add app/agents/eb/mb02_export.py app/agents/eb/router.py tests/agents/eb/test_mb02_export.py
git commit -m "feat(eb): attach selected stress scenario to MB02a export"
```

---

## Part D — Frontend

### Task 16: Frontend types

**Files:**
- Modify: `web/lib/api.ts`

**Interfaces:**
- Produces: new exported TS types `HoSoPeriod`, `CapitalBalanceCheck`,
  `StressTestV2Result`, `StressScenario`; extends `AssessmentResult` and
  `runStressTest`.

- [ ] **Step 1–4: Add types, typecheck (no unit tests — this repo has no
  frontend test runner; verification is `tsc`)**

Add to `web/lib/api.ts`:

```ts
export type HoSoPeriod = { selected: string | null; available: string[] };

export type CapitalBalanceCheck = {
  trai: number | null;
  phai: number | null;
  trang_thai: string;
  nhan_xet: string;
};

export type StressTestMetric = { value: number | null; status: string };

export type StressTestV2Result = {
  assumptions: { human_readable: string; deltas: Record<string, number>; comprehensive_mode: boolean };
  before: Record<string, unknown> & { revenue: number | null; ebit: number | null; interest_expense: number | null; nwc: StressTestMetric; dscr: StressTestMetric; icr: StressTestMetric; debt_service_label: string; principal_due: number | null; debt_service_total: number | null };
  after: StressTestV2Result["before"];
  nwc_impact_quantifiable: boolean;
  buffers: { dscr_buffer?: number; icr_buffer?: number };
  conclusions: string[];
  recommended_actions: string[];
  disclaimer: string;
};

export type StressScenario = {
  id: number;
  case_id: string;
  name: string;
  created_by: string;
  created_at: string;
  report_period: string | null;
  request: Record<string, unknown>;
  response: StressTestV2Result;
};

export async function runStressTestV2(
  inputs: Record<string, number | null>,
  deltas: Record<string, number>,
  comprehensiveMode: boolean
): Promise<StressTestV2Result> {
  const resp = await fetch("/api/eb/stress-test", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ inputs, deltas, comprehensive_mode: comprehensiveMode }),
  });
  if (!resp.ok) throw new Error(`Stress test thất bại: HTTP ${resp.status}`);
  return resp.json();
}

export async function saveStressScenario(
  caseId: string, name: string, createdBy: string, reportPeriod: string | null,
  request: Record<string, unknown>, response: StressTestV2Result
): Promise<{ id: number }> {
  const resp = await fetch("/api/eb/stress-test/scenarios", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ case_id: caseId, name, created_by: createdBy, report_period: reportPeriod, request, response }),
  });
  if (!resp.ok) throw new Error(`Lưu kịch bản thất bại: HTTP ${resp.status}`);
  return resp.json();
}

export async function fetchStressScenarios(caseId: string): Promise<StressScenario[]> {
  const resp = await fetch(`/api/eb/stress-test/scenarios?case_id=${encodeURIComponent(caseId)}`);
  if (!resp.ok) throw new Error(`Không tải được danh sách kịch bản: HTTP ${resp.status}`);
  const body = await resp.json();
  return body.scenarios ?? [];
}
```

Extend `AssessmentResult` with:

```ts
  ho_so_period?: HoSoPeriod;
  capital_balance_check?: CapitalBalanceCheck;
```

- [ ] **Step 5: Verify and commit**

Run: `cd web && npx tsc --noEmit -p .`
Expected: no errors

```bash
git add web/lib/api.ts
git commit -m "feat(eb): add frontend types for period selection, capital balance, stress test v2"
```

---

### Task 17: Left column — CompanyInfoBlock + FinancialDataTable

**Files:**
- Create: `web/components/eb/CompanyInfoBlock.tsx`
- Create: `web/components/eb/FinancialDataTable.tsx`

**Interfaces:**
- Consumes: `AssessmentResult.ho_so_period`, `AssessmentResult.customer_profile`,
  `AssessmentResult.credit_engine` (for each field's `input_values`/`input_sources`)
- Produces: `<CompanyInfoBlock result={AssessmentResult} onPeriodChange={(year: string) => void} />`,
  `<FinancialDataTable creditEngine={Record<string, MetricValue>} />`

- [ ] **Step 1: Write the components**

```tsx
// web/components/eb/CompanyInfoBlock.tsx
"use client";

import { Building2, Calendar, FileText, IdCard } from "lucide-react";
import { AssessmentResult } from "@/lib/api";
import { SectionHeader } from "../shared/SectionHeader";

export function CompanyInfoBlock({
  result,
  onPeriodChange,
}: {
  result: AssessmentResult;
  onPeriodChange: (year: string) => void;
}) {
  const period = result.ho_so_period;
  return (
    <div className="bg-white rounded-xl border border-gray-100 p-5 space-y-3">
      <SectionHeader icon={Building2} title="Thông tin doanh nghiệp" />
      <div className="text-sm space-y-2">
        <div className="flex items-center gap-2">
          <Building2 className="h-3.5 w-3.5 text-gray-400 shrink-0" />
          <span className="font-medium text-msb-navy">{(result.customer_profile?.customer_name as string) ?? "—"}</span>
        </div>
        <div className="flex items-center gap-2">
          <IdCard className="h-3.5 w-3.5 text-gray-400 shrink-0" />
          <span>MST {(result.customer_profile?.tax_id as string) ?? "—"}</span>
        </div>
        {period && period.available.length > 0 && (
          <div className="flex items-center gap-2">
            <Calendar className="h-3.5 w-3.5 text-gray-400 shrink-0" />
            <label className="text-xs text-gray-500">Kỳ báo cáo</label>
            <select
              className="border border-gray-200 rounded-lg px-2 py-1 text-sm"
              value={period.selected ?? ""}
              onChange={(e) => onPeriodChange(e.target.value)}
            >
              {period.available.map((y) => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>
          </div>
        )}
        <div className="flex items-center gap-2 text-gray-500 text-xs">
          <FileText className="h-3.5 w-3.5 shrink-0" />
          {(result.documents ?? []).map((d) => d.filename).join(", ") || "Chưa có tệp"}
        </div>
      </div>
    </div>
  );
}
```

```tsx
// web/components/eb/FinancialDataTable.tsx
"use client";

import { useState } from "react";
import { MetricValue } from "../shared/MetricCard";

const FIELD_CODES: Record<string, { label: string; code: string; formula: string; group: string }> = {
  net_revenue_vnd: { label: "Doanh thu thuần", code: "IS_REVENUE", formula: "Doanh thu bán hàng − các khoản giảm trừ", group: "Kết quả kinh doanh" },
  pbt_vnd: { label: "Lợi nhuận trước thuế", code: "IS_PBT", formula: "Theo BCTC", group: "Kết quả kinh doanh" },
  pat_vnd: { label: "Lợi nhuận sau thuế", code: "IS_PAT", formula: "Theo BCTC", group: "Kết quả kinh doanh" },
  interest_expense_vnd: { label: "Chi phí lãi vay", code: "IS_INTEREST", formula: "Theo BCTC", group: "Kết quả kinh doanh" },
  depreciation_vnd: { label: "Khấu hao", code: "IS_DEPRECIATION", formula: "Theo BCTC", group: "Kết quả kinh doanh" },
  ebitda: { label: "EBITDA", code: "CALC_EBITDA", formula: "EBIT + Khấu hao", group: "Kết quả kinh doanh" },
  current_assets_vnd: { label: "Tài sản ngắn hạn", code: "BS_CURRENT_ASSETS", formula: "Theo BCTC", group: "Vốn và cơ cấu" },
  current_liabilities_vnd: { label: "Nợ ngắn hạn", code: "BS_CURRENT_LIABILITIES", formula: "Theo BCTC", group: "Vốn và cơ cấu" },
  non_current_assets_vnd: { label: "Tài sản dài hạn", code: "BS_NON_CURRENT_ASSETS", formula: "Theo BCTC", group: "Vốn và cơ cấu" },
  long_term_capital: { label: "Nguồn vốn dài hạn", code: "BS_LONG_TERM_CAPITAL", formula: "VCSH + Nợ dài hạn", group: "Vốn và cơ cấu" },
  total_borrowings: { label: "Tổng nợ vay", code: "BS_TOTAL_BORROWINGS", formula: "Vay ngắn hạn + dài hạn + thuê tài chính", group: "Vốn và cơ cấu" },
  receivables_vnd: { label: "Phải thu khách hàng", code: "BS003", formula: "Theo BCTC", group: "Vốn và cơ cấu" },
  inventory_vnd: { label: "Hàng tồn kho", code: "BS004", formula: "Theo BCTC", group: "Vốn và cơ cấu" },
  payables_vnd: { label: "Phải trả người bán", code: "BS005", formula: "Theo BCTC", group: "Vốn và cơ cấu" },
  equity_vnd: { label: "Vốn chủ sở hữu", code: "BS008", formula: "Theo BCTC", group: "Vốn và cơ cấu" },
  cash_vnd: { label: "Tiền và tương đương tiền", code: "BS_CASH", formula: "Theo BCTC", group: "Vốn và cơ cấu" },
};

function formatVndSmart(value: unknown): string {
  if (typeof value !== "number") return "—";
  const abs = Math.abs(value);
  if (abs >= 1_000_000_000) return `${(value / 1_000_000_000).toFixed(1)} tỷ`;
  if (abs >= 1_000_000) return `${Math.round(value / 1_000_000)} triệu`;
  return value.toLocaleString("vi-VN");
}

export function FinancialDataTable({ creditEngine }: { creditEngine?: Record<string, MetricValue> }) {
  const [openRow, setOpenRow] = useState<string | null>(null);
  const groups = ["Kết quả kinh doanh", "Vốn và cơ cấu"];

  function rowValue(key: string): { value: unknown; source?: string } {
    for (const metric of Object.values(creditEngine ?? {})) {
      if (metric.input_values && key in metric.input_values) {
        return { value: metric.input_values[key], source: metric.input_sources?.[key] };
      }
    }
    if (key === "ebitda" || key === "long_term_capital" || key === "total_borrowings") {
      const m = creditEngine?.[key];
      return { value: m?.value, source: "computed" };
    }
    return { value: undefined };
  }

  return (
    <div className="bg-white rounded-xl border border-gray-100 p-5 space-y-4">
      <h3 className="text-sm font-semibold text-msb-navy">Dữ liệu BCTC cốt lõi (VND)</h3>
      {groups.map((group) => (
        <div key={group}>
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1.5">{group}</p>
          <table className="w-full text-sm">
            <tbody>
              {Object.entries(FIELD_CODES)
                .filter(([, meta]) => meta.group === group)
                .map(([key, meta]) => {
                  const { value, source } = rowValue(key);
                  const hasValue = typeof value === "number";
                  return (
                    <tr key={key} className="border-b border-gray-50 last:border-0">
                      <td className="py-2 pr-2 align-top">
                        <button
                          className="text-left"
                          title={meta.formula}
                          onClick={() => setOpenRow(openRow === key ? null : key)}
                        >
                          <span className="text-msb-navy">{meta.label}</span>
                          <span className="block text-[10px] text-gray-400">{meta.code}</span>
                        </button>
                        {openRow === key && <p className="text-[11px] text-gray-500 mt-1">{meta.formula}</p>}
                      </td>
                      <td className="py-2 text-right align-top">
                        <span className={hasValue ? "text-msb-navy font-medium" : "text-gray-400"}>
                          {hasValue ? formatVndSmart(value) : "Chưa xác định từ hồ sơ tải lên"}
                        </span>
                        <span className="block text-[10px] text-gray-400">
                          {source === "manual_rm_input" ? "Người dùng điều chỉnh" : hasValue ? "AI trích xuất" : ""}
                        </span>
                      </td>
                    </tr>
                  );
                })}
            </tbody>
          </table>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Verify and commit**

Run: `cd web && npx tsc --noEmit -p .`
Expected: no errors

```bash
git add web/components/eb/CompanyInfoBlock.tsx web/components/eb/FinancialDataTable.tsx
git commit -m "feat(eb): add left-column company info and financial data table components"
```

---

### Task 18: Middle column — CapitalBalanceDiagram + Qd039Card

**Files:**
- Create: `web/components/eb/CapitalBalanceDiagram.tsx`
- Create: `web/components/eb/Qd039Card.tsx`

**Interfaces:**
- Consumes: `AssessmentResult.capital_balance_check`, `AssessmentResult.credit_engine.receivables_financing_limit_80/85`

- [ ] **Step 1: Write the components**

```tsx
// web/components/eb/CapitalBalanceDiagram.tsx
"use client";

import { Scale } from "lucide-react";
import { CapitalBalanceCheck } from "@/lib/api";
import { SectionHeader } from "../shared/SectionHeader";

function formatVnd(v: number | null): string {
  if (v === null) return "Chưa xác định từ hồ sơ tải lên";
  return `${(v / 1_000_000_000).toFixed(2)} tỷ`;
}

export function CapitalBalanceDiagram({ check }: { check?: CapitalBalanceCheck }) {
  if (!check) return null;
  const balanced = check.trang_thai === "Can bang";
  return (
    <div className="bg-white rounded-xl border border-gray-100 p-5 space-y-3">
      <SectionHeader icon={Scale} title="Cân đối tài chính" />
      <div className="flex items-center justify-center gap-3 text-sm">
        <div className="text-center">
          <p className="text-xs text-gray-400">Vốn lưu động ròng</p>
          <p className="font-semibold text-msb-navy">{formatVnd(check.trai)}</p>
        </div>
        <span className="text-gray-300">=</span>
        <div className="text-center">
          <p className="text-xs text-gray-400">Nguồn vốn dài hạn ròng</p>
          <p className="font-semibold text-msb-navy">{formatVnd(check.phai)}</p>
        </div>
      </div>
      <span
        className={`inline-block text-xs font-semibold px-2.5 py-1 rounded-full ${
          balanced ? "bg-green-100 text-green-800" : "bg-amber-100 text-amber-800"
        }`}
      >
        {balanced ? "Cân bằng" : check.trang_thai}
      </span>
      <p className="text-xs text-gray-500">{check.nhan_xet}</p>
    </div>
  );
}
```

```tsx
// web/components/eb/Qd039Card.tsx
"use client";

import { useState } from "react";
import { Sparkles } from "lucide-react";
import { MetricValue } from "../shared/MetricCard";

export function Qd039Card({ creditEngine }: { creditEngine?: Record<string, MetricValue> }) {
  const [ltv, setLtv] = useState<"80" | "85">("80");
  const metric = creditEngine?.[`receivables_financing_limit_${ltv}`];
  const hasValue = metric?.status === "OK" && metric.value !== null;

  return (
    <div className="bg-white rounded-xl border-2 border-msb-orange/30 p-5 space-y-3">
      <div className="flex items-center gap-2">
        <Sparkles className="h-4 w-4 text-msb-orange" />
        <h3 className="text-sm font-semibold text-msb-navy">Tài trợ Chuỗi QĐ 039</h3>
      </div>
      <div className="flex gap-2">
        {(["80", "85"] as const).map((v) => (
          <button
            key={v}
            onClick={() => setLtv(v)}
            className={`text-xs font-semibold px-3 py-1.5 rounded-full ${
              ltv === v ? "bg-msb-orange text-white" : "bg-gray-100 text-gray-600"
            }`}
          >
            LTV {v}%
          </button>
        ))}
      </div>
      <p className={`text-2xl font-bold ${hasValue ? "text-msb-navy" : "text-gray-400"}`}>
        {hasValue ? `${(Number(metric!.value) / 1_000_000_000).toFixed(2)} tỷ` : "Chưa xác định từ hồ sơ tải lên"}
      </p>
      {hasValue && (
        <p className="text-xs text-gray-500">
          Khoản phải thu khách hàng có thể mở ra hạn mức tài trợ tham chiếu {(Number(metric!.value) / 1_000_000_000).toFixed(2)} tỷ.
        </p>
      )}
      {ltv === "85" && metric?.policy_version && (
        <p className="text-xs text-amber-700 bg-amber-50 rounded-lg px-3 py-2">{metric.policy_version}</p>
      )}
      <p className="text-xs text-gray-400">
        Cần thẩm định điều kiện tài sản bảo đảm, bên mua và hồ sơ theo QĐ 039.
      </p>
      <p className="text-[11px] text-gray-400 border-t border-gray-100 pt-2">
        Khuyến nghị sơ bộ từ dữ liệu BCTC — cần phê duyệt theo quy trình tín dụng MSB.
      </p>
    </div>
  );
}
```

- [ ] **Step 2: Verify and commit**

Run: `cd web && npx tsc --noEmit -p .`
Expected: no errors

```bash
git add web/components/eb/CapitalBalanceDiagram.tsx web/components/eb/Qd039Card.tsx
git commit -m "feat(eb): add capital balance diagram and QĐ 039 card components"
```

---

### Task 19: EB-specific risk-flags priority list

**Files:**
- Create: `web/components/eb/EbRiskFlagsPriorityList.tsx`

Note: this is a **new, EB-only** component — the existing
`shared/RiskFlagsSection.tsx` stays untouched so RB and Cross-sell's display
is unaffected; only EB's redesigned middle column uses this one.

**Interfaces:**
- Consumes: `AssessmentResult.risk_flags` (`RiskFlag[]`)

- [ ] **Step 1: Write the component**

```tsx
// web/components/eb/EbRiskFlagsPriorityList.tsx
"use client";

import { AlertTriangle, HelpCircle } from "lucide-react";
import { ACTIVATED_STATUS, INSUFFICIENT_DATA_STATUS, RiskFlag } from "@/lib/api";
import { SectionHeader } from "../shared/SectionHeader";

const SEVERITY_STYLE: Record<string, string> = {
  CRITICAL: "border-red-400 bg-red-50/40",
  HIGH: "border-red-300 bg-red-50/30",
  MEDIUM: "border-amber-300 bg-amber-50/30",
  LOW: "border-gray-300 bg-gray-50/30",
};

export function EbRiskFlagsPriorityList({ flags }: { flags: RiskFlag[] }) {
  const activated = flags.filter((f) => f.status === ACTIVATED_STATUS);
  const undetermined = flags.filter((f) => f.status === INSUFFICIENT_DATA_STATUS);
  const priorityRows = [...activated, ...undetermined];

  return (
    <div className="bg-white rounded-xl border border-gray-100 p-5 space-y-3">
      <SectionHeader icon={AlertTriangle} title="Tín hiệu cần thẩm định thêm từ dữ liệu BCTC" />
      {priorityRows.length === 0 ? (
        <p className="text-sm text-gray-500">Không có tín hiệu cần thẩm định thêm trong số các quy tắc đã kiểm tra.</p>
      ) : (
        <ul className="space-y-2.5">
          {priorityRows.map((f, i) => {
            const isUndetermined = f.status === INSUFFICIENT_DATA_STATUS;
            return (
              <li
                key={i}
                className={`border-l-4 rounded-r-lg px-3 py-2.5 text-sm ${
                  isUndetermined ? "border-gray-300 bg-gray-50/40" : SEVERITY_STYLE[f.severity ?? "LOW"]
                }`}
              >
                <div className="flex items-center gap-2 font-semibold text-msb-navy">
                  {isUndetermined && <HelpCircle className="h-3.5 w-3.5 text-gray-400 shrink-0" />}
                  {f.rule_name ?? f.rule_id}
                  {f.severity && !isUndetermined && (
                    <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-white/70">{f.severity}</span>
                  )}
                </div>
                {f.impact && <p className="text-gray-600 mt-0.5">{f.impact}</p>}
                {f.recommended_action && (
                  <p className="text-xs text-gray-500 mt-1">
                    <span className="font-medium">Hành động RM:</span> {f.recommended_action}
                  </p>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify and commit**

Run: `cd web && npx tsc --noEmit -p .`
Expected: no errors

```bash
git add web/components/eb/EbRiskFlagsPriorityList.tsx
git commit -m "feat(eb): add EB-specific red-flags priority list (mức độ/chỉ tiêu/lý do/hành động RM)"
```

---

### Task 20: 3-column `EbResultPanel.tsx` layout wiring

**Files:**
- Modify: `web/components/EbResultPanel.tsx`

**Interfaces:**
- Consumes: all components from Tasks 17–19, `runStressTestV2` types (Task 16)

- [ ] **Step 1: Rewrite the layout**

Replace the `export default function EbResultPanel` body (keep
`OverviewTable`, `DocumentPanel`, `METRIC_LABELS`, `fileIconFor` etc. as they
are — only the top-level render and the old inline `StressTestPanel` change).
Remove the old `StressTestPanel` function entirely (superseded by Task 21's
`StressTestDrawer`). Add a `report_period` re-fetch: selecting a period
re-runs `/api/eb/assess` is out of scope for this task (that would require
re-uploading files) — instead, the period dropdown in `CompanyInfoBlock`
calls a new prop `onPeriodChange` that re-submits the **already-uploaded**
assessment with a different `report_period` value. Since `EbResultPanel`
doesn't own the upload files, thread this back up: add an optional
`onRerunWithPeriod?: (period: string) => void` prop, wired from `page.tsx`
in Task 22 style (page.tsx changes are NOT part of this plan's scope beyond
passing this one callback through — see Task 20 Step 3).

```tsx
import { CompanyInfoBlock } from "./eb/CompanyInfoBlock";
import { FinancialDataTable } from "./eb/FinancialDataTable";
import { CapitalBalanceDiagram } from "./eb/CapitalBalanceDiagram";
import { Qd039Card } from "./eb/Qd039Card";
import { EbRiskFlagsPriorityList } from "./eb/EbRiskFlagsPriorityList";
import { StressTestDrawer } from "./eb/StressTestDrawer";  // Task 21

const EXTENDED_METRIC_LABELS: Record<string, { label: string; unit: string; note?: string }> = {
  ...METRIC_LABELS,
  ebitda: { label: "EBITDA", unit: "VND" },
  liquidity_balance: { label: "Cân đối thanh khoản", unit: "" },
};

export default function EbResultPanel({
  result, onRerunWithPeriod,
}: {
  result: AssessmentResult;
  onRerunWithPeriod?: (period: string) => void;
}) {
  const overview = result.overview ?? [];
  const summary = result.overview_summary;
  const [stressOpen, setStressOpen] = useState(false);

  return (
    <div className="mt-6">
      <InfoBar
        items={[
          { icon: BadgeIcon, label: "Mã hồ sơ", value: result.case_id ?? "—" },
          { icon: Clock, label: "Thời điểm chạy", value: result.assessed_at ?? "—" },
        ]}
        banner={result.overall_conclusion}
      />

      <div className="grid grid-cols-1 lg:grid-cols-[380px_1fr_340px] gap-5 mt-5">
        {/* Cột trái */}
        <div className="space-y-5 order-4 lg:order-1">
          <CompanyInfoBlock result={result} onPeriodChange={(y) => onRerunWithPeriod?.(y)} />
          <FinancialDataTable creditEngine={result.credit_engine as Record<string, MetricValue> | undefined} />
        </div>

        {/* Cột giữa */}
        <div className="space-y-5 order-2">
          <div className="bg-white rounded-xl border border-gray-100 p-6 space-y-3">
            <SectionHeader
              icon={ClipboardList}
              title="Kết luận thẩm định"
              subtitle={
                summary
                  ? `${summary.checked}/${summary.total} điều kiện đã kiểm tra đủ dữ liệu; kỳ ${result.ho_so_period?.selected ?? "—"}.`
                  : undefined
              }
            />
            <p className="text-sm font-semibold text-msb-navy">{result.overall_conclusion ?? result.credit_readiness ?? "—"}</p>
            <p className="text-[11px] text-gray-400">
              Khuyến nghị sơ bộ từ dữ liệu BCTC — cần phê duyệt theo quy trình tín dụng MSB.
            </p>
          </div>

          {result.credit_engine && (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              {Object.entries(result.credit_engine)
                .filter(([key]) => key in EXTENDED_METRIC_LABELS)
                .map(([key, metric]) => {
                  const meta = EXTENDED_METRIC_LABELS[key];
                  return <MetricCard key={key} label={meta.label} unit={meta.unit} note={meta.note} metric={metric as MetricValue} />;
                })}
            </div>
          )}

          <CapitalBalanceDiagram check={result.capital_balance_check} />
          <Qd039Card creditEngine={result.credit_engine as Record<string, MetricValue> | undefined} />
          <EbRiskFlagsPriorityList flags={result.risk_flags ?? []} />
          <OverviewTable rows={overview} caseId={result.case_id} />
          <DocumentPanel documents={result.documents ?? []} />
        </div>

        {/* Cột phải */}
        <div className="space-y-5 order-3">
          <AiInsightSection why={result.why ?? []} creditMemo={result.credit_memo} title="M-Insight AI" />
          <div className="bg-white rounded-xl border border-gray-100 p-5 flex flex-wrap gap-2">
            <button onClick={() => setStressOpen(true)} className="text-xs font-semibold px-3 py-2 rounded-lg bg-msb-navy text-white">
              Stress Test
            </button>
            {result.export_available && (
              <button
                onClick={async () => {
                  try {
                    const blob = await exportMb02(result);
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement("a");
                    a.href = url; a.download = "to-trinh-mb02-du-thao.docx"; a.click();
                    URL.revokeObjectURL(url);
                  } catch (err) {
                    alert(err instanceof Error ? err.message : "Xuất tờ trình thất bại.");
                  }
                }}
                className="text-xs font-semibold px-3 py-2 rounded-lg border border-msb-navy text-msb-navy"
              >
                Soạn tờ trình MB02a
              </button>
            )}
          </div>
          <CrossSellOpportunities
            opportunities={result.crosssell_opportunities ?? []}
            title="Cơ hội bán chéo"
          />
        </div>
      </div>

      <StressTestDrawer
        open={stressOpen}
        onClose={() => setStressOpen(false)}
        result={result}
      />
    </div>
  );
}
```

(`CrossSellOpportunities`'s empty state text change — "Đang chờ Cross-sell
Agent phân tích — chưa có khuyến nghị để hiển thị" — belongs to
`shared/CrossSellOpportunities.tsx`; add it there in this same task since
it's a one-line copy change: find its current empty-state string and
replace it.)

- [ ] **Step 2: Verify**

Run: `cd web && npx tsc --noEmit -p .`
Expected: errors referencing `StressTestDrawer` (not yet created — Task 21
creates it; if executing tasks in order, temporarily stub
`web/components/eb/StressTestDrawer.tsx` with a minimal typed component
exporting `StressTestDrawer({open, onClose, result}: {...})` returning
`null` so this task's `tsc` check passes standalone, then Task 21 replaces
the stub body).

Run: `npm run build`
Expected: succeeds once the stub (or real Task 21 component) is in place.

- [ ] **Step 3: Commit**

```bash
git add web/components/EbResultPanel.tsx web/components/shared/CrossSellOpportunities.tsx
git commit -m "feat(eb): rebuild EbResultPanel as a 3-column layout"
```

---

### Task 21: `StressTestDrawer.tsx`

**Files:**
- Create: `web/components/eb/StressTestDrawer.tsx`
- Modify: `web/components/EbResultPanel.tsx` (remove the Task 20 stub import if one was added)

**Interfaces:**
- Consumes: `runStressTestV2`, `saveStressScenario`, `fetchStressScenarios` (Task 16)
- Produces: `<StressTestDrawer open={boolean} onClose={() => void} result={AssessmentResult} />`

- [ ] **Step 1: Write the component**

```tsx
// web/components/eb/StressTestDrawer.tsx
"use client";

import { useState } from "react";
import { X } from "lucide-react";
import { AssessmentResult, MetricValue as _MV, StressTestV2Result, fetchStressScenarios, runStressTestV2, saveStressScenario, StressScenario } from "@/lib/api";

type Preset = "co_so" | "than_trong" | "bat_loi" | "tuy_chinh";

const PRESETS: Record<Exclude<Preset, "tuy_chinh">, { revenue_pct: number; ebit_pct: number; interest_pct: number; receivable_days_add: number; inventory_pct: number }> = {
  co_so: { revenue_pct: 0, ebit_pct: 0, interest_pct: 0, receivable_days_add: 0, inventory_pct: 0 },
  than_trong: { revenue_pct: -10, ebit_pct: -15, interest_pct: 15, receivable_days_add: 15, inventory_pct: 10 },
  bat_loi: { revenue_pct: -20, ebit_pct: -30, interest_pct: 30, receivable_days_add: 30, inventory_pct: 20 },
};

function fmt(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return `${(v / 1_000_000_000).toFixed(2)} tỷ`;
}

function dscrColor(v: number | null): string {
  if (v === null) return "text-gray-400";
  if (v < 1.0) return "text-red-600";
  if (v < 1.2) return "text-amber-600";
  return "text-green-600";
}

function icrColor(v: number | null): string {
  if (v === null) return "text-gray-400";
  return v < 1.5 ? "text-red-600" : "text-green-600";
}

export function StressTestDrawer({ open, onClose, result }: { open: boolean; onClose: () => void; result: AssessmentResult }) {
  const [preset, setPreset] = useState<Preset>("co_so");
  const [deltas, setDeltas] = useState(PRESETS.co_so);
  const [comprehensive, setComprehensive] = useState(false);
  const [stressResult, setStressResult] = useState<StressTestV2Result | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [scenarioName, setScenarioName] = useState("");
  const [createdBy, setCreatedBy] = useState("RM");
  const [scenarios, setScenarios] = useState<StressScenario[]>([]);

  if (!open) return null;

  function applyPreset(p: Preset) {
    setPreset(p);
    if (p !== "tuy_chinh") setDeltas(PRESETS[p]);
  }

  async function run() {
    setError(null);
    try {
      const inputs: Record<string, number | null> = {};
      for (const metric of Object.values((result.credit_engine ?? {}) as Record<string, _MV>)) {
        if (metric.input_values) {
          for (const [k, v] of Object.entries(metric.input_values)) {
            if (typeof v === "number") inputs[k] = v;
          }
        }
      }
      const r = await runStressTestV2(inputs, deltas, comprehensive);
      setStressResult(r);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Stress test thất bại");
    }
  }

  async function loadScenarios() {
    if (!result.case_id) return;
    try {
      setScenarios(await fetchStressScenarios(result.case_id));
    } catch {
      // best-effort — scenario history is a convenience, not required for the run itself
    }
  }

  async function save() {
    if (!result.case_id || !stressResult || !scenarioName.trim()) return;
    await saveStressScenario(result.case_id, scenarioName.trim(), createdBy, result.ho_so_period?.selected ?? null, { preset, deltas, comprehensive_mode: comprehensive }, stressResult);
    setScenarioName("");
    loadScenarios();
  }

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/30" onClick={onClose}>
      <div className="w-full sm:w-[560px] max-w-full h-full bg-white overflow-y-auto p-6 space-y-5" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-bold text-msb-navy">Stress Test Dòng tiền</h2>
            <p className="text-xs text-gray-400">
              {(result.customer_profile?.customer_name as string) ?? "—"} · MST {(result.customer_profile?.tax_id as string) ?? "—"} · Kỳ {result.ho_so_period?.selected ?? "—"}
            </p>
          </div>
          <button onClick={onClose}><X className="h-5 w-5 text-gray-400" /></button>
        </div>
        <span className="inline-block text-xs font-semibold px-2.5 py-1 rounded-full bg-amber-100 text-amber-800">Mô phỏng sơ bộ</span>

        <div className="space-y-2">
          <p className="text-sm font-semibold text-msb-navy">Kịch bản giả định</p>
          <div className="flex flex-wrap gap-2">
            {(["co_so", "than_trong", "bat_loi", "tuy_chinh"] as Preset[]).map((p) => (
              <button
                key={p}
                onClick={() => applyPreset(p)}
                className={`text-xs font-semibold px-3 py-1.5 rounded-full ${preset === p ? "bg-msb-orange text-white" : "bg-gray-100 text-gray-600"}`}
              >
                {p === "co_so" ? "Cơ sở" : p === "than_trong" ? "Thận trọng" : p === "bat_loi" ? "Bất lợi" : "Tùy chỉnh"}
              </button>
            ))}
          </div>
          {preset === "tuy_chinh" && (
            <div className="grid grid-cols-2 gap-2 pt-1">
              {(Object.keys(deltas) as Array<keyof typeof deltas>).map((k) => (
                <div key={k}>
                  <label className="block text-[11px] text-gray-500 mb-0.5">{k}</label>
                  <input
                    type="number"
                    className="w-full border border-gray-200 rounded-lg px-2 py-1 text-sm"
                    value={deltas[k]}
                    onChange={(e) => setDeltas((prev) => ({ ...prev, [k]: Number(e.target.value) }))}
                  />
                </div>
              ))}
            </div>
          )}
          <label className="flex items-center gap-2 text-xs text-gray-500 pt-1">
            <input type="checkbox" checked={comprehensive} onChange={(e) => setComprehensive(e.target.checked)} />
            Bao quát toàn bộ nghĩa vụ nợ
          </label>
          <div className="bg-gray-50 rounded-lg px-3 py-2 text-xs text-gray-600">
            Doanh thu thay đổi {deltas.revenue_pct}%, EBIT thay đổi {deltas.ebit_pct}%, chi phí lãi vay thay đổi {deltas.interest_pct}%.
          </div>
          <button onClick={run} className="bg-msb-orange text-white text-sm font-semibold px-4 py-2 rounded-lg">Chạy mô phỏng</button>
          {error && <p className="text-sm text-red-600">{error}</p>}
        </div>

        {stressResult && (
          <>
            <div className="space-y-2">
              <p className="text-sm font-semibold text-msb-navy">Tác động lên dòng tiền và nghĩa vụ nợ</p>
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div><p className="text-xs text-gray-400">Doanh thu</p><p>{fmt(stressResult.before.revenue as number)} → {fmt(stressResult.after.revenue as number)}</p></div>
                <div><p className="text-xs text-gray-400">EBIT</p><p>{fmt(stressResult.before.ebit as number)} → {fmt(stressResult.after.ebit as number)}</p></div>
                <div><p className="text-xs text-gray-400">Chi phí lãi vay</p><p>{fmt(stressResult.before.interest_expense as number)} → {fmt(stressResult.after.interest_expense as number)}</p></div>
                <div>
                  <p className="text-xs text-gray-400">Vốn lưu động ròng</p>
                  <p>{stressResult.nwc_impact_quantifiable ? "Xem chỉ tiêu B.1" : "Chưa đủ dữ liệu để định lượng tác động vốn lưu động"}</p>
                </div>
              </div>
              <div className="bg-gray-50 rounded-lg px-3 py-2 text-xs text-gray-600">
                {stressResult.before.debt_service_label}: {fmt(stressResult.before.debt_service_total as number)} → {fmt(stressResult.after.debt_service_total as number)}
              </div>
            </div>

            <div className="space-y-2">
              <p className="text-sm font-semibold text-msb-navy">Khả năng trả nợ sau stress</p>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <p className="text-xs text-gray-400">DSCR sau stress</p>
                  <p className={`text-2xl font-bold ${dscrColor(stressResult.after.dscr.value as number | null)}`}>
                    {stressResult.after.dscr.value !== null ? `${(stressResult.after.dscr.value as number).toFixed(2)}x` : "Chưa xác định từ hồ sơ tải lên"}
                  </p>
                  {stressResult.buffers.dscr_buffer !== undefined && (
                    <p className="text-xs text-gray-500">Đệm: {stressResult.buffers.dscr_buffer.toFixed(2)}x</p>
                  )}
                </div>
                <div>
                  <p className="text-xs text-gray-400">ICR sau stress</p>
                  <p className={`text-2xl font-bold ${icrColor(stressResult.after.icr.value as number | null)}`}>
                    {stressResult.after.icr.value !== null ? `${(stressResult.after.icr.value as number).toFixed(2)}x` : "Chưa xác định từ hồ sơ tải lên"}
                  </p>
                  {stressResult.buffers.icr_buffer !== undefined && (
                    <p className="text-xs text-gray-500">Đệm: {stressResult.buffers.icr_buffer.toFixed(2)}x</p>
                  )}
                </div>
              </div>
            </div>

            {stressResult.conclusions.length > 0 && (
              <div className="space-y-1">
                <p className="text-sm font-semibold text-msb-navy">Kết luận AI</p>
                <ul className="text-xs text-gray-600 list-disc list-inside space-y-1">
                  {stressResult.conclusions.map((c, i) => <li key={i}>{c}</li>)}
                </ul>
              </div>
            )}
            {stressResult.recommended_actions.length > 0 && (
              <div className="space-y-1">
                <p className="text-sm font-semibold text-msb-navy">Hành động RM đề xuất</p>
                <ol className="text-xs text-gray-600 list-decimal list-inside space-y-1">
                  {stressResult.recommended_actions.map((a, i) => <li key={i}>{a}</li>)}
                </ol>
              </div>
            )}

            <p className="text-[11px] text-gray-400 border-t pt-2">{stressResult.disclaimer}</p>

            <div className="space-y-2 border-t pt-3">
              <div className="flex gap-2">
                <input
                  className="flex-1 border border-gray-200 rounded-lg px-2 py-1.5 text-sm"
                  placeholder="Tên kịch bản"
                  value={scenarioName}
                  onChange={(e) => setScenarioName(e.target.value)}
                />
                <input
                  className="w-24 border border-gray-200 rounded-lg px-2 py-1.5 text-sm"
                  placeholder="Người tạo"
                  value={createdBy}
                  onChange={(e) => setCreatedBy(e.target.value)}
                />
                <button onClick={save} className="text-xs font-semibold px-3 py-1.5 rounded-lg bg-msb-navy text-white shrink-0">Lưu kịch bản</button>
              </div>
              <button onClick={() => applyPreset("co_so")} className="text-xs text-gray-500 underline">Khôi phục kịch bản cơ sở</button>
              <button onClick={loadScenarios} className="text-xs text-msb-navy underline ml-3">Xem kịch bản đã lưu</button>
              {scenarios.length > 0 && (
                <ul className="text-xs text-gray-500 space-y-1 pt-1">
                  {scenarios.map((s) => (
                    <li key={s.id}>{s.name} · {s.created_by} · {new Date(s.created_at).toLocaleString("vi-VN")}</li>
                  ))}
                </ul>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify**

Run: `cd web && npx tsc --noEmit -p .`
Expected: no errors

Run: `cd web && npm run build`
Expected: succeeds

- [ ] **Step 3: Commit**

```bash
git add web/components/eb/StressTestDrawer.tsx web/components/EbResultPanel.tsx
git commit -m "feat(eb): add Stress Test drawer with presets, DSCR/ICR gauges, scenario save/list"
```

---

### Task 22: Wire `report_period` re-run in `page.tsx`

**Files:**
- Modify: `web/app/page.tsx`

**Interfaces:**
- Consumes: `EbResultPanel`'s `onRerunWithPeriod` prop (Task 20)

- [ ] **Step 1: Add period re-run wiring**

`page.tsx` currently calls `AssessmentForm` once per submission and stores
the result in `result` state; it doesn't retain the uploaded `File[]`
needed to re-POST with a different `report_period`. Add a small piece of
state in `page.tsx` to retain the last-used files/customer/tax id for EB
specifically, and pass a callback down:

```tsx
const [lastEbFiles, setLastEbFiles] = useState<{ files: File[]; customerName: string; taxId: string } | null>(null);

// in AssessmentForm's onResult handler, when tab === "eb", also capture the
// submitted files/customerName/taxId (requires AssessmentForm to surface
// them in its onResult callback or a parallel onSubmit callback — add an
// onSubmitted?: (files: File[], customerName: string, taxId: string) => void
// prop to AssessmentForm.tsx and call it right before runAssessment(), a
// one-line addition to that file's existing handleSubmit).

async function handleRerunWithPeriod(period: string) {
  if (!lastEbFiles) return;
  const r = await runAssessment("eb", lastEbFiles.customerName, lastEbFiles.taxId, lastEbFiles.files, { report_period: period });
  setResult(r);
}

// ...
{result && tab === "eb" && <EbResultPanel result={result} onRerunWithPeriod={handleRerunWithPeriod} />}
```

Add the corresponding one-line `onSubmitted` prop + call in
`AssessmentForm.tsx`'s existing `handleSubmit`, right before
`await runAssessment(...)`.

- [ ] **Step 2: Verify**

Run: `cd web && npx tsc --noEmit -p .`
Expected: no errors

Run: `cd web && npm run build`
Expected: succeeds

- [ ] **Step 3: Commit**

```bash
git add web/app/page.tsx web/components/AssessmentForm.tsx
git commit -m "feat(eb): wire kỳ báo cáo dropdown to re-run assessment with selected period"
```

---

## Part E — Verification and deploy

### Task 23: Full verification, deploy, live check

**Files:** none (verification only)

- [ ] **Step 1: Full backend test suite**

Run: `/usr/local/bin/python -m pytest -q`
Expected: all tests pass, 0 failures

- [ ] **Step 2: Frontend typecheck and build**

Run: `cd web && npx tsc --noEmit -p . && npm run build`
Expected: both succeed with no errors

- [ ] **Step 3: Local smoke test via Playwright**

Start the app locally (`uvicorn app.main:app` after `npm run build` has
regenerated `web/out`), upload a synthetic 2-column BCTC (xlsx with header
`["Chi tieu", "31/12/2025", "31/12/2024"]` and rows for each field this plan
added), and screenshot: (a) the 3-column EB panel, (b) an expanded
`FinancialDataTable` row, (c) the QĐ 039 card at both LTV toggles, (d) the
Stress Test drawer after running the "Thận trọng" preset. Visually confirm
against the spec's layout order (Kết luận → KPI trả nợ → Cảnh báo → Dữ liệu
nguồn → Bán chéo) and that no fabricated numbers appear where data is
missing.

- [ ] **Step 4: Commit, push, wait for CI, verify live**

```bash
git push -u origin claude/pensive-hamilton-tu2cdx
```

Poll the GitHub Actions "Deploy to GreenNode AgentBase" run for this push
via the GitHub MCP tools until it completes. On success, repeat the curl +
Playwright checks from Step 3 against the production endpoint
(`https://endpoint-21af0bfd-8ddd-44c6-a5dc-60a08bf4770c.agentbase-runtime.aiplatform.vngcloud.vn`,
via the proxy/CA-bundle pattern already established in this repo's sessions).

- [ ] **Step 5: Report to user**

Summarize in Vietnamese: what shipped, what was explicitly scoped out (per
the spec's own out-of-scope section), and confirm the live verification
result.
