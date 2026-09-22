# EB Evidence-Backed Condition Checklist — Design Spec

**Status:** approved by user for autonomous implementation ("tự chạy code và lựa chọn phương án tối ưu nhất cho đến khi kết thúc" — proceed and pick the best option myself through completion).

## 1. Goal

Rework Agent EB so every number and every conclusion it shows is traceable to a
specific source document (file, page/sheet/cell, verbatim text), and add a
condition-by-condition checklist (11 rows) mirroring the bank's real screening
process. No field may show a fabricated value, a silent zero, or a status the
underlying evidence doesn't support. This is a screening aid for a credit
officer, not an approval decision — the UI must never imply approval.

## 2. Non-goals for this round

- Real integration with MSB's CIF/CIC/DSP/AML systems. Every condition that
  needs one of these always resolves to `PENDING_INTERNAL_CHECK` — modeled
  behind an adapter interface so a real integration can be plugged in later
  without touching the condition-evaluation engine.
- Real policy documents. All thresholds live in one demo config, each entry
  tagged `is_demo=True` and rendered as "Ngưỡng demo – chờ nghiệp vụ xác
  nhận" until someone fills in a real `doc_code`/`version`/`effective_date`.
- An in-browser PDF/Excel viewer with pixel-level highlighting. Evidence
  links open the original file (new tab / download) with a text citation
  ("Trang 3", "Sheet 'BCĐKT', dòng 12") — good enough to verify by hand.
- True multi-stage async document processing UI (Đang đọc → Đã trích xuất as
  live-updating steps). The whole assessment is one synchronous request/
  response today; the document panel shows each file's *final* status after
  the request completes, not a live progress feed.
- Multi-period trend analysis beyond what the uploaded documents actually
  contain — "Phân tích sâu" only compares periods it can find evidence for.

## 3. Core data model (`app/engine/core/types.py`)

Two new status enums, kept as plain string literals (matching the existing
`RuleResult.status` convention — no runtime enum class, this codebase already
uses string literals for readable JSON):

```python
FieldStatus = Literal["VERIFIED", "COMPUTED", "PENDING_REVIEW", "MISSING_DATA", "NOT_APPLICABLE"]
ConditionResult = Literal["PASS", "FAIL", "INSUFFICIENT_DATA", "PENDING_INTERNAL_CHECK", "NOT_APPLICABLE"]
```

`FieldStatus` describes one extracted/computed *value*. `ConditionResult`
describes the pass/fail outcome of comparing a value against a policy rule —
these are never the same field. A condition can have `observed.status ==
"COMPUTED"` (we have a number) and still `result == "INSUFFICIENT_DATA"`
(we don't have a confirmed rule to compare it against — see §5.3).

```python
@dataclass
class EvidenceRef:
    file_id: str
    filename: str
    location: str          # "Trang 3" | "Sheet 'BCĐKT', dòng 12" | "Toàn văn bản"
    original_text: str
    period: str | None = None

@dataclass
class EvidencedField:
    field_id: str
    label: str
    value: float | str | None
    unit: str | None
    period: str | None
    status: FieldStatus
    evidence: list[EvidenceRef] = field(default_factory=list)
    formula: str | None = None
    input_fields: list[str] = field(default_factory=list)
    policy_version: str | None = None
    last_verified_at: str | None = None

    def __post_init__(self):
        if self.status == "MISSING_DATA" and self.value is not None:
            raise ValueError(f"{self.field_id}: MISSING_DATA field must not carry a value")

@dataclass
class ConditionRow:
    condition_id: str
    condition_name: str
    observed: EvidencedField
    compare_rule: str
    result: ConditionResult
    reason_if_incomplete: str | None = None

    def __post_init__(self):
        if self.result in ("PASS", "FAIL") and self.observed.value is None:
            raise ValueError(f"{self.condition_id}: {self.result} requires observed.value")
```

`Metric` and `RuleResult` (existing) are untouched for RB/Cross-sell and for
EB's five existing risk flags — only EB's financial-input plumbing and new
condition rows use the new types. `last_verified_at` is set to
`datetime.now(UTC).isoformat()` at the moment a field is extracted/computed,
not hardcoded.

## 4. File persistence + provenance-aware extraction

### 4.1 Persisting uploaded files

- `case_id` generation changes from `f"EB-{tax_id}"` (collides across repeat
  runs for the same customer) to `f"EB-{tax_id}-{uuid4().hex[:8]}"`.
- New `app/storage/files.py`: `save_case_file(case_id, file_id, filename,
  content: bytes) -> Path` writes to `data/eb_files/<case_id>/<file_id>__
  <filename>`; `get_case_file_path(case_id, file_id) -> Path | None` reads
  it back. Same `db_path`-relative `data/` directory the SQLite file already
  lives in.
- New SQLite table `case_files` (case_id, file_id, filename, content_type,
  size_bytes, uploaded_at, storage_path) in `app/storage/db.py`'s schema.
  Add nullable `case_id TEXT` column to `assessments` too (existing rows get
  `NULL`, fine — `ALTER TABLE ... ADD COLUMN` is idempotent-safe behind a
  "column already exists" catch, matching how `init_db` is already called
  defensively).
- New endpoint `GET /api/eb/files/{case_id}/{file_id}`: streams the file
  back with the right `Content-Type` and `Content-Disposition: inline` for
  PDFs (opens in a new tab) / `attachment` for xlsx/docx/csv. 404 if the
  case or file id doesn't match — never leaks arbitrary filesystem paths.

### 4.2 Provenance-preserving extraction

- `ExtractedDocument` (app/extraction/types.py) gains `file_id: str` and
  `pages: list[str] | None` (populated for PDFs only — `pipeline.py`
  already builds this per-page list internally before joining it into
  `text`; stop discarding it). `tables` (xlsx/csv) already carries
  sheet+row granularity — unchanged. DOCX has no natural page concept;
  evidence from a DOCX always cites `"Toàn văn bản"`.
- Router passes a freshly generated `file_id` into `extract_document(path,
  filename, file_id=...)` for every uploaded file, before persisting it via
  §4.1.
- New `app/extraction/evidence_search.py`:
  `find_all_matches(documents: list[ExtractedDocument], pattern: re.Pattern)
  -> list[tuple[EvidenceRef, str]]` (str = raw matched value text) — scans
  **every** page/row/document (not stopping at the first hit, unlike
  today's `financial_inputs.py`). Caller decides what "conflict" means for
  its field (see §4.3).

### 4.3 `financial_inputs.py` rework

Returns `dict[str, EvidencedField]` instead of the flat `EbFinancialInputs`
dataclass. For each of the 13 existing fields:

- No match anywhere → `EvidencedField(value=None, status="MISSING_DATA", evidence=[])`.
- Exactly one distinct numeric value across all matches → `status="COMPUTED"`,
  `evidence=[every EvidenceRef that produced that same value]` (multiple
  citations for the same number is a *good* signal — it shows the figure is
  corroborated, and the UI can say so).
- Two or more **different** numeric values → `status="PENDING_REVIEW"`,
  `value=None`, `evidence=` all conflicting refs — exactly the "OCR không
  chắc hoặc nhiều file cho số khác nhau, yêu cầu xác nhận" case from the
  spec. Never silently pick one.

Every downstream consumer (`leverage.py`, `liquidity.py`,
`repayment_capacity.py`, `cashflow_flags.py`, `dsp_reconciliation.py`) reads
`.value`/`.status` off the new dict instead of dataclass attributes, and
threads `.evidence` through into the `Metric`/`RuleResult` it produces
(`Metric` gains an `evidence: list[EvidenceRef] = field(default_factory=list)`
field alongside its existing `input_sources: dict[str,str]` — `input_sources`
stays as the short human label ("bctc"), `evidence` carries the clickable
citation).

## 5. Section A — 11-condition overview engine

(The source table has 11 rows, not 12 — "Đối tượng áp dụng" through "Lịch sử
quan hệ tín dụng". The header count is computed from `len(conditions)`, never
hardcoded.)

### 5.1 Module layout

New package `app/agents/eb/overview/`, one function group per data-source
cluster (matches the existing one-rule-per-file convention):

| Module | Conditions | Source posture |
|---|---|---|
| `customer_status.py` | Đối tượng áp dụng; Tình trạng hoạt động | Needs CIF / business registry → §5.2 |
| `revenue.py` | Doanh thu 12 tháng (B02); Doanh thu 6 tháng qua TKTT (sao kê, never derived from B02) | Computable from uploaded docs |
| `industry.py` | Ngành nghề + đối chiếu danh sách ngành cấm | Computable + policy list |
| `partners.py` | 03/05 đối tác đầu ra/đầu vào | Computable data, unresolved policy reading — §5.3 |
| `operating_history.py` | Số năm hoạt động | Computable from ĐKKD |
| `equity_profit.py` | Vốn chủ sở hữu; LNST theo PAKD; Lợi nhuận gộp trừ lãi vay | Computable from B01/B02/PAKD |
| `credit_history.py` | Lịch sử quan hệ tín dụng | Needs CIC → §5.2 |

`app/agents/eb/overview/__init__.py` exposes `evaluate_overview(fields:
dict[str, EvidencedField], documents, policy) -> list[ConditionRow]`,
called once from the router.

### 5.2 Internal-system-gated conditions

Per the earlier decision: any condition whose source is CIF/CIC/DSP/AML and
that this app has no live connection to **always** resolves
`result="PENDING_INTERNAL_CHECK"`, `reason_if_incomplete` naming which
system is needed. Implemented as one small adapter,
`app/agents/eb/internal_systems.py`:

```python
def check_internal_system(system: str) -> ConditionResult:
    """Always PENDING_INTERNAL_CHECK today — no real CIF/CIC/DSP/AML
    connection exists. Swap this function's body, not its callers, when a
    real integration lands."""
    return "PENDING_INTERNAL_CHECK"
```

Every condition module that needs CIF/CIC calls this instead of hardcoding
the status inline, so the whole engine has exactly one place to change later.

### 5.3 The "03/05 đối tác" open policy question

Not a missing-data case — the partner counts are computable from
hóa đơn/hợp đồng/sổ chi tiết. What's missing is confirmation of whether the
rule applies separately to đầu ra and đầu vào or combined. Resolution:
compute and display the real observed data (partner list + per-side counts)
in `observed`, but set `result="INSUFFICIENT_DATA"` with
`reason_if_incomplete="Cách áp dụng '03/05' (tính riêng đầu ra/đầu vào hay
gộp) chưa được chủ chính sách xác nhận."` — this is the literal "Chưa đủ
căn cứ xác định điều kiện áp dụng" case the spec names for the overall
conclusion, applied at the single-condition level. `policy_config.py`
(§5.4) carries this as an `open_question` string on the relevant threshold
entry so the UI can surface it without hardcoding policy prose in Python.

### 5.4 Policy config store

New `app/agents/eb/policy_config.py`:

```python
@dataclass
class PolicyThreshold:
    value: Any
    doc_code: str | None = None
    version: str | None = None
    effective_date: str | None = None
    open_question: str | None = None
    is_demo: bool = True

    @property
    def policy_version_label(self) -> str:
        if self.is_demo:
            return "Ngưỡng demo – chờ nghiệp vụ xác nhận"
        return f"{self.doc_code} v{self.version} (hiệu lực {self.effective_date})"

POLICY_CONFIG: dict[str, PolicyThreshold] = {
    "REVENUE_12M_MIN_VND": PolicyThreshold(20_000_000_000),
    "REVENUE_12M_MAX_VND": PolicyThreshold(1_000_000_000_000),
    "MIN_OPERATING_MONTHS": PolicyThreshold(24),
    "TOP_PARTNERS_COUNT": PolicyThreshold(
        5, open_question="Áp dụng riêng đầu ra/đầu vào hay gộp — chờ chủ chính sách xác nhận."
    ),
    "PROHIBITED_INDUSTRIES": PolicyThreshold([]),  # empty until a real list is loaded
}
```

Every condition/metric that compares against a threshold reads
`POLICY_CONFIG[key].policy_version_label` for its `policy_version` field —
one string, one place, changes the instant a real policy doc is entered.

### 5.5 Header summary + overall conclusion

`evaluate_overview` also returns (or the router computes from its output) a
summary: `checked = len([c for c in rows if c.result in ("PASS","FAIL")])`,
`total = len(rows)`, `passed`, `failed`, `pending =
len([c for c in rows if c.result in ("INSUFFICIENT_DATA",
"PENDING_INTERNAL_CHECK")])`. Rendered as "X/Y điều kiện đã kiểm tra đủ dữ
liệu; A đạt, B không đạt, C chờ xác minh".

All 11 conditions are treated as required for the overall conclusion (no
subset is silently classified as "not critical" — the spec gives no such
weighting, so none is invented). The overall conclusion string is
`"Chưa đủ căn cứ xác định điều kiện áp dụng"` whenever `pending > 0`;
otherwise it falls through to the existing `credit_readiness`/
`recommendation` logic already in `router.py`. Given today's reality (no
CIF/CIC), this conclusion will almost always be the "chưa đủ căn cứ" one —
that's the honest state, not a bug to work around.

## 6. Section B.1 — four metric cards

NWC, DSCR, ICR: unchanged formulas, rewired to carry `evidence` (§4.3) and a
`policy_version` from `POLICY_CONFIG` where a threshold is compared (DSCR/ICR
already reference `RF05_POLICY_VERSION`, kept as-is — those thresholds stay
demo-marked exactly as they are today).

**New 4th metric — Tỷ lệ tài trợ hợp đồng đầu ra:**
`proposed_limit_vnd / eligible_contract_value_vnd × 100%`. Neither input is
extractable by regex from free text reliably (they come from an ĐVKD
proposal, not a standard BCTC line) — both are added as **optional manual
form fields** on the EB assessment form, the same pattern already used for
Cross-sell's `opening_balance` etc.: `proposed_limit_vnd`,
`eligible_contract_value_vnd`. Missing either → `MISSING_DATA`, never a
guessed ratio. `QD_EB_039_RATES` (already defined in
`app/agents/crosssell/qd_eb_039.py`) is reused, not duplicated — the label
"QĐ.EB.039" is attached to the card only when the RM also picks a financing
method from `QD_EB_039_RATES` **and** the case has been confirmed in scope
(a new optional `qd_eb_039_method` form field; absent → card still computes
the raw ratio but without the QĐ.EB.039 label, captioned "tỷ lệ đề xuất,
chưa phải mức đã phê duyệt" per spec). Every card exposes formula, raw
inputs, and each input's `EvidenceRef`/manual-entry marker; clicking expands
the explanation panel client-side (data's already in the payload, no new
endpoint needed for this).

## 7. Section C — risk flags

RF01–RF05 already: Vietnamese-only comments, `"CHƯA ĐÁNH GIÁ"` status for
the missing-data case (never silently "no warning"), `policy_version`,
`verification_question`, `recommended_action`. No backend rule logic changes
needed beyond threading `evidence` through from the new `financial_inputs`
(§4.3) the same way metrics do. Frontend groups flags into three buckets by
`status`: `"KÍCH HOẠT"` (active warnings, counted in the header), `"CHƯA
ĐÁNH GIÁ"` (its own "Chưa thể đánh giá" section, not counted as "no
warnings"), `"KHÔNG KÍCH HOẠT"` (hidden by default, available on toggle).
RF05's existing comment already separates whether DSCR, ICR, or both
triggered — no English leaks through in the current code, confirmed by
reading it; just needs the richer evidence wiring.

## 8. Section D — document panel

Per §2 non-goals, this reports the **final** per-file status computed
synchronously within the same request, not a live multi-step feed:

- `"KHÔNG_ĐỌC_ĐƯỢC"` — `extract_document` raised (today's `except Exception`
  path in the router already catches this per-file).
- `"ĐÃ_TRÍCH_XUẤT"` — extraction succeeded and at least one
  `EvidencedField`/`ConditionRow` cites this `file_id`.
- `"CHỜ_XÁC_MINH"` — extraction succeeded but every value derived from it
  ended up `PENDING_REVIEW` (conflicted with another file) or the doc
  classifier's confidence was low.
- `"ĐÃ_TẢI_LÊN"` — extraction succeeded but nothing downstream cited this
  file (e.g. a document type the checklist doesn't use yet) — distinct from
  "đã trích xuất" exactly as the spec insists ("Đã tải lên" không được hiển
  thị thành "Đã bóc tách").

Router builds this list per file: filename, doc_type (from the classifier),
size, extraction timestamp, status above, count of fields citing it, and any
warnings. Clicking a file in the UI lists every `EvidencedField`/
`ConditionRow` whose evidence references its `file_id`, with each one's
`location`/`original_text` — a client-side filter over data already in the
response payload.

## 9. Section E — cross-sell opportunities inside EB

Per the earlier decision: EB reuses the Cross-sell engine, not a parallel
implementation. `app/agents/crosssell/statement_parser.py` already parses
bank-statement documents out of a mixed `ExtractedDocument` list; if the
EB upload bundle contains a document the statement parser recognizes, the
EB router runs `parse_statement_documents` + the existing rule1–rule6
evaluators (already imported nowhere near EB today) and adapts each
`RuleResult` into the EB opportunity-card shape via a new
`app/agents/eb/crosssell_adapter.py`:

```python
def adapt_to_opportunity_card(rule_result: RuleResult) -> dict:
    ...
```

mapping `rule_name`/`comment`/`evidence`/`recommended_action` onto the
card fields (sản phẩm gợi ý, chứng từ căn cứ, công thức ước tính, mức ưu
tiên, người cần rà soát). Because the Cross-sell rules are statement-derived
(transaction patterns), never contract/invoice-derived, every EB-adapted
card is **always** presented as a qualitative opportunity — no dollar
"deal size" is asserted from this path (satisfies "chưa có chứng từ thì chỉ
nêu cơ hội định tính, không hiện số tiền"). A future round can add EB-native
contract/invoice-grounded cards with real deal sizes; out of scope here. If
no statement document is present in the EB bundle, section E is simply
empty — never fabricated.

## 10. Section F — AI Insight + action buttons

- **AI Insight structure**: EB's `narrative.py` system prompt is rewritten
  to require the five-part structure (Phát hiện → Số liệu và nguồn → Ý
  nghĩa tín dụng → Điều chưa chắc chắn → Việc cán bộ cần làm) and to cite a
  `field_id`/`condition_id` for every claim — enforced by a new test that
  feeds a fixture payload and asserts the parsed JSON's `why` entries each
  reference a known id. Still degrades to `why: []` on any parse failure,
  same fallback pattern as today.
- **Giải thích**: no new endpoint — the formula/evidence is already in the
  payload (§6); this is a frontend expand/collapse on the existing data.
- **Stress Test**: new `POST /api/eb/stress-test` taking the already-computed
  `EvidencedField` inputs plus RM-chosen deltas (revenue %, margin %,
  interest rate %, collection-speed %), recomputing NWC/DSCR/ICR with the
  adjusted inputs via the same pure functions from §6 (they already take
  plain numbers in, so stress-test reuses them directly — no duplicate
  formulas). Response carries `assumptions`, `before`, `after`, and is
  always labeled a hypothetical scenario, never a forecast, in both the API
  response text and the UI copy.
- **Soạn tờ trình**: `mb02_export.py` updated to read the same
  `EvidencedField`/`ConditionRow` objects the web response carries (not a
  parallel recomputation) — the value the docx prints for e.g. NWC is
  read from the exact same JSON structure the web page rendered, so they
  cannot drift. New test asserts this equality directly (build the docx,
  reopen it via `python-docx`, assert every numeric line matches the source
  `computed` dict).
- **Phân tích sâu**: if 2+ periods of the same document type are detected
  (multiple BCTC files/pages with distinct `period` values), compute simple
  deterministic deltas (revenue growth %, NWC trend) and pass them to the
  narrative call for prose; if only one period exists, the section states
  "Chỉ có 1 kỳ dữ liệu — chưa đủ để phân tích xu hướng" instead of
  fabricating a trend.

## 11. API contract (Section G)

Every `EvidencedField` and `ConditionRow` serializes via `dataclasses.asdict`
(already the router's pattern for `Metric`/`RuleResult`) — this gives
exactly the field set the spec's table names: `field_id, label, value, unit,
period, status, formula, input_fields, policy_version, last_verified_at`
plus `evidence: [{file_id, filename, location, original_text, period}]`
(a list instead of single `source_file`/`page_or_sheet_or_cell`/
`original_text` columns, since a corroborated field can cite more than one
source — the frontend mapping table below documents both).

Frontend (`web/lib/api.ts`) types gain `EvidencedField`, `EvidenceRef`,
`ConditionRow` matching the above 1:1, plus `overview: ConditionRow[]`,
`overview_summary: {checked, total, passed, failed, pending}`,
`documents: DocumentStatus[]`, `opportunities: OpportunityCard[]` on
`AssessmentResult`. **No demo numbers or silent fallback in frontend code**:
every render path checks `status`/`result` first; `value === null` always
renders "Chưa có dữ liệu", never `0` or blank.

### Mapping table (UI region → API field → source → status-when-missing)

| UI region | API field | Source | Status when missing |
|---|---|---|---|
| A. mỗi dòng điều kiện | `overview[].observed`, `.result`, `.reason_if_incomplete` | `overview/*.py` | `INSUFFICIENT_DATA` / `PENDING_INTERNAL_CHECK` |
| B. mã hồ sơ/kỳ/thời điểm | `case_id`, `assessed_at` (new, `datetime.now(UTC)` at request start) | router | never missing — always generated |
| B.1 4 thẻ chỉ tiêu | `credit_engine.{nwc,dscr,icr,output_contract_financing_ratio}` | liquidity/repayment_capacity/new module | `MISSING_DATA` |
| C. cảnh báo rủi ro | `risk_flags[]` | RF01–05 modules | `"CHƯA ĐÁNH GIÁ"` |
| D. hồ sơ khách hàng | `documents[]` | router, built from `ExtractedDocument` + citation counts | `"KHÔNG_ĐỌC_ĐƯỢC"` |
| E. cơ hội bán chéo | `opportunities[]` | `crosssell_adapter.py` | empty list |
| F. AI Insight | `why[]`, `credit_memo` | `narrative.py` | `[]` / disclaimer text |
| F. Stress Test | new `/api/eb/stress-test` response | §10 | 400 if required inputs missing |
| F. Soạn tờ trình | `/api/eb/export` (existing, updated) | `mb02_export.py` | omits section, never fabricates |

### Test fixtures (new, under `tests/fixtures/`)

1. `eb_complete_evidence/` — BCTC + ĐKKD + PAKD + sao kê with every number a
   real, findable string (built with `reportlab`/`openpyxl` the same way
   existing fixtures are generated), expected: all computable conditions
   resolve PASS/FAIL (never INSUFFICIENT_DATA for a condition whose source
   document is present), all 4 metric cards have `status="COMPUTED"` with
   non-empty `evidence`.
2. `eb_missing_cic/` — same bundle minus anything CIC/AML-shaped, expected:
   "Lịch sử quan hệ tín dụng" condition is `PENDING_INTERNAL_CHECK`, overall
   conclusion is `"Chưa đủ căn cứ xác định điều kiện áp dụng"` — this is the
   test that would catch a regression where the system silently reports
   "Đạt" without real CIC data.

## 12. Acceptance

Every number/claim on the web response and in the exported MB02a docx must
trace to either an `EvidenceRef` (file_id + location + original_text) or a
`formula` + `input_fields` chain that bottoms out in `EvidenceRef`s. Verified
directly by the docx-vs-json equality test (§10) plus a new end-to-end test
per fixture (§11) asserting the full response shape and the two expected
overall conclusions.
