# EB Screen Redesign + Stress Test Module — Design Spec

## Context and goal

Redesign the EB (KHDN) assessment result screen so it shows the customer's
real financial substance ("nội lực thật bên trong doanh nghiệp") to help
RM/CVKH and approvers decide faster, and build a proper Stress Test module.
The navigation bar, header, upload area, and the "Chạy thẩm định AI 360°"
CTA (`AssessmentForm.tsx`) stay untouched — this spec only changes the
**result panel** (`EbResultPanel.tsx`) and adds new backend fields/endpoints
behind it.

Delivered as a single combined change (per explicit instruction), covering
both the screen redesign and the Stress Test module in one pass.

## Global constraints

- AI extracts figures **only** from uploaded BCTC files (docx/pdf/xlsx/csv).
  Never fabricate a number; a missing field renders
  `"Chưa xác định từ hồ sơ tải lên"` and names the missing field.
- Every figure group shows its source: filename, kỳ dữ liệu (period), and an
  "AI đã trích xuất" / "Người dùng điều chỉnh" provenance badge.
- Selecting kỳ báo cáo (2024/2025) switches **all** figures, metrics,
  comments, and warnings to that year's data — no year-over-year comparison
  numbers shown next to it.
- "Nợ thuế", "Mua sắm công", "Trinh sát dữ liệu công khai" stay out of scope
  entirely — confirmed via codebase exploration that none of the three exist
  today, so this constraint requires no code, just a note not to build them
  yet (until Tổng cục Thuế / Cổng đấu thầu quốc gia integrations exist).
- "Cơ hội bán chéo" keeps using EB's existing lightweight adapter
  (`crosssell_adapter.py`, 4 rules, no deal size) per explicit decision —
  only its labeling/empty-state changes ("chờ Cross-sell Agent", never a
  fabricated opportunity).
- Every AI-derived result carries the label **"Khuyến nghị sơ bộ từ dữ liệu
  BCTC — cần phê duyệt theo quy trình tín dụng MSB"** and is never presented
  as a final credit decision.
- MSB visual language preserved: light background, MSB orange for
  CTAs/actions, green/amber/red for good/watch/risk signals. Demo/sample
  data, if ever shown, is labeled "Demo".
- Formulas and thresholds not yet confirmed as official MSB policy keep the
  existing `*_POLICY_VERSION = "DEMO_UAT..."` labeling convention already
  used throughout `app/agents/eb/`.

## Architecture overview

Two new layers, everything else additive:

1. **Period-aware extraction** (`app/extraction/period_columns.py`,
   `app/agents/eb/financial_inputs.py` rewritten) — detects which table
   column holds which fiscal year and returns one `EbFinancialInputs` per
   detected year. Every existing metric/rule module
   (`liquidity.py`, `repayment_capacity.py`, `leverage.py`,
   `contract_financing.py`, `cashflow_flags.py`, `dsp_reconciliation.py`)
   keeps consuming a flat `EbFinancialInputs` **unchanged** — the router
   just picks which year's dataclass to feed them, so 20+ existing
   rule/formula files and their tests are not touched by the period
   feature itself.
2. **Stress Test v2** (`app/agents/eb/stress_test.py` rewritten +
   new `app/agents/eb/stress_scenarios.py` + new DB table) — richer
   request/response contract, deterministic template-based conclusions
   (no LLM call, consistent with the Cross-sell agent's approach), and
   named scenario persistence.

## 1. Period-aware extraction

### 1.1 Year-column detection (`app/extraction/period_columns.py`, new)

```python
def detect_document_primary_year(doc: ExtractedDocument) -> int | None:
    """Scans doc text/tables for the newest 4-digit year in a reporting-date
    context ("tai ngay 31/12/2025", "nam tai chinh ket thuc ... 2025",
    "BAO CAO TAI CHINH NAM 2025"). Returns the max year found, or None."""

def detect_year_columns(header_row: list[str], primary_year: int | None) -> dict[int, str]:
    """Maps column index -> year string ("2025"/"2024") from a table's
    header row. Two signal types:
    - Explicit 4-digit year in the cell -> that year.
    - Relative labels: "so cuoi nam"/"cuoi ky"/"nam nay" -> primary_year;
      "so dau nam"/"dau ky"/"nam truoc" -> primary_year - 1.
    A column with no usable signal is left out of the returned dict."""
```

Applied only to **table-sourced** matches (xlsx/csv rows, docx tables, and
PDF tables where the pipeline already yields `ExtractedTable`) — real BCTC
statements are virtually always tabular, so multi-column fidelity work
concentrates where it pays off. Plain paragraph text (docx prose, a PDF
page with no detected table) keeps today's single-value behavior, tagged
`period_confidence: "suy_doan"` and assigned to the document's detected
primary year (or `"khong_xac_dinh"` if that can't be found either) — never
silently dropped, never silently mixed into the wrong year.

### 1.2 Multi-value row extraction (`app/extraction/evidence_search.py`, extended)

New `find_all_matches_by_period(documents, pattern, year_columns_by_table)`
— same row-matching as today's `find_all_matches`, but once a row matches,
extracts **every** VN-numeric cell in that row (not just the first capture
group) and zips each cell's column index against the table's detected year
map. Returns `list[tuple[EvidenceRef, str, str]]` (ref, raw value, year).
Existing `find_all_matches` is untouched (still used by RB/Cross-sell/EB
non-financial fields), so no regression risk there.

### 1.3 `EbFinancialInputs` — new fields

Extends the existing 13-field dataclass (unchanged fields keep their exact
current meaning/formula usage) with:

| New field | Spec code | Note |
|---|---|---|
| `net_revenue_vnd` | `IS_REVENUE` | Distinct from `revenue_bctc_vnd` (kept as-is, feeds RF04 DSP reconciliation only) |
| `pbt_vnd` | `IS_PBT` | |
| `pat_vnd` | `IS_PAT` | |
| `depreciation_vnd` | `IS_DEPRECIATION` | |
| `non_current_assets_vnd` | `BS_NON_CURRENT_ASSETS` | |
| `long_term_debt_vnd` | (supports `BS_LONG_TERM_CAPITAL`, `BS_TOTAL_BORROWINGS`) | "Nợ dài hạn" |
| `finance_lease_debt_vnd` | (supports `BS_TOTAL_BORROWINGS`) | Optional, often absent |
| `receivables_vnd` | `BS003` | Phải thu khách hàng |
| `inventory_vnd` | `BS004` | Hàng tồn kho |
| `payables_vnd` | `BS005` | Phải trả người bán |
| `cash_vnd` | `BS_CASH` | |
| `total_principal_due_vnd` | supports comprehensive DSCR | "Tổng nợ gốc đến hạn" (vs. existing `principal_due_vnd` treated as dài hạn only) |

`ebit_vnd` stays in the dataclass but its resolution order changes: prefer
a directly extracted "EBIT" line if present (rare in VN BCTC), else compute
`pbt_vnd + interest_expense_vnd` when both are available — this is exactly
the spec's own formula (`CALC_EBIT`), not a suy diễn, since it only runs on
already-extracted real figures.

Each new field gets its own `_FIELD_PATTERNS` regex, same style as today's.

### 1.4 Router wiring

`extract_period_aware_financial_inputs(documents) -> dict[str, PeriodExtraction]`
(new function in `financial_inputs.py`) replaces the direct
`extract_financial_inputs` call in `router.py`. New optional form field
`report_period: str | None` on `POST /api/eb/assess`; if given and present
among detected years, that year's `EbFinancialInputs` feeds the entire
existing downstream pipeline unchanged; otherwise the most recent detected
year is used, and `computed["ho_so_period"] = {"selected": ..., "available": [...]}`
is added to the response for the frontend dropdown. `EvidenceRef.period`
(already declared, always `None` today) gets populated with the resolved
year string throughout this path.

## 2. New/changed computed metrics

All computed metric functions keep the existing `Metric` dataclass shape
(`value`, `formula`, `input_values`, `input_sources`, `status`,
`policy_version`) — only new functions are added, none of the 6 existing
ones change signature.

- **EBITDA** (`liquidity.py` or new `profitability.py`) —
  `ebit_vnd + depreciation_vnd`; `NEED_MORE_DATA` if either missing.
- **Cân đối thanh khoản (Liquidity Balance)** — `(current_assets_vnd -
  current_liabilities_vnd) / net_revenue_vnd`. No hard threshold (spec:
  "không gán ngưỡng chuẩn cứng nếu chưa có chính sách MSB") — comment only,
  `> 0` vs `≤ 0` wording exactly as specified.
- **Nguồn vốn dài hạn** — `equity_vnd + long_term_debt_vnd`.
- **Tổng nợ vay** — `short_term_debt_vnd + long_term_debt_vnd +
  (finance_lease_debt_vnd or 0)`.
- **Cân đối tài chính (balance check)** — compares
  `nwc.value` against `nguon_von_dai_han - non_current_assets_vnd`; status
  `"Can bang"` if they match within a rounding tolerance, else
  `"Can ra soat phan loai nguon von"`. Rendered as a two-sided diagram per
  spec, not a single formula line.
- **DSCR — comprehensive mode** (`repayment_capacity.py`, new
  `compute_dscr(..., comprehensive: bool = False)` parameter, default
  `False` preserves today's exact behavior/tests) — when `True`, numerator
  uses `interest_expense_vnd` (already used by ICR) instead of
  `interest_due_vnd`, denominator uses `total_principal_due_vnd +
  interest_expense_vnd` instead of `principal_due_vnd + interest_due_vnd`.
  `NEED_MORE_DATA` if the comprehensive-mode fields are absent — never
  silently falls back to the non-comprehensive numbers.
- **QĐ 039 card** (`contract_financing.py` extended) — new
  `compute_receivables_financing_limit(receivables_vnd, ltv)` with
  `ltv ∈ {0.80, 0.85}`; `0.85` always carries the fixed note "Điều kiện ưu
  tiên — cần xác minh bên mua thuộc VNR500/FDI và phê duyệt theo quy định".
  Uses `receivables_vnd` (`BS003`) directly per the new requirement (the
  existing `proposed_limit_vnd`/`eligible_contract_value_vnd` manual-RM
  fields stay as they are, for the case where the RM already has a specific
  contract value — the two cards are complementary, not a replacement).

## 3. Red flags — additions and display changes

Two new rules, same `RuleResult`/3-way-status pattern as existing RF01–RF05,
`DEMO_UAT`-labeled thresholds:

- **RF06** — Phải thu + tồn kho chiếm tỷ trọng lớn trong tài sản ngắn hạn:
  fires (`MEDIUM`) if `(receivables_vnd + inventory_vnd) / current_assets_vnd
  > 0.70`.
- **RF07** — Chi phí lãi vay lớn bất thường so với EBIT: fires (`MEDIUM`) if
  `interest_expense_vnd > 0.30 * ebit_vnd` (an earlier warning than ICR's
  1.5x failure threshold).

No new rule needed for "thiếu dữ liệu để tính DSCR/ICR" — RF05 already
returns `CHƯA ĐÁNH GIÁ` for that case; the **display** changes so the new
"Cảnh báo rủi ro" priority list always shows `CHƯA ĐÁNH GIÁ` entries
(currently collapsed into a separate "not determined" bucket in
`RiskFlagsSection`) as first-class priority-list rows, each with mức độ /
chỉ tiêu ảnh hưởng / lý do / hành động RM, replacing the old "an toàn tín
dụng MSB" phrasing (not used anywhere in code today, confirmed) with **"Tín
hiệu cần thẩm định thêm từ dữ liệu BCTC"** as the section's framing copy.

## 4. Stress Test v2

### 4.1 Backend contract

`POST /api/eb/stress-test` — backward-incompatible rewrite (only caller is
this app's own frontend, not an external contract):

```jsonc
// Request
{
  "case_id": "EB-...",
  "inputs": { /* EbFinancialInputs subset, as today */ },
  "preset": "co_so" | "than_trong" | "bat_loi" | "tuy_chinh",
  "deltas": {
    "revenue_pct": 0, "ebit_pct": 0, "interest_pct": 0,
    "receivable_days_add": 0, "inventory_pct": 0,
    "principal_due_pct": null   // only usable when total_principal_due_vnd present
  },
  "comprehensive_mode": false
}
```

```jsonc
// Response
{
  "assumptions": { "human_readable": "...", "deltas": {...}, "comprehensive_mode": false },
  "before": { "revenue": ..., "ebit": ..., "interest_expense": ..., "nwc": {...Metric},
              "dscr": {...Metric}, "icr": {...Metric}, "debt_service_total": ... },
  "after":  { /* same shape, stressed */ },
  "nwc_impact_quantifiable": true,
  "buffers": { "dscr_buffer": 0.34, "icr_buffer": 0.12 },
  "conclusions": ["..."],          // up to 3, template-generated, cites real numbers
  "recommended_actions": ["..."],  // deterministic, ordered per the spec's fixed action set
  "disclaimer": "Mô phỏng theo giả định — không thay thế thẩm định tín dụng và phê duyệt MSB."
}
```

`revenue_pct`/`ebit_pct` apply independently (previously `revenue_pct` and
`margin_pct` were compounded into one `ebit_vnd` multiplier — now revenue
and EBIT are separate lines so the UI can show both "before/after" rows per
spec). NWC-after-stress is only computed (`nwc_impact_quantifiable: true`)
when `inventory_vnd`, `receivables_vnd`, and `net_revenue_vnd` are all
present (needed for the day-based/inventory-pct math); otherwise the field
is `false` and the frontend renders "Chưa đủ dữ liệu để định lượng tác
động vốn lưu động" verbatim, never a guessed number.

Conclusions/recommended actions are generated by a new
`app/agents/eb/stress_conclusions.py` — deterministic templates filled
from computed before/after deltas (same reasoning as the Cross-sell agent's
`scenario_templates.py`: literal fill-in-the-blank beats a free LLM call
for both anti-hallucination and latency). No LLM call added to this
endpoint.

### 4.2 Scenario persistence (new)

New table in `app/storage/db.py`:

```sql
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

New `app/agents/eb/stress_scenarios.py` (`save_scenario`,
`list_scenarios(case_id)`), new router endpoints
`POST /api/eb/stress-test/scenarios` (save; body includes `name`,
`created_by` — the demo app has no auth, so `created_by` is a free-text
field the RM types, defaulting to "RM"), `GET
/api/eb/stress-test/scenarios?case_id=...` (list, newest first).

### 4.3 "Đưa vào tờ trình"

`app/agents/eb/mb02_export.py` gets an optional `stress_scenario: dict |
None` parameter; when present, `build_mb02_docx` appends a new section with
the scenario name, assumptions, and before/after DSCR/ICR — appended, not
replacing any existing export content. `POST /api/eb/export` accepts an
optional `stress_scenario` key in its existing `computed` body.

## 5. Frontend layout

`EbResultPanel.tsx` gets a responsive 3-column CSS grid (`grid-cols-1
lg:grid-cols-[380px_1fr_340px]` or similar), collapsing to a single stacked
column on mobile in this fixed order: **Kết luận thẩm định → KPI trả nợ →
Cảnh báo → Dữ liệu nguồn → Bán chéo** (per explicit instruction).

**Cột trái — Hồ sơ & dữ liệu gốc**: new `CompanyInfoBlock` (tên, MST, kỳ
báo cáo dropdown wired to `report_period`, loại BCTC if extractable,
nguồn dữ liệu, "Xem dữ liệu đã trích xuất" trace button) + new
`FinancialDataTable` — a compact two-column (label | value) table, each row
showing a small technical field code, a tooltip (formula/definition), and
an "AI trích xuất"/"Người dùng điều chỉnh" provenance chip with an edit-pencil
icon. Values are read-only text by default; the pencil opens a small inline
editor that, on save, flips the provenance chip and keeps both the AI value
and the edited value in an audit trail (`edit_history` array on that field,
new backend support in `financial_inputs.py`'s evidence dict).

**Cột giữa — Sức khỏe tài chính & quyết định tín dụng**: banner (status +
one-line conclusion + processing time/period/completeness) at the top, then
the 4 KPI cards (NWC, Liquidity Balance, DSCR, ICR — colored by threshold,
formula on hover, short comment), then the "Cân đối tài chính" two-sided
diagram block, then the QĐ 039 opportunity card (LTV 80/85 toggle), then
the "Cảnh báo rủi ro" priority list (RF01–RF07 + CHƯA ĐÁNH GIÁ rows).

**Cột phải — M-Insight AI & bán chéo**: condensed `AiInsightSection`
(strengths/watch-items/one-line thesis, capped at 3 bullets each, no raw
data repeats) + action buttons (Giải thích chỉ số / Stress Test / Soạn tờ
trình / Phân tích sâu) + `CrossSellOpportunities` (unchanged data source,
new "Đang chờ Cross-sell Agent phân tích" empty state instead of the
current bare "no opportunities" case).

Every computed value carries `title="<formula>"` for hover-tooltip and a
"Xem dữ liệu nguồn" link jumping to that field's row in the left column's
evidence table (matching the Cross-sell UI's evidence-jump pattern already
established in this codebase). VND formatting: tỷ đồng in card/table view,
full VND on hover/expand (a small shared `formatVndSmart()` helper).

## 6. Stress Test UI

New `StressTestDrawer.tsx` (full-screen modal on mobile, wide drawer on
desktop), opened from the "Stress Test" button in the right column's AI
panel, page never navigates away.

1. **Header** — tên DN/MST/kỳ BCTC/tên file nguồn, badge "Mô phỏng sơ bộ",
   quick baseline status (DSCR/ICR/NWC/QĐ039 hạn mức tham chiếu).
2. **Kịch bản giả định** — 3 preset buttons (Cơ sở/Thận trọng/Bất lợi) with
   the spec's exact fixed values + a "Tùy chỉnh" panel (sliders + %
   inputs) for revenue/EBIT/interest/receivable-days/inventory, plus an
   optional nợ-gốc-đến-hạn % input gated on `total_principal_due_vnd`
   being present. A "Giả định đang áp dụng" box renders the human-readable
   assumption sentence from the response.
3. **Tác động lên dòng tiền và nghĩa vụ nợ** — 4 before/after KPI pairs
   (doanh thu, EBIT, chi phí lãi vay, NWC — NWC shows the "chưa đủ dữ liệu"
   fallback when `nwc_impact_quantifiable` is `false`) + a "Nghĩa vụ nợ đến
   hạn" card (nợ gốc, lãi vay, tổng — label switches to "Tổng nghĩa vụ nợ"
   under comprehensive mode).
4. **Khả năng trả nợ sau stress** — DSCR/ICR bar/gauge with the exact
   threshold colors and wording from the request, buffer numbers
   ("còn cách ngưỡng X"), AI conclusions list (≤3, from `conclusions[]`),
   "Hành động RM đề xuất" ordered list (from `recommended_actions[]`).

Actions: "Lưu kịch bản" (name + creator, posts to the new scenarios
endpoint, appears in a small history list within the drawer), "Đưa vào tờ
trình" (attaches the current scenario to the next MB02a export call),
"Khôi phục kịch bản cơ sở" (resets to preset `co_so`). All stressed values
render with a distinct background + "Sau stress" label/icon, never mixed
visually with the real BCTC figures. Mobile: conclusions + DSCR/ICR-after
move to the top; assumption sliders collapse into an accordion below.

## Review Focus

- **BCTC with only one column (no prior-year comparison printed)** — year
  detection must not crash or silently mislabel; falls back to
  `period_confidence: "suy_doan"` tagged to the document's detected primary
  year, covered by a dedicated test.
- **Uploaded file mixing 2024 and 2025 statements in one document** with
  conflicting values for the same field/year — must surface as
  `PENDING_REVIEW` for that (field, year) pair, not silently pick one.
- **RM selects a `report_period` no document actually contains** — must
  fall back to the most recent detected year with a visible note, not
  return an empty/broken panel.
- **Stress test preset pushes a field into a negative/nonsensical range**
  (e.g. EBIT after stress ≤ 0, ICR undefined) — ICR/DSCR must return
  `NEED_MORE_DATA`-equivalent rather than a division error or a misleading
  huge/negative ratio rendered as if valid.
- **DSCR comprehensive-mode toggle flipped without the comprehensive-mode
  fields present in this document** — must show "Chưa xác định từ hồ sơ
  tải lên" for that metric, not silently fall back to the non-comprehensive
  numbers under the comprehensive label (which would misrepresent the
  figure as more inclusive than it is).

---

**Explicitly out of scope for this pass**: full BCTC OCR for scanned-image
PDFs (existing OCR path is untouched), any real "loại BCTC" (kiểm
toán/nội bộ/thuế) classifier beyond best-effort text matching, auth/RBAC
for `created_by` on saved scenarios (free-text only, no login system exists
in this app), and the three explicitly-deferred modules (Nợ thuế, Mua sắm
công, Trinh sát dữ liệu công khai).
