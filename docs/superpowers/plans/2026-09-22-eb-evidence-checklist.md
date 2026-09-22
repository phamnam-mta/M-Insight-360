# EB Evidence-Backed Condition Checklist Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every number/status Agent EB shows traceable to a source document (file/page/sheet/cell/original text), add the 11-condition checklist from spec §A, a 4th metric card, and sync the web response with the MB02a export — all evidence-first, never a silent guess.

**Architecture:** A new `EvidenceRef`/`EvidencedField`/`ConditionRow` data model (app/engine/core/types.py) threads through a provenance-preserving extraction rework, a new 11-condition overview engine, a demo-marked policy config store, and an EB-specific frontend panel. `EbFinancialInputs` (the existing plain-float dataclass every RF0x rule already consumes) is kept unchanged in shape — `extract_financial_inputs` now returns it alongside a parallel `dict[str, FieldEvidence]` so existing rule logic and its ~25 existing tests are untouched, while the router wires evidence into the response.

**Tech Stack:** Python/FastAPI backend (dataclasses, sqlite3, pytest), Next.js/React/TypeScript frontend, python-docx for MB02a export.

**Spec:** docs/superpowers/specs/2026-09-22-eb-evidence-checklist-design.md

## Global Constraints

- No field may show `0` or a fabricated value when data is missing — always `null`/`None` with the correct status.
- All new policy thresholds start `is_demo=True`, rendered "Ngưỡng demo – chờ nghiệp vụ xác nhận", never "Chuẩn MSB".
- Every condition needing CIF/CIC/DSP/AML resolves via `check_internal_system()` (one function, swappable later) — never a hardcoded per-condition guess.
- `EbFinancialInputs` keeps its existing plain-`float | None` field shape — do not change its constructor signature; evidence travels in a separate parallel structure.
- Run `/usr/local/bin/python -m pytest -q` (not bare `pytest`) after every task; full suite must stay green before each commit.
- Vietnamese-only user-facing text (labels, statuses, error messages) — no English leaking into API string fields the UI renders directly.
- Follow TDD: failing test → minimal implementation → passing test → commit, for every step below.

## Review Focus

- A field with conflicting values across two uploaded files must never silently pick one — `financial_inputs.py`'s multi-source scan is the one place this is enforced; task 5's tests must include a two-file-disagree case.
- A condition whose only source is CIF/CIC (e.g. "Đối tượng áp dụng", "Lịch sử quan hệ tín dụng") must never resolve PASS/FAIL from an uploaded document alone, however convincing the document text looks — tasks 8 and 14 must each test that a document claiming e.g. "khách hàng hiện hữu" still yields `PENDING_INTERNAL_CHECK`.
- The MB02a docx export must never show a number that differs from the web JSON for the same field — task 21's equality test is the one thing that catches drift here.
- A file that fails extraction (corrupt/unsupported) must still appear in the `documents[]` list with status `KHÔNG_ĐỌC_ĐƯỢC`, not silently vanish from the response — task 17's test must upload one bad + one good file and assert both appear.
- The overall conclusion must read "Chưa đủ căn cứ xác định điều kiện áp dụng" whenever any condition is still `INSUFFICIENT_DATA`/`PENDING_INTERNAL_CHECK` — never let a partially-complete checklist produce an upbeat-sounding conclusion; task 15's test asserts this on a bundle missing only one condition's data.

---

## Task 1: Core evidence data types

**Files:**
- Modify: `app/engine/core/types.py`
- Test: `tests/test_engine_core_types.py` (new)

**Interfaces:**
- Produces: `FieldStatus`, `ConditionResult` (type aliases), `EvidenceRef`, `EvidencedField`, `ConditionRow` dataclasses; `Metric.evidence: dict[str, list[EvidenceRef]]` (new field, default `{}`, keyed by the same names as `Metric.input_values`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_engine_core_types.py
import pytest

from app.engine.core.types import ConditionRow, EvidencedField, EvidenceRef, Metric


def _evidence():
    return EvidenceRef(
        file_id="f1", filename="bctc.pdf", location="Trang 3",
        original_text="Von chu so huu: 500.000.000",
    )


def test_evidenced_field_missing_data_cannot_carry_a_value():
    with pytest.raises(ValueError):
        EvidencedField(
            field_id="equity_vnd", label="Vốn chủ sở hữu", value=500_000_000,
            unit="VND", period=None, status="MISSING_DATA",
        )


def test_evidenced_field_ok_with_value_when_computed():
    f = EvidencedField(
        field_id="equity_vnd", label="Vốn chủ sở hữu", value=500_000_000,
        unit="VND", period="2025", status="COMPUTED", evidence=[_evidence()],
    )
    assert f.value == 500_000_000
    assert f.evidence[0].location == "Trang 3"


def test_condition_row_pass_requires_observed_value():
    observed = EvidencedField(
        field_id="revenue_12m_vnd", label="Doanh thu 12 tháng", value=None,
        unit="VND", period=None, status="MISSING_DATA",
    )
    with pytest.raises(ValueError):
        ConditionRow(
            condition_id="C02", condition_name="Doanh thu 12 tháng",
            observed=observed, compare_rule="≥20 tỷ và <1.000 tỷ", result="PASS",
        )


def test_condition_row_insufficient_data_does_not_require_value():
    observed = EvidencedField(
        field_id="revenue_12m_vnd", label="Doanh thu 12 tháng", value=None,
        unit="VND", period=None, status="MISSING_DATA",
    )
    row = ConditionRow(
        condition_id="C02", condition_name="Doanh thu 12 tháng",
        observed=observed, compare_rule="≥20 tỷ và <1.000 tỷ",
        result="INSUFFICIENT_DATA", reason_if_incomplete="Thiếu B02/BCTC.",
    )
    assert row.result == "INSUFFICIENT_DATA"


def test_metric_evidence_defaults_to_empty_dict():
    m = Metric(metric="nwc", value=None, formula="a - b", input_values={}, input_sources={})
    assert m.evidence == {}


def test_rule_result_evidence_refs_defaults_to_empty_dict_and_keeps_existing_evidence_list():
    from app.engine.core.types import RuleResult

    r = RuleResult(rule_id="RF01", rule_name="Mất cân đối vốn", status="KHÔNG KÍCH HOẠT")
    assert r.evidence_refs == {}
    assert r.evidence == []  # the existing human-readable string list is untouched
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/local/bin/python -m pytest tests/test_engine_core_types.py -v`
Expected: FAIL — `ImportError: cannot import name 'EvidencedField'` (and `ConditionRow`, `EvidenceRef`).

- [ ] **Step 3: Implement**

Add to `app/engine/core/types.py` (keep existing `Metric`/`RuleResult` as-is, just add the `evidence` field to `Metric` and append the new types):

```python
from typing import Literal

FieldStatus = Literal["VERIFIED", "COMPUTED", "PENDING_REVIEW", "MISSING_DATA", "NOT_APPLICABLE"]
ConditionResult = Literal["PASS", "FAIL", "INSUFFICIENT_DATA", "PENDING_INTERNAL_CHECK", "NOT_APPLICABLE"]


@dataclass
class EvidenceRef:
    file_id: str
    filename: str
    location: str
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
    evidence: list["EvidenceRef"] = field(default_factory=list)
    formula: str | None = None
    input_fields: list[str] = field(default_factory=list)
    policy_version: str | None = None
    last_verified_at: str | None = None

    def __post_init__(self) -> None:
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

    def __post_init__(self) -> None:
        if self.result in ("PASS", "FAIL") and self.observed.value is None:
            raise ValueError(f"{self.condition_id}: {self.result} requires observed.value")
```

And add one field to the existing `Metric` dataclass (insert after `input_sources`):
```python
    evidence: dict[str, list["EvidenceRef"]] = field(default_factory=dict)
```

Also add a same-shaped field to the existing `RuleResult` dataclass (insert after its existing `evidence: list[str]` field — keep that field's name and type exactly as-is since ~30 existing tests assert against it as a list of human-readable strings; this is a new, separately-named field):
```python
    evidence_refs: dict[str, list["EvidenceRef"]] = field(default_factory=dict)
```
Spec §7 requires risk flags to carry "chứng từ nguồn" (source citations) the same way metric cards do — this is the field that carries them, kept distinct from `RuleResult.evidence` (the existing human-readable string list) to avoid breaking any existing test.

- [ ] **Step 4: Run tests to verify they pass**

Run: `/usr/local/bin/python -m pytest tests/test_engine_core_types.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Run full suite and commit**

Run: `/usr/local/bin/python -m pytest -q`
Expected: all previously-passing tests still pass (Metric's new field has a default, so no existing `Metric(...)` call site breaks).

```bash
git add app/engine/core/types.py tests/test_engine_core_types.py
git commit -m "feat: add evidence-tracked field/condition data types"
```

---

## Task 2: Evidence search over documents

**Files:**
- Create: `app/extraction/evidence_search.py`
- Test: `tests/test_extraction_evidence_search.py`

**Interfaces:**
- Consumes: `ExtractedDocument` (app/extraction/types.py) — used as-is in this task; `pages`/`file_id` fields it will gain in Task 4 are read defensively (`getattr(doc, "pages", None)`) so this task does not depend on Task 4 landing first.
- Produces: `find_all_matches(documents: list[ExtractedDocument], pattern: re.Pattern) -> list[tuple[EvidenceRef, str]]` — one `(EvidenceRef, matched_value_text)` pair per match found, scanning every page/row/document rather than stopping at the first hit.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_extraction_evidence_search.py
import re

from app.extraction.evidence_search import find_all_matches
from app.extraction.types import ExtractedDocument, ExtractedTable

PATTERN = re.compile(r"von chu so huu[:\s]*(-?[\d.,]+)")


def _pdf_doc(pages: list[str], file_id="f1", filename="bctc.pdf"):
    doc = ExtractedDocument(
        filename=filename, doc_type="pdf", text="\n".join(pages), tables=[],
        extraction_method="text_layer", confidence=1.0,
    )
    doc.file_id = file_id
    doc.pages = pages
    return doc


def test_finds_match_on_specific_page_not_whole_doc():
    doc = _pdf_doc(["Trang mo dau khong co gi", "Von chu so huu: 500.000.000"])
    matches = find_all_matches([doc], PATTERN)
    assert len(matches) == 1
    ref, value = matches[0]
    assert ref.location == "Trang 2"
    assert ref.file_id == "f1"
    assert "500.000.000" in value


def test_finds_matches_across_multiple_documents():
    doc1 = _pdf_doc(["Von chu so huu: 500.000.000"], file_id="f1", filename="a.pdf")
    doc2 = _pdf_doc(["Von chu so huu: 900.000.000"], file_id="f2", filename="b.pdf")
    matches = find_all_matches([doc1, doc2], PATTERN)
    assert len(matches) == 2
    assert {m[0].filename for m in matches} == {"a.pdf", "b.pdf"}


def test_xlsx_table_cites_sheet_and_row():
    doc = ExtractedDocument(
        filename="bctc.xlsx", doc_type="xlsx", text="", tables=[
            ExtractedTable(rows=[["Chi tieu", "Gia tri"], ["Von chu so huu", "700.000.000"]], sheet_or_page="BCĐKT")
        ], extraction_method="spreadsheet", confidence=1.0,
    )
    doc.file_id = "f3"
    pattern = re.compile(r"von chu so huu\s*\|\s*([\d.,]+)")
    matches = find_all_matches([doc], pattern)
    assert len(matches) == 1
    ref, value = matches[0]
    assert "BCĐKT" in ref.location
    assert "dòng 2" in ref.location


def test_docx_falls_back_to_whole_document_location():
    doc = ExtractedDocument(
        filename="pakd.docx", doc_type="docx", text="Von chu so huu: 300.000.000",
        tables=[], extraction_method="docx", confidence=1.0,
    )
    doc.file_id = "f4"
    matches = find_all_matches([doc], PATTERN)
    assert len(matches) == 1
    assert matches[0][0].location == "Toàn văn bản"


def test_no_match_returns_empty_list():
    doc = _pdf_doc(["Khong co gi lien quan"])
    assert find_all_matches([doc], PATTERN) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/local/bin/python -m pytest tests/test_extraction_evidence_search.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.extraction.evidence_search'`

- [ ] **Step 3: Implement**

```python
# app/extraction/evidence_search.py
import re
import unicodedata

from app.engine.core.types import EvidenceRef
from .types import ExtractedDocument


def _strip_accents_lower(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(c for c in normalized if not unicodedata.combining(c))
    return ascii_text.lower()


def _extract_value(original: str, stripped_match: re.Match) -> str:
    # NFKD-decompose-and-strip is character-count-preserving for standard
    # Vietnamese text (every character maps to exactly one base character,
    # combining marks aside), so a match span found in the accent-stripped
    # haystack indexes correctly into the ORIGINAL string too. Slicing the
    # original here (instead of returning stripped_match.group(1)) recovers
    # proper Vietnamese diacritics/casing for free-text captures like an
    # industry name — numeric captures are unaffected either way.
    start, end = stripped_match.span(1) if stripped_match.groups() else stripped_match.span(0)
    return original[start:end]


def find_all_matches(
    documents: list[ExtractedDocument], pattern: re.Pattern
) -> list[tuple[EvidenceRef, str]]:
    results: list[tuple[EvidenceRef, str]] = []
    for doc in documents:
        file_id = getattr(doc, "file_id", doc.filename)
        pages = getattr(doc, "pages", None)
        if pages:
            for i, page_text in enumerate(pages):
                haystack = _strip_accents_lower(page_text)
                match = pattern.search(haystack)
                if match:
                    line = next(
                        (l for l in page_text.splitlines() if pattern.search(_strip_accents_lower(l))),
                        page_text,
                    )
                    results.append((
                        EvidenceRef(
                            file_id=file_id, filename=doc.filename,
                            location=f"Trang {i + 1}", original_text=line.strip(),
                        ),
                        _extract_value(page_text, match),
                    ))
            continue

        if doc.tables:
            for table in doc.tables:
                for row_idx, row in enumerate(table.rows):
                    joined = " | ".join(row)
                    haystack = _strip_accents_lower(joined)
                    match = pattern.search(haystack)
                    if match:
                        results.append((
                            EvidenceRef(
                                file_id=file_id, filename=doc.filename,
                                location=f"Sheet '{table.sheet_or_page}', dòng {row_idx + 1}",
                                original_text=joined,
                            ),
                            _extract_value(joined, match),
                        ))
            continue

        haystack = _strip_accents_lower(doc.text)
        match = pattern.search(haystack)
        if match:
            line = next(
                (l for l in doc.text.splitlines() if pattern.search(_strip_accents_lower(l))),
                doc.text,
            )
            results.append((
                EvidenceRef(
                    file_id=file_id, filename=doc.filename,
                    location="Toàn văn bản", original_text=line.strip(),
                ),
                _extract_value(doc.text, match),
            ))
    return results
```

Note the xlsx test's pattern matches against `" | ".join(row)` lowercased+unaccented — the row `["Von chu so huu", "700.000.000"]` joins to `"von chu so huu | 700.000.000"`, matching `r"von chu so huu\s*\|\s*([\d.,]+)"`.

Add one more test proving diacritics survive the round trip (append to the same test file):

```python
def test_free_text_capture_preserves_vietnamese_diacritics():
    industry_pattern = re.compile(r"nganh nghe kinh doanh[:\s]*([^\n]+)")
    doc = _pdf_doc(["Nganh nghe kinh doanh: Bán lẻ hàng tiêu dùng"])
    matches = find_all_matches([doc], industry_pattern)
    assert matches[0][1] == "Bán lẻ hàng tiêu dùng"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/usr/local/bin/python -m pytest tests/test_extraction_evidence_search.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add app/extraction/evidence_search.py tests/test_extraction_evidence_search.py
git commit -m "feat: add multi-source evidence search over extracted documents"
```

---

## Task 3: Persist uploaded files (storage layer)

**Files:**
- Modify: `app/storage/db.py`
- Create: `app/storage/files.py`
- Test: `tests/test_storage_files.py`

**Interfaces:**
- Produces: `save_case_file(base_dir: str, case_id: str, file_id: str, filename: str, content: bytes) -> str` (returns the storage path); `get_case_file_path(base_dir: str, case_id: str, file_id: str, filename: str) -> Path | None`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_storage_files.py
from pathlib import Path

from app.storage.files import get_case_file_path, save_case_file


def test_save_and_read_back_file(tmp_path):
    base_dir = str(tmp_path / "eb_files")
    path = save_case_file(base_dir, "EB-001-abcd1234", "f1", "bctc.pdf", b"%PDF-1.4 fake content")
    assert Path(path).exists()
    assert Path(path).read_bytes() == b"%PDF-1.4 fake content"


def test_get_case_file_path_resolves_saved_file(tmp_path):
    base_dir = str(tmp_path / "eb_files")
    save_case_file(base_dir, "EB-001-abcd1234", "f1", "bctc.pdf", b"content")
    resolved = get_case_file_path(base_dir, "EB-001-abcd1234", "f1", "bctc.pdf")
    assert resolved is not None
    assert resolved.read_bytes() == b"content"


def test_get_case_file_path_returns_none_for_unknown_file(tmp_path):
    base_dir = str(tmp_path / "eb_files")
    assert get_case_file_path(base_dir, "EB-001-abcd1234", "missing", "x.pdf") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/local/bin/python -m pytest tests/test_storage_files.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.storage.files'`

- [ ] **Step 3: Implement**

```python
# app/storage/files.py
from pathlib import Path


def _case_dir(base_dir: str, case_id: str) -> Path:
    return Path(base_dir) / case_id


def save_case_file(base_dir: str, case_id: str, file_id: str, filename: str, content: bytes) -> str:
    case_dir = _case_dir(base_dir, case_id)
    case_dir.mkdir(parents=True, exist_ok=True)
    path = case_dir / f"{file_id}__{filename}"
    path.write_bytes(content)
    return str(path)


def get_case_file_path(base_dir: str, case_id: str, file_id: str, filename: str) -> Path | None:
    path = _case_dir(base_dir, case_id) / f"{file_id}__{filename}"
    return path if path.exists() else None
```

Add `case_files` table + `case_id` column to `app/storage/db.py`'s `SCHEMA`:

```python
SCHEMA = """
CREATE TABLE IF NOT EXISTS assessments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_type TEXT NOT NULL,
    customer_name TEXT NOT NULL,
    tax_id TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS case_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id TEXT NOT NULL,
    file_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    content_type TEXT,
    size_bytes INTEGER NOT NULL,
    uploaded_at TEXT NOT NULL DEFAULT (datetime('now')),
    storage_path TEXT NOT NULL
);
"""


def init_db(db_path: str) -> None:
    conn = get_connection(db_path)
    try:
        conn.executescript(SCHEMA)
        cols = {row["name"] for row in conn.execute("PRAGMA table_info(assessments)")}
        if "case_id" not in cols:
            conn.execute("ALTER TABLE assessments ADD COLUMN case_id TEXT")
        conn.commit()
    finally:
        conn.close()
```

(`PRAGMA table_info` + conditional `ALTER TABLE` keeps `init_db` idempotent across repeated calls — same defensive pattern the router already relies on.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `/usr/local/bin/python -m pytest tests/test_storage_files.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Run full suite and commit**

Run: `/usr/local/bin/python -m pytest -q`

```bash
git add app/storage/files.py app/storage/db.py tests/test_storage_files.py
git commit -m "feat: persist uploaded case files and add case_files schema"
```

---

## Task 4: Extraction keeps file_id and per-page provenance

**Files:**
- Modify: `app/extraction/types.py`
- Modify: `app/extraction/pipeline.py`
- Test: `tests/test_extraction_pipeline.py` (add to existing file)

**Interfaces:**
- Consumes: nothing new — this task changes what `extract_document` accepts/returns.
- Produces: `ExtractedDocument.file_id: str` (default `""`, so existing call sites that don't pass one still construct), `ExtractedDocument.pages: list[str] | None` (populated for PDFs only); `extract_document(file_path, filename, file_id: str = "") -> ExtractedDocument` (new optional 3rd param, threaded through to `_extract_pdf_document`).

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_extraction_pipeline.py`:

```python
def test_extract_document_carries_file_id_through(fixtures_dir):
    doc = pipeline.extract_document(str(fixtures_dir / "sample_text.pdf"), "sample_text.pdf", file_id="abc123")
    assert doc.file_id == "abc123"


def test_extract_document_pdf_keeps_per_page_text(fixtures_dir):
    doc = pipeline.extract_document(str(fixtures_dir / "sample_text.pdf"), "sample_text.pdf")
    assert doc.pages is not None
    assert len(doc.pages) >= 1
    assert "".join(doc.pages).strip() != ""


def test_extract_document_xlsx_has_no_pages_field_populated(fixtures_dir):
    doc = pipeline.extract_document(str(fixtures_dir / "sample.xlsx"), "sample.xlsx")
    assert doc.pages is None
```

(Check `tests/fixtures/` first — `sample_text.pdf` and `sample.xlsx` already exist per the fixtures used by the current `test_extraction_pipeline.py`; reuse them rather than generating new ones for this task.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/local/bin/python -m pytest tests/test_extraction_pipeline.py -k file_id_through -v`
Expected: FAIL — `TypeError: extract_document() got an unexpected keyword argument 'file_id'`

- [ ] **Step 3: Implement**

`app/extraction/types.py` — add two fields to `ExtractedDocument` (after `warnings`):

```python
    file_id: str = ""
    pages: list[str] | None = None
```

`app/extraction/pipeline.py` — thread `file_id` through and stop discarding the per-page list:

```python
def extract_document(file_path: str, filename: str, file_id: str = "") -> ExtractedDocument:
    ext = os.path.splitext(filename)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Định dạng file không được hỗ trợ: {ext}")

    if ext == ".pdf":
        doc = _extract_pdf_document(file_path, filename)
    elif ext == ".docx":
        doc = extract_docx(file_path, filename)
    elif ext == ".xlsx":
        doc = extract_xlsx(file_path, filename)
    else:
        doc = extract_csv(file_path, filename)  # ext == ".csv"
    doc.file_id = file_id
    return doc
```

In `_extract_pdf_document`, the no-OCR-needed early return already builds `text` from `page_texts` — set `pages` there too:

```python
    if not ocr_needed_idx:
        text = "\n".join(f"[Trang {i + 1}]\n{t}" for i, t in enumerate(page_texts))
        return ExtractedDocument(
            filename=filename, doc_type="pdf", text=text, tables=[],
            extraction_method="text_layer", confidence=1.0, warnings=[], pages=page_texts,
        )
```

And at the bottom, where `final_texts` is built and the ultimate `ExtractedDocument` is constructed (after the OCR `ThreadPoolExecutor` block), add `pages=final_texts` to that `return ExtractedDocument(...)` call too — `final_texts` is already a per-page list at that point (`list(page_texts)` with OCR'd pages overwritten in place), so no other logic changes.

- [ ] **Step 4: Run tests to verify they pass**

Run: `/usr/local/bin/python -m pytest tests/test_extraction_pipeline.py -v`
Expected: PASS (all, including the 3 new tests — full file since `extract_document`'s signature changed for every caller in this file)

- [ ] **Step 5: Run full suite and commit**

Run: `/usr/local/bin/python -m pytest -q`
Expected: green — `file_id: str = ""` and `pages: list[str] | None = None` both default, so no other caller of `extract_document`/`ExtractedDocument(...)` breaks.

```bash
git add app/extraction/types.py app/extraction/pipeline.py tests/test_extraction_pipeline.py
git commit -m "feat: thread file_id and preserve per-page PDF text through extraction"
```

---

## Task 5: financial_inputs.py returns parallel evidence, detects conflicts

**Files:**
- Modify: `app/agents/eb/financial_inputs.py`
- Modify: `tests/agents/eb/test_financial_inputs.py`
- Test: same file (extended)

**Interfaces:**
- Consumes: `find_all_matches` (Task 2), `EvidenceRef` (Task 1).
- Produces: `extract_financial_inputs(documents) -> tuple[EbFinancialInputs, dict[str, FieldEvidence]]` (changed return type — was `EbFinancialInputs` alone). `FieldEvidence` is a new small dataclass: `status: Literal["COMPUTED", "PENDING_REVIEW", "MISSING_DATA"]`, `evidence: list[EvidenceRef]`. `EbFinancialInputs` itself is unchanged (still plain `float | None` fields) — every downstream rule module (`liquidity.py` etc.) keeps working against it unmodified; only the router (Task 6) and the new overview engine (Tasks 8-15) read the second tuple element.

- [ ] **Step 1: Update existing tests for the new tuple return**

Every existing test in `tests/agents/eb/test_financial_inputs.py` calls `extract_financial_inputs([_doc(text)])` and reads `inputs.field`. Update each call site to unpack:

```python
def test_extracts_equity_and_current_assets_liabilities():
    text = (
        "Von chu so huu: 500,000,000\n"
        "Tai san ngan han: 2,000,000,000\n"
        "No ngan han: 2,500,000,000\n"
    )
    inputs, _ = extract_financial_inputs([_doc(text)])
    assert inputs.equity_vnd == 500_000_000
    assert inputs.current_assets_vnd == 2_000_000_000
    assert inputs.current_liabilities_vnd == 2_500_000_000
```

Apply the same `inputs, _ = extract_financial_inputs(...)` change to every other test function in the file (`test_extracts_cfo`, `test_extracts_short_term_debt_and_total_liabilities`, `test_extracts_ebit_and_interest_expense`, `test_missing_fields_are_none`, `test_extracts_vn_locale_figures_without_silent_truncation`, `test_vn_locale_balance_sheet_yields_correct_nwc_sign` — that last one already reads `inputs` further down via `compute_nwc(inputs)`, so just fix its `extract_financial_inputs` call site the same way).

Then add new tests for evidence + conflict detection:

```python
def test_returns_evidence_for_matched_field():
    text = "Von chu so huu: 500,000,000\n"
    inputs, evidence = extract_financial_inputs([_doc(text)])
    assert inputs.equity_vnd == 500_000_000
    ev = evidence["equity_vnd"]
    assert ev.status == "COMPUTED"
    assert len(ev.evidence) == 1
    assert ev.evidence[0].filename == "bctc.pdf"


def test_missing_field_has_missing_data_evidence_status():
    inputs, evidence = extract_financial_inputs([_doc("khong co gi")])
    assert inputs.equity_vnd is None
    assert evidence["equity_vnd"].status == "MISSING_DATA"
    assert evidence["equity_vnd"].evidence == []


def test_conflicting_values_across_files_yield_pending_review_and_none_value():
    doc1 = _doc("Von chu so huu: 500.000.000", filename="a.pdf")
    doc2 = _doc("Von chu so huu: 900.000.000", filename="b.pdf")
    inputs, evidence = extract_financial_inputs([doc1, doc2])
    assert inputs.equity_vnd is None  # never silently pick one
    ev = evidence["equity_vnd"]
    assert ev.status == "PENDING_REVIEW"
    assert len(ev.evidence) == 2
    assert {e.filename for e in ev.evidence} == {"a.pdf", "b.pdf"}


def test_same_value_confirmed_in_two_files_stays_computed():
    doc1 = _doc("Von chu so huu: 500.000.000", filename="a.pdf")
    doc2 = _doc("Von chu so huu: 500.000.000", filename="b.pdf")
    inputs, evidence = extract_financial_inputs([doc1, doc2])
    assert inputs.equity_vnd == 500_000_000
    assert evidence["equity_vnd"].status == "COMPUTED"
    assert len(evidence["equity_vnd"].evidence) == 2
```

Update the `_doc` helper at the top of the file to accept a `filename` param and set `file_id`/`pages` for evidence_search:

```python
def _doc(text: str, filename: str = "bctc.pdf") -> ExtractedDocument:
    doc = ExtractedDocument(
        filename=filename, doc_type="pdf", text=text, tables=[],
        extraction_method="text_layer", confidence=1.0,
    )
    doc.file_id = filename
    doc.pages = [text]
    return doc
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/local/bin/python -m pytest tests/agents/eb/test_financial_inputs.py -v`
Expected: FAIL — old tests fail with "too many values to unpack" or similar (tuple vs dataclass), new tests fail with `ImportError`/`AttributeError`.

- [ ] **Step 3: Implement**

```python
# app/agents/eb/financial_inputs.py
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Literal

from app.engine.core.numbers import parse_vn_number
from app.engine.core.types import EvidenceRef
from app.extraction.evidence_search import find_all_matches
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


@dataclass
class FieldEvidence:
    status: Literal["COMPUTED", "PENDING_REVIEW", "MISSING_DATA"]
    evidence: list[EvidenceRef] = field(default_factory=list)


def _strip_accents_lower(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(c for c in normalized if not unicodedata.combining(c))
    return ascii_text.lower()


def _to_number(raw: str) -> float:
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
    "cfads_vnd": re.compile(r"cfads[:\s]*(-?[\d.,]+)"),
    "principal_due_vnd": re.compile(r"goc den han[:\s]*(-?[\d.,]+)"),
    "interest_due_vnd": re.compile(r"lai den han[:\s]*(-?[\d.,]+)"),
    "ebit_vnd": re.compile(r"ebit\)?[:\s]*(-?[\d.,]+)"),
    "interest_expense_vnd": re.compile(r"chi phi lai vay[:\s]*(-?[\d.,]+)"),
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
```

Note `find_all_matches` scans `_strip_accents_lower`'d text internally (Task 2's implementation already lowercases+strips accents before matching), so the patterns here (already lowercase, no accents) keep working unchanged against it.

- [ ] **Step 4: Run tests to verify they pass**

Run: `/usr/local/bin/python -m pytest tests/agents/eb/test_financial_inputs.py -v`
Expected: PASS (all — updated + 4 new)

- [ ] **Step 5: Run full suite and commit**

Run: `/usr/local/bin/python -m pytest -q`
Expected: **FAIL** — `tests/agents/eb/test_router.py` and any other caller of `extract_financial_inputs` inside `app/agents/eb/router.py` itself now breaks (router still does `financial_inputs = extract_financial_inputs(documents)` expecting a single value). This is expected and fixed in Task 6, not here — do not attempt to fix `router.py` in this task; commit only `financial_inputs.py` + its own test file, matching the "one deliverable per task" rule, then proceed immediately to Task 6 (do not stop with the suite red between tasks in practice — Tasks 5 and 6 are worked as one continuous TDD cycle since router.py is what makes the suite green again).

```bash
git add app/agents/eb/financial_inputs.py tests/agents/eb/test_financial_inputs.py
git commit -m "feat: financial_inputs.py returns evidence and detects cross-file conflicts"
```

---

## Task 6: Router persists files, wires file_id, exposes evidence file endpoint

**Files:**
- Modify: `app/agents/eb/router.py`
- Modify: `app/agents/eb/liquidity.py`, `leverage.py`, `repayment_capacity.py` (attach `evidence` onto the `Metric` each already returns, and `evidence_refs` onto the `RuleResult` each's `evaluate_rf0x` returns)
- Modify: `app/agents/eb/cashflow_flags.py`, `dsp_reconciliation.py` (attach `evidence_refs` onto RF02/RF04's `RuleResult`)
- Test: `tests/agents/eb/test_router.py` (add new tests)

**Interfaces:**
- Consumes: `save_case_file`/`get_case_file_path` (Task 3), `extract_financial_inputs` returning a tuple (Task 5), `extract_document(..., file_id=...)` (Task 4).
- Produces: `GET /api/eb/files/{case_id}/{file_id}` endpoint; `computed["credit_engine"][name]["evidence"]` populated for nwc/current_ratio/short_term_debt_ratio/dscr/icr; `computed["risk_flags"][*]["evidence_refs"]` populated for RF01–RF05 when the field_evidence backing them carries citations.

- [ ] **Step 1: Write the failing tests**

Add to `tests/agents/eb/test_router.py`:

```python
def test_assess_endpoint_case_id_is_unique_per_run(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test8.db"))
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(eb_router, "generate_narrative", lambda computed: {"why": [], "credit_memo": ""})

    files = {"files": ("bctc.csv", io.BytesIO(b"Von chu so huu: 500.000.000\n"), "text/csv")}
    with TestClient(app) as client:
        resp1 = client.post("/api/eb/assess", data={"customer_name": "A", "tax_id": "0100000001"}, files=files)
        files2 = {"files": ("bctc.csv", io.BytesIO(b"Von chu so huu: 500.000.000\n"), "text/csv")}
        resp2 = client.post("/api/eb/assess", data={"customer_name": "A", "tax_id": "0100000001"}, files=files2)
    assert resp1.json()["case_id"] != resp2.json()["case_id"]
    assert resp1.json()["case_id"].startswith("EB-0100000001-")


def test_assess_endpoint_persists_uploaded_file_and_serves_it_back(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test9.db"))
    monkeypatch.setenv("CASE_FILES_DIR", str(tmp_path / "eb_files"))
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(eb_router, "generate_narrative", lambda computed: {"why": [], "credit_memo": ""})

    content = b"Von chu so huu: 500.000.000\n"
    files = {"files": ("bctc.csv", io.BytesIO(content), "text/csv")}
    with TestClient(app) as client:
        resp = client.post("/api/eb/assess", data={"customer_name": "A", "tax_id": "0100000001"}, files=files)
        case_id = resp.json()["case_id"]
        nwc_evidence = resp.json()["credit_engine"]["nwc"]
        assert nwc_evidence.get("evidence"), "expected NWC metric to carry evidence citations"
        file_id = list(nwc_evidence["evidence"].values())[0][0]["file_id"]
        file_resp = client.get(f"/api/eb/files/{case_id}/{file_id}")
    assert file_resp.status_code == 200
    assert file_resp.content == content


def test_get_file_endpoint_404s_on_unknown_case(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test10.db"))
    monkeypatch.setenv("CASE_FILES_DIR", str(tmp_path / "eb_files"))
    from app.config import get_settings

    get_settings.cache_clear()
    with TestClient(app) as client:
        resp = client.get("/api/eb/files/NOPE/NOPE")
    assert resp.status_code == 404
```

`CASE_FILES_DIR` is a new env-driven setting — add it to `app/config.py`'s `Settings` dataclass and `get_settings()`:
```python
    case_files_dir: str = "data/eb_files"
```
and in `get_settings()`:
```python
        case_files_dir=os.environ.get("CASE_FILES_DIR", "data/eb_files"),
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/local/bin/python -m pytest tests/agents/eb/test_router.py -v`
Expected: FAIL — existing tests fail first because `extract_financial_inputs` now returns a tuple (router unpacks it wrong); new tests fail on 404/missing endpoint.

- [ ] **Step 3: Implement**

`app/agents/eb/router.py` — replace the file-saving loop and the `financial_inputs` call:

```python
import uuid
from fastapi import HTTPException
from fastapi.responses import FileResponse

from app.storage.files import get_case_file_path, save_case_file

...

@router.post("/assess")
async def assess(
    customer_name: str = Form(...),
    tax_id: str = Form(...),
    files: list[UploadFile] = File(...),
) -> dict:
    request_start = time.monotonic()
    settings = get_settings()
    case_id = f"EB-{tax_id}-{uuid.uuid4().hex[:8]}"
    with tempfile.TemporaryDirectory() as tmp_dir:
        saved_files: list[tuple[str, str, str]] = []  # (path, name, file_id)
        for upload in files:
            file_id = uuid.uuid4().hex[:10]
            path = os.path.join(tmp_dir, upload.filename)
            content = await upload.read()
            with open(path, "wb") as out:
                out.write(content)
            save_case_file(settings.case_files_dir, case_id, file_id, upload.filename, content)
            saved_files.append((path, upload.filename, file_id))

        documents = []
        extraction_warnings: list[str] = []
        for path, name, file_id in saved_files:
            try:
                documents.append(extract_document(path, name, file_id=file_id))
            except Exception as exc:  # noqa: BLE001
                extraction_warnings.append(f"{name}: không đọc được nội dung file ({exc})")

        classified = classify_documents(documents)
        missing = missing_from_classified(classified)

        financial_inputs, field_evidence = extract_financial_inputs(documents)

        nwc = compute_nwc(financial_inputs, field_evidence)
        current_ratio = compute_current_ratio(financial_inputs, field_evidence)
        short_term_debt_ratio = compute_short_term_debt_ratio(financial_inputs, field_evidence)
        dscr = compute_dscr(financial_inputs, field_evidence)
        icr = compute_icr(financial_inputs, field_evidence)
```

(the rest of the function body — risk flags, `credit_readiness`, narrative — stays exactly as-is, since `evaluate_rf0x` functions still take `financial_inputs`, unchanged).

Change `computed["case_id"]` to use the new `case_id` variable instead of `f"EB-{tax_id}"`.

Add the new endpoint at the bottom of the file:

```python
@router.get("/files/{case_id}/{file_id}")
async def get_evidence_file(case_id: str, file_id: str) -> FileResponse:
    settings = get_settings()
    db_path = settings.db_path
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT filename, content_type FROM case_files WHERE case_id = ? AND file_id = ?",
            (case_id, file_id),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy file")
    path = get_case_file_path(settings.case_files_dir, case_id, file_id, row["filename"])
    if path is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy file")
    return FileResponse(path, media_type=row["content_type"] or "application/octet-stream", filename=row["filename"])
```

This needs `case_files` rows actually written on save — update `save_case_file` callers in the router to also insert a DB row (via a new `app/storage/files.py` helper `record_case_file(db_path, case_id, file_id, filename, content_type, size_bytes, storage_path)` that does the `INSERT INTO case_files`, called right after `save_case_file` in the router's upload loop). Add:

```python
# app/storage/files.py, appended
from .db import get_connection


def record_case_file(
    db_path: str, case_id: str, file_id: str, filename: str,
    content_type: str | None, size_bytes: int, storage_path: str,
) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT INTO case_files (case_id, file_id, filename, content_type, size_bytes, storage_path) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (case_id, file_id, filename, content_type, size_bytes, storage_path),
        )
        conn.commit()
    finally:
        conn.close()
```

and in the router's upload loop, after `save_case_file(...)`:
```python
            storage_path = save_case_file(settings.case_files_dir, case_id, file_id, upload.filename, content)
            init_db(settings.db_path)
            record_case_file(
                settings.db_path, case_id, file_id, upload.filename,
                upload.content_type, len(content), storage_path,
            )
```

`liquidity.py`/`leverage.py`/`repayment_capacity.py` — each `compute_*` function gains a second optional param and attaches the matching `FieldEvidence.evidence` list onto the returned `Metric.evidence` dict, e.g. in `liquidity.py`:

```python
def compute_nwc(inputs: EbFinancialInputs, field_evidence: dict | None = None) -> Metric:
    if inputs.current_assets_vnd is None or inputs.current_liabilities_vnd is None:
        return Metric.need_more_data("nwc", "tai_san_ngan_han - no_ngan_han")
    value = inputs.current_assets_vnd - inputs.current_liabilities_vnd
    evidence = {}
    if field_evidence:
        for key in ("current_assets_vnd", "current_liabilities_vnd"):
            if key in field_evidence:
                evidence[key] = field_evidence[key].evidence
    return Metric(
        metric="nwc", value=value, formula="tai_san_ngan_han - no_ngan_han",
        input_values={"current_assets_vnd": inputs.current_assets_vnd, "current_liabilities_vnd": inputs.current_liabilities_vnd},
        input_sources={"current_assets_vnd": "bctc", "current_liabilities_vnd": "bctc"},
        evidence=evidence,
    )
```

The default `field_evidence: dict | None = None` keeps every existing test in `test_liquidity.py`/`test_leverage.py`/`test_repayment_capacity.py` passing unchanged (they call `compute_nwc(inputs)` with one arg). Apply the same `field_evidence` param + `evidence` dict pattern to `compute_current_ratio`, `compute_short_term_debt_ratio` (leverage.py), `compute_dscr`, `compute_icr` (repayment_capacity.py) — each keyed by its own `input_values` field names.

Now thread the same `field_evidence` through into each RF0x `evaluate_*` function, populating the new `RuleResult.evidence_refs` (Task 1) — this is what satisfies spec §7's "chứng từ nguồn" requirement for risk flags, not just metric cards. Each function gains the same optional `field_evidence: dict | None = None` parameter and forwards the relevant entries' `.evidence` lists:

`liquidity.py`'s `evaluate_rf01_capital_imbalance`:
```python
def evaluate_rf01_capital_imbalance(
    inputs: EbFinancialInputs, nwc: Metric, field_evidence: dict | None = None,
) -> RuleResult:
    ...  # existing body unchanged up to each `return RuleResult(...)` call
```
Add `evidence_refs=nwc.evidence` to every `return RuleResult(...)` in this function (nwc's own `.evidence` dict already carries `current_assets_vnd`/`current_liabilities_vnd` citations from Task 6's `compute_nwc` change above — no separate lookup needed here).

`leverage.py`'s `evaluate_rf03_short_term_debt_ratio(ratio: Metric)` — same pattern: add `evidence_refs=ratio.evidence` to each `return RuleResult(...)`.

`repayment_capacity.py`'s `evaluate_rf05_weak_repayment_capacity(dscr: Metric, icr: Metric)` — merge both metrics' evidence: add `evidence_refs={**dscr.evidence, **icr.evidence}` to each `return RuleResult(...)`.

`cashflow_flags.py`'s `evaluate_rf02_negative_cfo` gains the same optional parameter:
```python
def evaluate_rf02_negative_cfo(inputs: EbFinancialInputs, field_evidence: dict | None = None) -> RuleResult:
    ...  # existing body unchanged
```
Add `evidence_refs={"cfo_vnd": field_evidence["cfo_vnd"].evidence} if field_evidence and "cfo_vnd" in field_evidence else {}` to each `return RuleResult(...)`.

`dsp_reconciliation.py`'s `evaluate_rf04_dsp_mismatch` — same pattern, keyed by `revenue_bctc_vnd`/`revenue_dsp_vnd`:
```python
def evaluate_rf04_dsp_mismatch(inputs: EbFinancialInputs, field_evidence: dict | None = None) -> RuleResult:
    ...  # existing body unchanged
```
Add to each `return RuleResult(...)`:
```python
    evidence_refs={
        k: field_evidence[k].evidence for k in ("revenue_bctc_vnd", "revenue_dsp_vnd")
        if field_evidence and k in field_evidence
    },
```

Router changes (`app/agents/eb/router.py`) — pass `field_evidence` into every `evaluate_rf0x` call alongside the metric it already receives:
```python
        risk_flags = [
            evaluate_rf01_capital_imbalance(financial_inputs, nwc, field_evidence),
            evaluate_rf02_negative_cfo(financial_inputs, field_evidence),
            evaluate_rf03_short_term_debt_ratio(short_term_debt_ratio, field_evidence),
            evaluate_rf04_dsp_mismatch(financial_inputs, field_evidence),
            evaluate_rf05_weak_repayment_capacity(dscr, icr, field_evidence),
        ]
```

Add one new test to each of `test_liquidity.py`, `test_leverage.py`, `test_repayment_capacity.py`, `test_cashflow_flags.py`, `test_dsp_reconciliation.py` proving the wiring (example for `test_cashflow_flags.py`):
```python
def test_rf02_carries_evidence_refs_when_field_evidence_provided():
    from app.agents.eb.financial_inputs import FieldEvidence
    from app.engine.core.types import EvidenceRef

    ref = EvidenceRef(file_id="f1", filename="bctc.pdf", location="Trang 1", original_text="CFO: -1.188.000.000")
    field_evidence = {"cfo_vnd": FieldEvidence(status="COMPUTED", evidence=[ref])}
    result = evaluate_rf02_negative_cfo(EbFinancialInputs(cfo_vnd=-1_188_000_000), field_evidence)
    assert result.evidence_refs["cfo_vnd"] == [ref]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/usr/local/bin/python -m pytest tests/agents/eb -v`
Expected: PASS (all — existing + new)

- [ ] **Step 5: Run full suite and commit**

Run: `/usr/local/bin/python -m pytest -q`
Expected: green.

```bash
git add app/agents/eb/router.py app/agents/eb/liquidity.py app/agents/eb/leverage.py \
        app/agents/eb/repayment_capacity.py app/agents/eb/cashflow_flags.py \
        app/agents/eb/dsp_reconciliation.py app/storage/files.py app/config.py \
        tests/agents/eb/test_router.py tests/agents/eb/test_liquidity.py \
        tests/agents/eb/test_leverage.py tests/agents/eb/test_repayment_capacity.py \
        tests/agents/eb/test_cashflow_flags.py tests/agents/eb/test_dsp_reconciliation.py
git commit -m "feat: persist EB uploads, generate unique case_id, wire metric and risk-flag evidence"
```

---

## Task 7: Policy config store + internal-system gate

**Files:**
- Create: `app/agents/eb/policy_config.py`
- Create: `app/agents/eb/internal_systems.py`
- Test: `tests/agents/eb/test_policy_config.py`
- Test: `tests/agents/eb/test_internal_systems.py`

**Interfaces:**
- Produces: `PolicyThreshold` dataclass with `.policy_version_label` property; `POLICY_CONFIG: dict[str, PolicyThreshold]`; `check_internal_system(system: str) -> ConditionResult` (always returns `"PENDING_INTERNAL_CHECK"` today).

- [ ] **Step 1: Write the failing tests**

```python
# tests/agents/eb/test_policy_config.py
from app.agents.eb.policy_config import POLICY_CONFIG, PolicyThreshold


def test_demo_threshold_renders_demo_label():
    t = PolicyThreshold(20_000_000_000)
    assert t.is_demo is True
    assert t.policy_version_label == "Ngưỡng demo – chờ nghiệp vụ xác nhận"


def test_confirmed_threshold_renders_doc_code_label():
    t = PolicyThreshold(20_000_000_000, doc_code="QĐ.EB.012", version="1.0", effective_date="2026-01-01", is_demo=False)
    assert "QĐ.EB.012" in t.policy_version_label
    assert "2026-01-01" in t.policy_version_label


def test_revenue_thresholds_are_registered():
    assert POLICY_CONFIG["REVENUE_12M_MIN_VND"].value == 20_000_000_000
    assert POLICY_CONFIG["REVENUE_12M_MAX_VND"].value == 1_000_000_000_000


def test_top_partners_threshold_carries_open_question():
    t = POLICY_CONFIG["TOP_PARTNERS_COUNT"]
    assert t.value == 5
    assert t.open_question is not None
    assert "đầu ra" in t.open_question or "đầu vào" in t.open_question
```

```python
# tests/agents/eb/test_internal_systems.py
from app.agents.eb.internal_systems import check_internal_system


def test_always_returns_pending_internal_check():
    assert check_internal_system("CIF") == "PENDING_INTERNAL_CHECK"
    assert check_internal_system("CIC") == "PENDING_INTERNAL_CHECK"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/local/bin/python -m pytest tests/agents/eb/test_policy_config.py tests/agents/eb/test_internal_systems.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

```python
# app/agents/eb/policy_config.py
from dataclasses import dataclass
from typing import Any


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
        5,
        open_question=(
            "Áp dụng riêng đầu ra/đầu vào hay gộp — chờ chủ chính sách xác nhận."
        ),
    ),
    "PROHIBITED_INDUSTRIES": PolicyThreshold([]),
}
```

```python
# app/agents/eb/internal_systems.py
from app.engine.core.types import ConditionResult


def check_internal_system(system: str) -> ConditionResult:
    """Always PENDING_INTERNAL_CHECK today — no real CIF/CIC/DSP/AML
    connection exists. Swap this function's body, not its callers, when a
    real integration lands."""
    return "PENDING_INTERNAL_CHECK"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/usr/local/bin/python -m pytest tests/agents/eb/test_policy_config.py tests/agents/eb/test_internal_systems.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add app/agents/eb/policy_config.py app/agents/eb/internal_systems.py \
        tests/agents/eb/test_policy_config.py tests/agents/eb/test_internal_systems.py
git commit -m "feat: add demo-marked policy config store and internal-system gate"
```

---

## Task 8: Shared numeric-condition builder

**Files:**
- Create: `app/agents/eb/overview/__init__.py` (empty package marker for now — populated in Task 15)
- Create: `app/agents/eb/overview/_common.py`
- Test: `tests/agents/eb/overview/test_common.py`
- Test: `tests/agents/eb/overview/__init__.py` (empty)

**Interfaces:**
- Consumes: `find_all_matches` (Task 2), `parse_vn_number` (existing), `EvidencedField`/`ConditionRow` (Task 1).
- Produces: `build_numeric_condition(condition_id, condition_name, field_id, documents, pattern, compare_rule_text, evaluate_fn, unit="VND", period=None) -> ConditionRow` — the shared "regex → number → PASS/FAIL against a threshold" path six of the eleven conditions use.

- [ ] **Step 1: Write the failing tests**

```python
# tests/agents/eb/overview/test_common.py
import re

from app.agents.eb.overview._common import build_numeric_condition
from app.extraction.types import ExtractedDocument

PATTERN = re.compile(r"von chu so huu[:\s]*(-?[\d.,]+)")


def _doc(text: str, filename="bctc.pdf"):
    doc = ExtractedDocument(
        filename=filename, doc_type="pdf", text=text, tables=[],
        extraction_method="text_layer", confidence=1.0,
    )
    doc.file_id = filename
    doc.pages = [text]
    return doc


def test_pass_when_value_satisfies_rule():
    row = build_numeric_condition(
        "C08", "Vốn chủ sở hữu", "equity_vnd", [_doc("Von chu so huu: 500.000.000")],
        PATTERN, "> 0", lambda v: v > 0,
    )
    assert row.result == "PASS"
    assert row.observed.value == 500_000_000
    assert row.observed.status == "COMPUTED"
    assert len(row.observed.evidence) == 1


def test_fail_when_value_does_not_satisfy_rule():
    row = build_numeric_condition(
        "C08", "Vốn chủ sở hữu", "equity_vnd", [_doc("Von chu so huu: -100.000.000")],
        PATTERN, "> 0", lambda v: v > 0,
    )
    assert row.result == "FAIL"


def test_insufficient_data_when_no_match():
    row = build_numeric_condition(
        "C08", "Vốn chủ sở hữu", "equity_vnd", [_doc("khong co gi")],
        PATTERN, "> 0", lambda v: v > 0,
    )
    assert row.result == "INSUFFICIENT_DATA"
    assert row.observed.value is None
    assert row.reason_if_incomplete is not None


def test_insufficient_data_when_sources_conflict():
    docs = [_doc("Von chu so huu: 500.000.000", "a.pdf"), _doc("Von chu so huu: 900.000.000", "b.pdf")]
    row = build_numeric_condition("C08", "Vốn chủ sở hữu", "equity_vnd", docs, PATTERN, "> 0", lambda v: v > 0)
    assert row.result == "INSUFFICIENT_DATA"
    assert row.observed.value is None
    assert len(row.observed.evidence) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/local/bin/python -m pytest tests/agents/eb/overview/test_common.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.agents.eb.overview'`

- [ ] **Step 3: Implement**

```python
# app/agents/eb/overview/_common.py
import re
from collections.abc import Callable

from app.engine.core.numbers import parse_vn_number
from app.engine.core.types import ConditionRow, EvidencedField
from app.extraction.evidence_search import find_all_matches
from app.extraction.types import ExtractedDocument


def build_numeric_condition(
    condition_id: str,
    condition_name: str,
    field_id: str,
    documents: list[ExtractedDocument],
    pattern: re.Pattern,
    compare_rule_text: str,
    evaluate_fn: Callable[[float], bool],
    unit: str | None = "VND",
    period: str | None = None,
) -> ConditionRow:
    matches = find_all_matches(documents, pattern)
    if not matches:
        observed = EvidencedField(
            field_id=field_id, label=condition_name, value=None, unit=unit,
            period=period, status="MISSING_DATA",
        )
        return ConditionRow(
            condition_id=condition_id, condition_name=condition_name, observed=observed,
            compare_rule=compare_rule_text, result="INSUFFICIENT_DATA",
            reason_if_incomplete=f"Không tìm thấy dữ liệu cho '{condition_name}' trong hồ sơ đã tải lên.",
        )

    distinct_values = {round(parse_vn_number(raw), 6) for _, raw in matches}
    refs = [ref for ref, _ in matches]

    if len(distinct_values) > 1:
        observed = EvidencedField(
            field_id=field_id, label=condition_name, value=None, unit=unit,
            period=period, status="PENDING_REVIEW", evidence=refs,
        )
        return ConditionRow(
            condition_id=condition_id, condition_name=condition_name, observed=observed,
            compare_rule=compare_rule_text, result="INSUFFICIENT_DATA",
            reason_if_incomplete="Các nguồn tài liệu cho giá trị khác nhau — cần cán bộ xác nhận trước khi kết luận.",
        )

    value = parse_vn_number(matches[0][1])
    observed = EvidencedField(
        field_id=field_id, label=condition_name, value=value, unit=unit,
        period=period, status="COMPUTED", evidence=refs,
    )
    result = "PASS" if evaluate_fn(value) else "FAIL"
    return ConditionRow(
        condition_id=condition_id, condition_name=condition_name, observed=observed,
        compare_rule=compare_rule_text, result=result,
    )
```

`app/agents/eb/overview/__init__.py`: empty file for now (Task 15 fills it in).
`tests/agents/eb/overview/__init__.py`: empty file (test package marker).

- [ ] **Step 4: Run tests to verify they pass**

Run: `/usr/local/bin/python -m pytest tests/agents/eb/overview/test_common.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add app/agents/eb/overview/ tests/agents/eb/overview/
git commit -m "feat: add shared numeric-condition builder for EB overview checklist"
```

---

## Task 9: Internal-system-gated conditions (Đối tượng áp dụng, Lịch sử quan hệ tín dụng)

**Files:**
- Create: `app/agents/eb/overview/customer_status.py`
- Create: `app/agents/eb/overview/credit_history.py`
- Test: `tests/agents/eb/overview/test_customer_status.py`
- Test: `tests/agents/eb/overview/test_credit_history.py`

**Interfaces:**
- Produces: `evaluate_customer_segment() -> ConditionRow` (condition_id `"C01"`), `evaluate_operating_status(documents) -> ConditionRow` (condition_id `"C05"`), `evaluate_credit_history() -> ConditionRow` (condition_id `"C11"`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/agents/eb/overview/test_customer_status.py
from app.agents.eb.overview.customer_status import evaluate_customer_segment, evaluate_operating_status
from app.extraction.types import ExtractedDocument


def _doc(text: str):
    doc = ExtractedDocument(
        filename="dkkd.pdf", doc_type="pdf", text=text, tables=[],
        extraction_method="text_layer", confidence=1.0,
    )
    doc.file_id = "dkkd.pdf"
    doc.pages = [text]
    return doc


def test_customer_segment_always_pending_internal_check():
    # Even a document that plainly claims "khách hàng hiện hữu" cannot decide
    # this without CIF — the app has no live CIF connection.
    row = evaluate_customer_segment()
    assert row.result == "PENDING_INTERNAL_CHECK"
    assert row.observed.status == "MISSING_DATA"
    assert row.observed.value is None


def test_operating_status_pass_when_active_keyword_found():
    row = evaluate_operating_status([_doc("Tinh trang: dang hoat dong")])
    assert row.result == "PASS"
    assert row.observed.value == "dang hoat dong"


def test_operating_status_fail_when_dissolved_keyword_found():
    row = evaluate_operating_status([_doc("Tinh trang: da giai the")])
    assert row.result == "FAIL"


def test_operating_status_insufficient_data_when_not_stated():
    row = evaluate_operating_status([_doc("Khong co thong tin tinh trang")])
    assert row.result == "INSUFFICIENT_DATA"
```

```python
# tests/agents/eb/overview/test_credit_history.py
from app.agents.eb.overview.credit_history import evaluate_credit_history


def test_credit_history_always_pending_internal_check():
    row = evaluate_credit_history()
    assert row.result == "PENDING_INTERNAL_CHECK"
    assert row.observed.value is None
    assert "CIC" in row.reason_if_incomplete
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/local/bin/python -m pytest tests/agents/eb/overview/test_customer_status.py tests/agents/eb/overview/test_credit_history.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

```python
# app/agents/eb/overview/customer_status.py
import re
import unicodedata

from app.agents.eb.internal_systems import check_internal_system
from app.engine.core.types import ConditionRow, EvidencedField
from app.extraction.evidence_search import find_all_matches
from app.extraction.types import ExtractedDocument

_STATUS_PATTERN = re.compile(r"(dang hoat dong|tam ngung hoat dong|da giai the|giai the)")


def _strip_accents_lower(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(c for c in normalized if not unicodedata.combining(c))
    return ascii_text.lower()


def evaluate_customer_segment() -> ConditionRow:
    # Whether this customer is new or existing at MSB can only come from the
    # bank's own CIF/credit-relationship history — a BCTC or business
    # registration certificate, however complete, cannot answer this.
    observed = EvidencedField(
        field_id="customer_segment", label="Đối tượng áp dụng", value=None,
        unit=None, period=None, status="MISSING_DATA",
    )
    return ConditionRow(
        condition_id="C01", condition_name="Đối tượng áp dụng", observed=observed,
        compare_rule="Xác định KH tín dụng mới hay hiện hữu qua CIF",
        result=check_internal_system("CIF"),
        reason_if_incomplete="Cần đối chiếu CIF/lịch sử quan hệ tín dụng tại MSB — hồ sơ tải lên không đủ căn cứ.",
    )


def evaluate_operating_status(documents: list[ExtractedDocument]) -> ConditionRow:
    # Simplification (documented, not hidden): this reads only the status
    # keyword stated in the uploaded documents themselves, not a live query
    # against the authoritative national business registry — a dissolution
    # or suspension notice found in the documents is treated as reliable
    # negative evidence; an "đang hoạt động" claim is treated as the best
    # available signal, not a live-verified fact.
    matches = find_all_matches(documents, _STATUS_PATTERN)
    if not matches:
        observed = EvidencedField(
            field_id="operating_status", label="Tình trạng hoạt động", value=None,
            unit=None, period=None, status="MISSING_DATA",
        )
        return ConditionRow(
            condition_id="C05", condition_name="Tình trạng hoạt động", observed=observed,
            compare_rule="Phải đang hoạt động (không tạm ngừng/giải thể)",
            result="INSUFFICIENT_DATA",
            reason_if_incomplete="Không tìm thấy công bố tình trạng hoạt động trong hồ sơ.",
        )
    distinct = {v for _, v in matches}
    refs = [ref for ref, _ in matches]
    if len(distinct) > 1:
        observed = EvidencedField(
            field_id="operating_status", label="Tình trạng hoạt động", value=None,
            unit=None, period=None, status="PENDING_REVIEW", evidence=refs,
        )
        return ConditionRow(
            condition_id="C05", condition_name="Tình trạng hoạt động", observed=observed,
            compare_rule="Phải đang hoạt động (không tạm ngừng/giải thể)",
            result="INSUFFICIENT_DATA",
            reason_if_incomplete="Các nguồn công bố tình trạng hoạt động mâu thuẫn nhau.",
        )
    status_text = matches[0][1]
    observed = EvidencedField(
        field_id="operating_status", label="Tình trạng hoạt động", value=status_text,
        unit=None, period=None, status="COMPUTED", evidence=refs,
    )
    is_active = status_text == "dang hoat dong"
    return ConditionRow(
        condition_id="C05", condition_name="Tình trạng hoạt động", observed=observed,
        compare_rule="Phải đang hoạt động (không tạm ngừng/giải thể)",
        result="PASS" if is_active else "FAIL",
    )
```

```python
# app/agents/eb/overview/credit_history.py
from app.agents.eb.internal_systems import check_internal_system
from app.engine.core.types import ConditionRow, EvidencedField


def evaluate_credit_history() -> ConditionRow:
    observed = EvidencedField(
        field_id="credit_history", label="Lịch sử quan hệ tín dụng", value=None,
        unit=None, period=None, status="MISSING_DATA",
    )
    return ConditionRow(
        condition_id="C11", condition_name="Lịch sử quan hệ tín dụng", observed=observed,
        compare_rule="Không nợ nhóm 2/chậm trả ≥10 ngày trong 12 tháng; không nợ xấu trong 36 tháng",
        result=check_internal_system("CIC"),
        reason_if_incomplete="Cần dữ liệu CIC và lịch sử tại MSB — không thể kết luận chỉ từ hồ sơ tải lên.",
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/usr/local/bin/python -m pytest tests/agents/eb/overview -v`
Expected: PASS (all, including Task 8's tests)

- [ ] **Step 5: Commit**

```bash
git add app/agents/eb/overview/customer_status.py app/agents/eb/overview/credit_history.py \
        tests/agents/eb/overview/test_customer_status.py tests/agents/eb/overview/test_credit_history.py
git commit -m "feat: add internal-system-gated EB overview conditions"
```

---

## Task 10: Revenue conditions (Doanh thu 12 tháng, Doanh thu 6 tháng qua TKTT)

**Files:**
- Create: `app/agents/eb/overview/revenue.py`
- Test: `tests/agents/eb/overview/test_revenue.py`

**Interfaces:**
- Consumes: `build_numeric_condition` (Task 8), `parse_statement_documents` (`app/agents/crosssell/statement_parser.py`, existing).
- Produces: `evaluate_revenue_12m(documents) -> ConditionRow` (`"C02"`), `evaluate_revenue_6m_statement(documents) -> ConditionRow` (`"C03"`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/agents/eb/overview/test_revenue.py
from app.agents.eb.overview.revenue import evaluate_revenue_12m, evaluate_revenue_6m_statement
from app.extraction.types import ExtractedDocument, ExtractedTable


def _pdf(text: str):
    doc = ExtractedDocument(
        filename="bctc.pdf", doc_type="pdf", text=text, tables=[],
        extraction_method="text_layer", confidence=1.0,
    )
    doc.file_id = "bctc.pdf"
    doc.pages = [text]
    return doc


def test_revenue_12m_pass_within_range():
    row = evaluate_revenue_12m([_pdf("Doanh thu thuan: 50.000.000.000")])
    assert row.result == "PASS"
    assert row.observed.value == 50_000_000_000


def test_revenue_12m_fail_below_minimum():
    row = evaluate_revenue_12m([_pdf("Doanh thu thuan: 5.000.000.000")])
    assert row.result == "FAIL"


def test_revenue_12m_fail_at_or_above_maximum():
    row = evaluate_revenue_12m([_pdf("Doanh thu thuan: 1.000.000.000.000")])
    assert row.result == "FAIL"


def test_revenue_12m_insufficient_data_without_match():
    row = evaluate_revenue_12m([_pdf("khong co gi")])
    assert row.result == "INSUFFICIENT_DATA"


def _statement_doc(rows, filename="sao_ke.xlsx"):
    doc = ExtractedDocument(
        filename=filename, doc_type="xlsx", text="", tables=[
            ExtractedTable(rows=rows, sheet_or_page="Sheet1")
        ], extraction_method="spreadsheet", confidence=1.0,
    )
    doc.file_id = filename
    return doc


def test_revenue_6m_statement_insufficient_data_without_statement():
    row = evaluate_revenue_6m_statement([_pdf("khong lien quan")])
    assert row.result == "INSUFFICIENT_DATA"
    assert row.observed.value is None


def test_revenue_6m_statement_insufficient_data_even_with_statement():
    # We can sum credit turnover but cannot verify it's exactly the trailing
    # 6-month window from a raw date string — must not claim PASS/FAIL on an
    # unverified window (spec: "tính đúng cửa sổ 6/12/36 tháng").
    header = ["Ngay", "So but toan", "Ghi No", "Ghi Co", "Dien giai", "Doi tac", "TK doi tac", "NH doi tac", "Loai tien", "Nguon"]
    row1 = ["01/01/2026", "1", "0", "100000000", "thu tien hang", "Cong ty A", "", "", "VND", ""]
    doc = _statement_doc([header, row1])
    row = evaluate_revenue_6m_statement([doc])
    assert row.result == "INSUFFICIENT_DATA"
    assert row.observed.value == 100_000_000  # data is shown even though window can't be verified
    assert row.observed.status == "COMPUTED"
    assert row.reason_if_incomplete is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/local/bin/python -m pytest tests/agents/eb/overview/test_revenue.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

```python
# app/agents/eb/overview/revenue.py
import re

from app.agents.crosssell.statement_parser import parse_statement_documents
from app.agents.eb.policy_config import POLICY_CONFIG
from app.engine.core.types import ConditionRow, EvidencedField
from app.extraction.types import ExtractedDocument

from ._common import build_numeric_condition

_REVENUE_PATTERN = re.compile(r"doanh thu thuan[:\s]*(-?[\d.,]+)")


def evaluate_revenue_12m(documents: list[ExtractedDocument]) -> ConditionRow:
    min_v = POLICY_CONFIG["REVENUE_12M_MIN_VND"].value
    max_v = POLICY_CONFIG["REVENUE_12M_MAX_VND"].value
    return build_numeric_condition(
        condition_id="C02", condition_name="Doanh thu 12 tháng gần nhất",
        field_id="revenue_12m_vnd", documents=documents, pattern=_REVENUE_PATTERN,
        compare_rule_text=f"≥ {min_v:,.0f} và < {max_v:,.0f} VND",
        evaluate_fn=lambda v: min_v <= v < max_v,
    )


def evaluate_revenue_6m_statement(documents: list[ExtractedDocument]) -> ConditionRow:
    total_credit = 0.0
    evidence = []
    for doc in documents:
        txns = parse_statement_documents([doc])
        if not txns:
            continue
        doc_credit = sum(t.credit for t in txns)
        total_credit += doc_credit
        file_id = getattr(doc, "file_id", doc.filename)
        from app.engine.core.types import EvidenceRef
        evidence.append(EvidenceRef(
            file_id=file_id, filename=doc.filename,
            location=f"Toàn bộ sao kê ({len(txns)} giao dịch)",
            original_text=f"Tổng ghi Có: {doc_credit:,.0f} VND",
        ))
    compare_rule = "Tổng ghi Có/giao dịch đủ điều kiện trong 6 tháng gần nhất"
    if not evidence:
        observed = EvidencedField(
            field_id="revenue_6m_statement_vnd", label="Doanh thu 6 tháng gần nhất qua TKTT",
            value=None, unit="VND", period=None, status="MISSING_DATA",
        )
        return ConditionRow(
            condition_id="C03", condition_name="Doanh thu 6 tháng gần nhất qua TKTT",
            observed=observed, compare_rule=compare_rule, result="INSUFFICIENT_DATA",
            reason_if_incomplete="Không tìm thấy sao kê tài khoản thanh toán trong hồ sơ.",
        )
    observed = EvidencedField(
        field_id="revenue_6m_statement_vnd", label="Doanh thu 6 tháng gần nhất qua TKTT",
        value=round(total_credit, 2), unit="VND",
        period="Toàn bộ sao kê tải lên (chưa xác định chính xác cửa sổ 6 tháng)",
        status="COMPUTED", evidence=evidence,
    )
    return ConditionRow(
        condition_id="C03", condition_name="Doanh thu 6 tháng gần nhất qua TKTT",
        observed=observed, compare_rule=compare_rule, result="INSUFFICIENT_DATA",
        reason_if_incomplete=(
            "Có dữ liệu sao kê nhưng chưa xác định được chính xác cửa sổ 6 tháng gần nhất "
            "từ ngày giao dịch — cần cán bộ xác nhận kỳ trước khi kết luận Đạt/Không đạt."
        ),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/usr/local/bin/python -m pytest tests/agents/eb/overview/test_revenue.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add app/agents/eb/overview/revenue.py tests/agents/eb/overview/test_revenue.py
git commit -m "feat: add EB revenue overview conditions (12m BCTC, 6m statement)"
```

---

## Task 11: Equity/profit conditions (Vốn chủ sở hữu, LNST theo PAKD, Lợi nhuận gộp trừ lãi vay)

**Files:**
- Create: `app/agents/eb/overview/equity_profit.py`
- Test: `tests/agents/eb/overview/test_equity_profit.py`

**Interfaces:**
- Consumes: `build_numeric_condition` (Task 8), `find_all_matches` (Task 2).
- Produces: `evaluate_equity(documents) -> ConditionRow` (`"C08"`), `evaluate_lnst_pakd(documents) -> ConditionRow` (`"C09"`), `evaluate_gross_profit_less_interest(documents) -> ConditionRow` (`"C10"`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/agents/eb/overview/test_equity_profit.py
from app.agents.eb.overview.equity_profit import (
    evaluate_equity, evaluate_gross_profit_less_interest, evaluate_lnst_pakd,
)
from app.extraction.types import ExtractedDocument


def _doc(text: str, filename="doc.pdf"):
    doc = ExtractedDocument(
        filename=filename, doc_type="pdf", text=text, tables=[],
        extraction_method="text_layer", confidence=1.0,
    )
    doc.file_id = filename
    doc.pages = [text]
    return doc


def test_equity_pass_when_positive():
    row = evaluate_equity([_doc("Von chu so huu: 500.000.000")])
    assert row.result == "PASS"


def test_equity_fail_when_non_positive():
    row = evaluate_equity([_doc("Von chu so huu: 0")])
    assert row.result == "FAIL"


def test_lnst_pakd_pass_when_positive():
    row = evaluate_lnst_pakd([_doc("LNST theo PAKD: 200.000.000")])
    assert row.result == "PASS"


def test_lnst_pakd_insufficient_without_match():
    row = evaluate_lnst_pakd([_doc("khong co gi")])
    assert row.result == "INSUFFICIENT_DATA"


def test_gross_profit_less_interest_computed_and_passes():
    doc = _doc("Loi nhuan gop: 1.000.000.000\nChi phi lai vay: 300.000.000")
    row = evaluate_gross_profit_less_interest([doc])
    assert row.result == "PASS"
    assert row.observed.value == 700_000_000
    assert row.observed.formula == "loi_nhuan_gop - chi_phi_lai_vay"


def test_gross_profit_less_interest_fails_when_negative():
    doc = _doc("Loi nhuan gop: 100.000.000\nChi phi lai vay: 300.000.000")
    row = evaluate_gross_profit_less_interest([doc])
    assert row.result == "FAIL"


def test_gross_profit_less_interest_insufficient_when_either_missing():
    row = evaluate_gross_profit_less_interest([_doc("Loi nhuan gop: 100.000.000")])
    assert row.result == "INSUFFICIENT_DATA"
    assert "lãi vay" in row.reason_if_incomplete
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/local/bin/python -m pytest tests/agents/eb/overview/test_equity_profit.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

```python
# app/agents/eb/overview/equity_profit.py
import re

from app.engine.core.numbers import parse_vn_number
from app.engine.core.types import ConditionRow, EvidencedField
from app.extraction.evidence_search import find_all_matches
from app.extraction.types import ExtractedDocument

from ._common import build_numeric_condition

_EQUITY_PATTERN = re.compile(r"von chu so huu[:\s]*(-?[\d.,]+)")
_LNST_PAKD_PATTERN = re.compile(r"lnst (?:theo )?pakd[:\s]*(-?[\d.,]+)")
_GROSS_PROFIT_PATTERN = re.compile(r"loi nhuan gop[:\s]*(-?[\d.,]+)")
_INTEREST_EXPENSE_PATTERN = re.compile(r"chi phi lai vay[:\s]*(-?[\d.,]+)")


def evaluate_equity(documents: list[ExtractedDocument]) -> ConditionRow:
    return build_numeric_condition(
        condition_id="C08", condition_name="Vốn chủ sở hữu", field_id="equity_vnd",
        documents=documents, pattern=_EQUITY_PATTERN, compare_rule_text="> 0",
        evaluate_fn=lambda v: v > 0,
    )


def evaluate_lnst_pakd(documents: list[ExtractedDocument]) -> ConditionRow:
    return build_numeric_condition(
        condition_id="C09", condition_name="LNST theo PAKD", field_id="lnst_pakd_vnd",
        documents=documents, pattern=_LNST_PAKD_PATTERN, compare_rule_text="> 0",
        evaluate_fn=lambda v: v > 0,
    )


def evaluate_gross_profit_less_interest(documents: list[ExtractedDocument]) -> ConditionRow:
    gross_matches = find_all_matches(documents, _GROSS_PROFIT_PATTERN)
    interest_matches = find_all_matches(documents, _INTEREST_EXPENSE_PATTERN)
    compare_rule = "> 0"
    if not gross_matches or not interest_matches:
        missing = []
        if not gross_matches:
            missing.append("lợi nhuận gộp")
        if not interest_matches:
            missing.append("chi phí lãi vay")
        observed = EvidencedField(
            field_id="gross_profit_less_interest_vnd", label="Lợi nhuận gộp trừ lãi vay",
            value=None, unit="VND", period=None, status="MISSING_DATA",
        )
        return ConditionRow(
            condition_id="C10", condition_name="Lợi nhuận gộp trừ lãi vay", observed=observed,
            compare_rule=compare_rule, result="INSUFFICIENT_DATA",
            reason_if_incomplete=f"Thiếu {', '.join(missing)} trong hồ sơ.",
        )

    gross_distinct = {round(parse_vn_number(r), 6) for _, r in gross_matches}
    interest_distinct = {round(parse_vn_number(r), 6) for _, r in interest_matches}
    refs = [ref for ref, _ in gross_matches] + [ref for ref, _ in interest_matches]
    if len(gross_distinct) > 1 or len(interest_distinct) > 1:
        observed = EvidencedField(
            field_id="gross_profit_less_interest_vnd", label="Lợi nhuận gộp trừ lãi vay",
            value=None, unit="VND", period=None, status="PENDING_REVIEW", evidence=refs,
        )
        return ConditionRow(
            condition_id="C10", condition_name="Lợi nhuận gộp trừ lãi vay", observed=observed,
            compare_rule=compare_rule, result="INSUFFICIENT_DATA",
            reason_if_incomplete="Các nguồn cho giá trị lợi nhuận gộp hoặc chi phí lãi vay khác nhau.",
        )

    gross = parse_vn_number(gross_matches[0][1])
    interest = parse_vn_number(interest_matches[0][1])
    value = gross - interest
    observed = EvidencedField(
        field_id="gross_profit_less_interest_vnd", label="Lợi nhuận gộp trừ lãi vay",
        value=value, unit="VND", period=None, status="COMPUTED", evidence=refs,
        formula="loi_nhuan_gop - chi_phi_lai_vay",
        input_fields=["gross_profit_vnd", "interest_expense_vnd"],
    )
    return ConditionRow(
        condition_id="C10", condition_name="Lợi nhuận gộp trừ lãi vay", observed=observed,
        compare_rule=compare_rule, result="PASS" if value > 0 else "FAIL",
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/usr/local/bin/python -m pytest tests/agents/eb/overview/test_equity_profit.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add app/agents/eb/overview/equity_profit.py tests/agents/eb/overview/test_equity_profit.py
git commit -m "feat: add EB equity/profit overview conditions"
```

---

## Task 12: Operating-history condition (Số năm hoạt động)

**Files:**
- Create: `app/agents/eb/overview/operating_history.py`
- Test: `tests/agents/eb/overview/test_operating_history.py`

**Interfaces:**
- Produces: `evaluate_operating_history(documents, today: date | None = None) -> ConditionRow` (`"C07"`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/agents/eb/overview/test_operating_history.py
from datetime import date

from app.agents.eb.overview.operating_history import evaluate_operating_history
from app.extraction.types import ExtractedDocument


def _doc(text: str):
    doc = ExtractedDocument(
        filename="dkkd.pdf", doc_type="pdf", text=text, tables=[],
        extraction_method="text_layer", confidence=1.0,
    )
    doc.file_id = "dkkd.pdf"
    doc.pages = [text]
    return doc


def test_pass_when_operating_at_least_24_months():
    row = evaluate_operating_history([_doc("Ngay thanh lap: 01/01/2023")], today=date(2026, 1, 1))
    assert row.result == "PASS"
    assert row.observed.value == 36


def test_fail_when_operating_less_than_24_months():
    row = evaluate_operating_history([_doc("Ngay thanh lap: 01/01/2025")], today=date(2026, 1, 1))
    assert row.result == "FAIL"
    assert row.observed.value == 12


def test_insufficient_data_without_a_date():
    row = evaluate_operating_history([_doc("khong co ngay thanh lap")], today=date(2026, 1, 1))
    assert row.result == "INSUFFICIENT_DATA"


def test_insufficient_data_on_conflicting_dates():
    doc1 = _doc("Ngay thanh lap: 01/01/2020")
    doc2_text = "Ngay thanh lap: 01/01/2022"
    doc2 = ExtractedDocument(filename="b.pdf", doc_type="pdf", text=doc2_text, tables=[], extraction_method="text_layer", confidence=1.0)
    doc2.file_id = "b.pdf"
    doc2.pages = [doc2_text]
    row = evaluate_operating_history([doc1, doc2], today=date(2026, 1, 1))
    assert row.result == "INSUFFICIENT_DATA"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/local/bin/python -m pytest tests/agents/eb/overview/test_operating_history.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

```python
# app/agents/eb/overview/operating_history.py
import re
from datetime import date

from app.agents.eb.policy_config import POLICY_CONFIG
from app.engine.core.types import ConditionRow, EvidencedField
from app.extraction.evidence_search import find_all_matches
from app.extraction.types import ExtractedDocument

_DATE_PATTERN = re.compile(r"ngay thanh lap[:\s]*(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4})")


def _parse_vn_date(raw: str) -> date | None:
    for sep in ("/", "-", "."):
        if sep in raw:
            parts = raw.split(sep)
            if len(parts) == 3:
                try:
                    d, m, y = int(parts[0]), int(parts[1]), int(parts[2])
                    if y < 100:
                        y += 2000
                    return date(y, m, d)
                except ValueError:
                    return None
    return None


def evaluate_operating_history(
    documents: list[ExtractedDocument], today: date | None = None
) -> ConditionRow:
    today = today or date.today()
    threshold = POLICY_CONFIG["MIN_OPERATING_MONTHS"].value
    compare_rule = f"≥ {threshold} tháng"
    matches = find_all_matches(documents, _DATE_PATTERN)
    if not matches:
        observed = EvidencedField(
            field_id="operating_months", label="Số năm hoạt động", value=None,
            unit="tháng", period=None, status="MISSING_DATA",
        )
        return ConditionRow(
            condition_id="C07", condition_name="Số năm hoạt động", observed=observed,
            compare_rule=compare_rule, result="INSUFFICIENT_DATA",
            reason_if_incomplete="Không tìm thấy ngày thành lập trong hồ sơ.",
        )

    parsed_dates = {_parse_vn_date(raw) for _, raw in matches}
    parsed_dates.discard(None)
    refs = [ref for ref, _ in matches]
    if len(parsed_dates) != 1:
        observed = EvidencedField(
            field_id="operating_months", label="Số năm hoạt động", value=None,
            unit="tháng", period=None, status="PENDING_REVIEW", evidence=refs,
        )
        return ConditionRow(
            condition_id="C07", condition_name="Số năm hoạt động", observed=observed,
            compare_rule=compare_rule, result="INSUFFICIENT_DATA",
            reason_if_incomplete="Không xác định được một ngày thành lập duy nhất, đáng tin cậy từ hồ sơ.",
        )

    start_date = next(iter(parsed_dates))
    months = (today.year - start_date.year) * 12 + (today.month - start_date.month)
    observed = EvidencedField(
        field_id="operating_months", label="Số năm hoạt động", value=months,
        unit="tháng", period=None, status="COMPUTED", evidence=refs,
        policy_version=POLICY_CONFIG["MIN_OPERATING_MONTHS"].policy_version_label,
    )
    return ConditionRow(
        condition_id="C07", condition_name="Số năm hoạt động", observed=observed,
        compare_rule=compare_rule, result="PASS" if months >= threshold else "FAIL",
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/usr/local/bin/python -m pytest tests/agents/eb/overview/test_operating_history.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add app/agents/eb/overview/operating_history.py tests/agents/eb/overview/test_operating_history.py
git commit -m "feat: add EB operating-history overview condition"
```

---

## Task 13: Industry condition (Ngành nghề + danh sách cấm)

**Files:**
- Create: `app/agents/eb/overview/industry.py`
- Test: `tests/agents/eb/overview/test_industry.py`

**Interfaces:**
- Produces: `evaluate_industry(documents) -> ConditionRow` (`"C04"`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/agents/eb/overview/test_industry.py
from app.agents.eb.overview.industry import evaluate_industry
from app.extraction.types import ExtractedDocument


def _doc(text: str):
    doc = ExtractedDocument(
        filename="dkkd.pdf", doc_type="pdf", text=text, tables=[],
        extraction_method="text_layer", confidence=1.0,
    )
    doc.file_id = "dkkd.pdf"
    doc.pages = [text]
    return doc


def test_insufficient_data_when_prohibited_list_not_loaded():
    # POLICY_CONFIG["PROHIBITED_INDUSTRIES"] starts empty — even a clearly
    # stated industry cannot be cleared as "not prohibited" without a real list.
    row = evaluate_industry([_doc("Nganh nghe kinh doanh: Ban le hang tieu dung")])
    assert row.result == "INSUFFICIENT_DATA"
    assert row.observed.value == "Ban le hang tieu dung"
    assert row.observed.status == "COMPUTED"


def test_insufficient_data_without_any_industry_text():
    row = evaluate_industry([_doc("khong co thong tin nganh")])
    assert row.result == "INSUFFICIENT_DATA"
    assert row.observed.value is None


def test_fail_when_list_loaded_and_industry_matches(monkeypatch):
    from app.agents.eb import policy_config

    monkeypatch.setitem(
        policy_config.POLICY_CONFIG, "PROHIBITED_INDUSTRIES",
        policy_config.PolicyThreshold(["ca do", "vu khi"]),
    )
    row = evaluate_industry([_doc("Nganh nghe kinh doanh: Ca do trực tuyến")])
    assert row.result == "FAIL"


def test_pass_when_list_loaded_and_industry_does_not_match(monkeypatch):
    from app.agents.eb import policy_config

    monkeypatch.setitem(
        policy_config.POLICY_CONFIG, "PROHIBITED_INDUSTRIES",
        policy_config.PolicyThreshold(["ca do", "vu khi"]),
    )
    row = evaluate_industry([_doc("Nganh nghe kinh doanh: Ban le hang tieu dung")])
    assert row.result == "PASS"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/local/bin/python -m pytest tests/agents/eb/overview/test_industry.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

```python
# app/agents/eb/overview/industry.py
import re
import unicodedata

from app.agents.eb.policy_config import POLICY_CONFIG
from app.engine.core.types import ConditionRow, EvidencedField
from app.extraction.evidence_search import find_all_matches
from app.extraction.types import ExtractedDocument

_INDUSTRY_PATTERN = re.compile(r"nganh nghe(?: kinh doanh)?[:\s]*([^\n]+)")


def _strip_accents_lower(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(c for c in normalized if not unicodedata.combining(c))
    return ascii_text.lower()


def evaluate_industry(documents: list[ExtractedDocument]) -> ConditionRow:
    compare_rule = "Không thuộc danh sách ngành cấm/loại trừ của MSB"
    matches = find_all_matches(documents, _INDUSTRY_PATTERN)
    if not matches:
        observed = EvidencedField(
            field_id="industry", label="Ngành nghề", value=None, unit=None,
            period=None, status="MISSING_DATA",
        )
        return ConditionRow(
            condition_id="C04", condition_name="Ngành nghề", observed=observed,
            compare_rule=compare_rule, result="INSUFFICIENT_DATA",
            reason_if_incomplete="Không tìm thấy ngành nghề đăng ký trong hồ sơ.",
        )

    ref, raw_value = matches[0]
    industry_name = raw_value.strip()
    threshold = POLICY_CONFIG["PROHIBITED_INDUSTRIES"]
    observed = EvidencedField(
        field_id="industry", label="Ngành nghề", value=industry_name, unit=None,
        period=None, status="COMPUTED", evidence=[ref],
        policy_version=threshold.policy_version_label,
    )
    prohibited = threshold.value
    if not prohibited:
        return ConditionRow(
            condition_id="C04", condition_name="Ngành nghề", observed=observed,
            compare_rule=compare_rule, result="INSUFFICIENT_DATA",
            reason_if_incomplete=(
                "Chưa nạp danh sách ngành cấm/loại trừ có kiểm soát phiên bản — không thể kết luận."
            ),
        )
    haystack = _strip_accents_lower(industry_name)
    is_prohibited = any(_strip_accents_lower(p) in haystack for p in prohibited)
    return ConditionRow(
        condition_id="C04", condition_name="Ngành nghề", observed=observed,
        compare_rule=compare_rule, result="FAIL" if is_prohibited else "PASS",
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/usr/local/bin/python -m pytest tests/agents/eb/overview/test_industry.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add app/agents/eb/overview/industry.py tests/agents/eb/overview/test_industry.py
git commit -m "feat: add EB industry overview condition"
```

---

## Task 14: Top-partners condition (03/05 đối tác — unresolved policy reading)

**Files:**
- Create: `app/agents/eb/overview/partners.py`
- Test: `tests/agents/eb/overview/test_partners.py`

**Interfaces:**
- Consumes: `parse_statement_documents`, `is_excluded_from_partner_ranking` (`app/agents/crosssell/statement_parser.py`, `rule2_partners.py`, existing).
- Produces: `evaluate_top_partners(documents) -> ConditionRow` (`"C06"`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/agents/eb/overview/test_partners.py
from app.agents.eb.overview.partners import evaluate_top_partners
from app.extraction.types import ExtractedDocument, ExtractedTable


def _statement_doc(rows, filename="so_chi_tiet.xlsx"):
    doc = ExtractedDocument(
        filename=filename, doc_type="xlsx", text="", tables=[
            ExtractedTable(rows=rows, sheet_or_page="Sheet1")
        ], extraction_method="spreadsheet", confidence=1.0,
    )
    doc.file_id = filename
    return doc


HEADER = ["Ngay", "So but toan", "Ghi No", "Ghi Co", "Dien giai", "Doi tac", "TK doi tac", "NH doi tac", "Loai tien", "Nguon"]


def test_insufficient_data_without_any_partner_records():
    row = evaluate_top_partners([])
    assert row.result == "INSUFFICIENT_DATA"
    assert row.observed.value is None


def test_insufficient_data_even_with_partner_data_due_to_open_policy_question():
    rows = [
        HEADER,
        ["01/01/2026", "1", "0", "100000000", "thu tien", "Cong ty A", "", "", "VND", ""],
        ["02/01/2026", "2", "50000000", "0", "tra tien", "Cong ty B", "", "", "VND", ""],
    ]
    row = evaluate_top_partners([_statement_doc(rows)])
    assert row.result == "INSUFFICIENT_DATA"
    assert row.observed.status == "COMPUTED"
    assert "Cong ty A" in str(row.observed.value) or "1" in str(row.observed.value)
    assert row.reason_if_incomplete is not None
    assert "đầu ra" in row.reason_if_incomplete or "đầu vào" in row.reason_if_incomplete
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/local/bin/python -m pytest tests/agents/eb/overview/test_partners.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

```python
# app/agents/eb/overview/partners.py
from app.agents.crosssell.rule2_partners import is_excluded_from_partner_ranking
from app.agents.crosssell.statement_parser import parse_statement_documents
from app.agents.eb.policy_config import POLICY_CONFIG
from app.engine.core.types import ConditionRow, EvidencedField, EvidenceRef
from app.extraction.types import ExtractedDocument


def evaluate_top_partners(documents: list[ExtractedDocument]) -> ConditionRow:
    compare_rule = "≥ 03/05 đối tác đầu ra/đầu vào có hoạt động/hóa đơn trong 6 tháng"
    outbound_partners: set[str] = set()  # đầu ra: partner paid us (credit)
    inbound_partners: set[str] = set()   # đầu vào: we paid partner (debit)
    evidence: list[EvidenceRef] = []

    for doc in documents:
        txns = parse_statement_documents([doc])
        if not txns:
            continue
        for t in txns:
            if is_excluded_from_partner_ranking(t) or not t.partner.strip():
                continue
            if t.credit > 0:
                outbound_partners.add(t.partner)
            if t.debit > 0:
                inbound_partners.add(t.partner)
        if outbound_partners or inbound_partners:
            file_id = getattr(doc, "file_id", doc.filename)
            evidence.append(EvidenceRef(
                file_id=file_id, filename=doc.filename,
                location=f"Toàn bộ sổ chi tiết ({len(txns)} giao dịch)",
                original_text=f"Đầu ra: {len(outbound_partners)} đối tác, Đầu vào: {len(inbound_partners)} đối tác",
            ))

    if not evidence:
        observed = EvidencedField(
            field_id="top_partners_count", label="03/05 đối tác đầu ra, đầu vào lớn nhất",
            value=None, unit=None, period=None, status="MISSING_DATA",
        )
        return ConditionRow(
            condition_id="C06", condition_name="03/05 đối tác đầu ra, đầu vào lớn nhất",
            observed=observed, compare_rule=compare_rule, result="INSUFFICIENT_DATA",
            reason_if_incomplete="Không tìm thấy sổ chi tiết bán/mua hàng hoặc sao kê trong hồ sơ.",
        )

    threshold = POLICY_CONFIG["TOP_PARTNERS_COUNT"]
    observed = EvidencedField(
        field_id="top_partners_count", label="03/05 đối tác đầu ra, đầu vào lớn nhất",
        value=f"Đầu ra: {len(outbound_partners)} đối tác, Đầu vào: {len(inbound_partners)} đối tác",
        unit=None, period=None, status="COMPUTED", evidence=evidence,
        policy_version=threshold.policy_version_label,
    )
    return ConditionRow(
        condition_id="C06", condition_name="03/05 đối tác đầu ra, đầu vào lớn nhất",
        observed=observed, compare_rule=compare_rule, result="INSUFFICIENT_DATA",
        reason_if_incomplete=threshold.open_question,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/usr/local/bin/python -m pytest tests/agents/eb/overview/test_partners.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add app/agents/eb/overview/partners.py tests/agents/eb/overview/test_partners.py
git commit -m "feat: add EB top-partners overview condition with open policy question"
```

---

## Task 15: Overview aggregator + summary

**Files:**
- Modify: `app/agents/eb/overview/__init__.py`
- Test: `tests/agents/eb/overview/test_init.py`

**Interfaces:**
- Consumes: every `evaluate_*` function from Tasks 9–14.
- Produces: `evaluate_overview(documents: list[ExtractedDocument]) -> tuple[list[ConditionRow], dict]` — the summary dict has keys `checked, total, passed, failed, pending`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/agents/eb/overview/test_init.py
from app.agents.eb.overview import evaluate_overview
from app.extraction.types import ExtractedDocument


def _doc(text: str, filename="doc.pdf"):
    doc = ExtractedDocument(
        filename=filename, doc_type="pdf", text=text, tables=[],
        extraction_method="text_layer", confidence=1.0,
    )
    doc.file_id = filename
    doc.pages = [text]
    return doc


def test_returns_eleven_condition_rows():
    rows, summary = evaluate_overview([_doc("khong co gi ca")])
    assert len(rows) == 11
    assert summary["total"] == 11


def test_summary_counts_pending_conditions_correctly():
    # Nothing computable in this bundle — every condition should land in
    # INSUFFICIENT_DATA/PENDING_INTERNAL_CHECK, none PASS/FAIL.
    rows, summary = evaluate_overview([_doc("khong co gi ca")])
    assert summary["checked"] == 0
    assert summary["pending"] == 11


def test_summary_reflects_a_passing_condition():
    text = "Von chu so huu: 500.000.000\n"
    rows, summary = evaluate_overview([_doc(text)])
    equity_row = next(r for r in rows if r.condition_id == "C08")
    assert equity_row.result == "PASS"
    assert summary["passed"] >= 1
    assert summary["checked"] >= 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/local/bin/python -m pytest tests/agents/eb/overview/test_init.py -v`
Expected: FAIL — `ImportError: cannot import name 'evaluate_overview'`

- [ ] **Step 3: Implement**

```python
# app/agents/eb/overview/__init__.py
from app.engine.core.types import ConditionRow
from app.extraction.types import ExtractedDocument

from .credit_history import evaluate_credit_history
from .customer_status import evaluate_customer_segment, evaluate_operating_status
from .equity_profit import evaluate_equity, evaluate_gross_profit_less_interest, evaluate_lnst_pakd
from .industry import evaluate_industry
from .operating_history import evaluate_operating_history
from .partners import evaluate_top_partners
from .revenue import evaluate_revenue_12m, evaluate_revenue_6m_statement


def evaluate_overview(documents: list[ExtractedDocument]) -> tuple[list[ConditionRow], dict]:
    rows = [
        evaluate_customer_segment(),
        evaluate_revenue_12m(documents),
        evaluate_revenue_6m_statement(documents),
        evaluate_industry(documents),
        evaluate_operating_status(documents),
        evaluate_top_partners(documents),
        evaluate_operating_history(documents),
        evaluate_equity(documents),
        evaluate_lnst_pakd(documents),
        evaluate_gross_profit_less_interest(documents),
        evaluate_credit_history(),
    ]
    passed = sum(1 for r in rows if r.result == "PASS")
    failed = sum(1 for r in rows if r.result == "FAIL")
    pending = sum(1 for r in rows if r.result in ("INSUFFICIENT_DATA", "PENDING_INTERNAL_CHECK"))
    summary = {
        "checked": passed + failed, "total": len(rows),
        "passed": passed, "failed": failed, "pending": pending,
    }
    return rows, summary
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/usr/local/bin/python -m pytest tests/agents/eb/overview -v`
Expected: PASS (all — full overview test suite)

- [ ] **Step 5: Run full suite and commit**

Run: `/usr/local/bin/python -m pytest -q`

```bash
git add app/agents/eb/overview/__init__.py tests/agents/eb/overview/test_init.py
git commit -m "feat: add EB overview aggregator with X/Y summary"
```

---

## Task 16: 4th metric card — Tỷ lệ tài trợ hợp đồng đầu ra

**Files:**
- Create: `app/agents/eb/contract_financing.py`
- Test: `tests/agents/eb/test_contract_financing.py`

**Interfaces:**
- Consumes: `QD_EB_039_RATES` (`app/agents/crosssell/qd_eb_039.py`, existing).
- Produces: `compute_output_contract_financing_ratio(proposed_limit_vnd, eligible_contract_value_vnd, method=None) -> Metric`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/agents/eb/test_contract_financing.py
from app.agents.eb.contract_financing import compute_output_contract_financing_ratio


def test_computes_ratio_as_percentage():
    m = compute_output_contract_financing_ratio(800_000_000, 1_000_000_000)
    assert m.value == 80.0
    assert m.status == "OK"


def test_missing_either_input_is_need_more_data():
    assert compute_output_contract_financing_ratio(None, 1_000_000_000).status == "NEED_MORE_DATA"
    assert compute_output_contract_financing_ratio(800_000_000, None).status == "NEED_MORE_DATA"
    assert compute_output_contract_financing_ratio(800_000_000, 0).status == "NEED_MORE_DATA"


def test_no_policy_label_without_a_recognised_method():
    m = compute_output_contract_financing_ratio(800_000_000, 1_000_000_000)
    assert m.policy_version is None


def test_qd_eb_039_label_attached_for_recognised_method():
    m = compute_output_contract_financing_ratio(800_000_000, 1_000_000_000, method="lc_or_bltt")
    assert "QĐ.EB.039" in m.policy_version


def test_unrecognised_method_does_not_attach_label():
    m = compute_output_contract_financing_ratio(800_000_000, 1_000_000_000, method="khong_hop_le")
    assert m.policy_version is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/local/bin/python -m pytest tests/agents/eb/test_contract_financing.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

```python
# app/agents/eb/contract_financing.py
from app.agents.crosssell.qd_eb_039 import QD_EB_039_RATES
from app.engine.core.types import Metric


def compute_output_contract_financing_ratio(
    proposed_limit_vnd: float | None,
    eligible_contract_value_vnd: float | None,
    method: str | None = None,
) -> Metric:
    if (
        proposed_limit_vnd is None
        or eligible_contract_value_vnd is None
        or eligible_contract_value_vnd <= 0
    ):
        return Metric.need_more_data(
            "output_contract_financing_ratio",
            "han_muc_de_xuat / gia_tri_hop_dong_du_dieu_kien * 100%",
        )

    value = round(proposed_limit_vnd / eligible_contract_value_vnd * 100, 2)
    policy_version = None
    if method in QD_EB_039_RATES:
        max_rate = QD_EB_039_RATES[method] * 100
        policy_version = (
            f"QĐ.EB.039 (tỷ lệ tối đa demo theo phương thức '{method}': {max_rate:.0f}%, "
            "chưa xác nhận phạm vi áp dụng chính thức)"
        )
    return Metric(
        metric="output_contract_financing_ratio", value=value,
        formula="han_muc_de_xuat / gia_tri_hop_dong_du_dieu_kien * 100%",
        input_values={
            "proposed_limit_vnd": proposed_limit_vnd,
            "eligible_contract_value_vnd": eligible_contract_value_vnd,
        },
        input_sources={
            "proposed_limit_vnd": "manual_rm_input",
            "eligible_contract_value_vnd": "manual_rm_input",
        },
        policy_version=policy_version,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/usr/local/bin/python -m pytest tests/agents/eb/test_contract_financing.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add app/agents/eb/contract_financing.py tests/agents/eb/test_contract_financing.py
git commit -m "feat: add 4th EB metric card (output-contract financing ratio)"
```

---

## Task 17: Router wires overview, 4th metric, document status list, assessed_at

**Files:**
- Create: `app/agents/eb/document_status.py`
- Modify: `app/agents/eb/router.py`
- Test: `tests/agents/eb/test_document_status.py`
- Test: `tests/agents/eb/test_router.py` (add)

**Interfaces:**
- Consumes: `evaluate_overview` (Task 15), `compute_output_contract_financing_ratio` (Task 16).
- Produces: `build_document_status_list(documents, extraction_warnings, condition_rows, metrics) -> list[dict]`; router response gains `overview`, `overview_summary`, `documents`, `assessed_at` keys and 4 new optional form fields (`proposed_limit_vnd`, `eligible_contract_value_vnd`, `qd_eb_039_method`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/agents/eb/test_document_status.py
from app.agents.eb.document_status import build_document_status_list
from app.engine.core.types import ConditionRow, EvidencedField, EvidenceRef, Metric
from app.extraction.types import ExtractedDocument


def _doc(filename, file_id):
    doc = ExtractedDocument(
        filename=filename, doc_type="pdf", text="x", tables=[],
        extraction_method="text_layer", confidence=1.0,
    )
    doc.file_id = file_id
    return doc


def test_extraction_failure_is_khong_doc_duoc():
    statuses = build_document_status_list(
        documents=[], extraction_warnings=["broken.jpg: không đọc được nội dung file (bad format)"],
        condition_rows=[], metrics={},
    )
    assert statuses[0]["filename"] == "broken.jpg"
    assert statuses[0]["status"] == "KHÔNG_ĐỌC_ĐƯỢC"


def test_file_cited_by_computed_evidence_is_da_trich_xuat():
    doc = _doc("bctc.pdf", "f1")
    ref = EvidenceRef(file_id="f1", filename="bctc.pdf", location="Trang 1", original_text="x")
    field_ = EvidencedField(
        field_id="equity_vnd", label="Vốn chủ sở hữu", value=1, unit="VND",
        period=None, status="COMPUTED", evidence=[ref],
    )
    row = ConditionRow(condition_id="C08", condition_name="Vốn chủ sở hữu", observed=field_, compare_rule="> 0", result="PASS")
    statuses = build_document_status_list([doc], [], [row], {})
    assert statuses[0]["status"] == "ĐÃ_TRÍCH_XUẤT"
    assert statuses[0]["cited_field_count"] == 1


def test_file_cited_only_by_pending_review_metric_is_cho_xac_minh():
    doc = _doc("bctc.pdf", "f1")
    ref = EvidenceRef(file_id="f1", filename="bctc.pdf", location="Trang 1", original_text="x")
    metric = Metric(
        metric="nwc", value=None, formula="a-b", input_values={}, input_sources={},
        evidence={"current_assets_vnd": [ref]},
    )
    statuses = build_document_status_list([doc], [], [], {"nwc": metric})
    assert statuses[0]["status"] in ("ĐÃ_TRÍCH_XUẤT", "CHỜ_XÁC_MINH")


def test_uncited_extracted_file_is_da_tai_len():
    doc = _doc("khac.pdf", "f2")
    statuses = build_document_status_list([doc], [], [], {})
    assert statuses[0]["status"] == "ĐÃ_TẢI_LÊN"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/local/bin/python -m pytest tests/agents/eb/test_document_status.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

```python
# app/agents/eb/document_status.py
from app.engine.core.types import ConditionRow, Metric
from app.extraction.types import ExtractedDocument


def build_document_status_list(
    documents: list[ExtractedDocument],
    extraction_warnings: list[str],
    condition_rows: list[ConditionRow],
    metrics: dict[str, Metric],
) -> list[dict]:
    cited_ok: set[str] = set()
    cited_pending: set[str] = set()

    for row in condition_rows:
        target = cited_ok if row.observed.status in ("COMPUTED", "VERIFIED") else cited_pending
        for ref in row.observed.evidence:
            target.add(ref.file_id)

    for metric in metrics.values():
        for refs in metric.evidence.values():
            for ref in refs:
                cited_ok.add(ref.file_id)

    result: list[dict] = []
    for name in extraction_warnings:
        filename = name.split(":", 1)[0]
        result.append({"filename": filename, "status": "KHÔNG_ĐỌC_ĐƯỢC", "cited_field_count": 0, "warnings": [name]})

    for doc in documents:
        file_id = getattr(doc, "file_id", doc.filename)
        if file_id in cited_pending:
            status = "CHỜ_XÁC_MINH"
        elif file_id in cited_ok:
            status = "ĐÃ_TRÍCH_XUẤT"
        else:
            status = "ĐÃ_TẢI_LÊN"
        result.append({
            "filename": doc.filename, "doc_type": doc.doc_type, "status": status,
            "cited_field_count": sum(
                1 for r in condition_rows for ref in r.observed.evidence if ref.file_id == file_id
            ),
            "warnings": list(doc.warnings),
        })
    return result
```

Router changes in `app/agents/eb/router.py`:

```python
import datetime

from .contract_financing import compute_output_contract_financing_ratio
from .document_status import build_document_status_list
from .overview import evaluate_overview

...

@router.post("/assess")
async def assess(
    customer_name: str = Form(...),
    tax_id: str = Form(...),
    files: list[UploadFile] = File(...),
    proposed_limit_vnd: float | None = Form(default=None),
    eligible_contract_value_vnd: float | None = Form(default=None),
    qd_eb_039_method: str | None = Form(default=None),
) -> dict:
    assessed_at = datetime.datetime.now(datetime.UTC).isoformat()
    ...
```

After computing `dscr`/`icr` (existing lines), add:

```python
        output_contract_ratio = compute_output_contract_financing_ratio(
            proposed_limit_vnd, eligible_contract_value_vnd, qd_eb_039_method,
        )
        overview_rows, overview_summary = evaluate_overview(documents)
```

Extend the `credit_engine` dict literal to include the 4th metric:
```python
            "credit_engine": {
                name: asdict(metric)
                for name, metric in {
                    "nwc": nwc, "current_ratio": current_ratio,
                    "short_term_debt_ratio": short_term_debt_ratio, "dscr": dscr, "icr": icr,
                    "output_contract_financing_ratio": output_contract_ratio,
                }.items()
            },
```

Add to the `computed` dict literal:
```python
            "assessed_at": assessed_at,
            "overview": [asdict(r) for r in overview_rows],
            "overview_summary": overview_summary,
            "documents": build_document_status_list(
                documents, extraction_warnings, overview_rows,
                {"nwc": nwc, "current_ratio": current_ratio, "short_term_debt_ratio": short_term_debt_ratio,
                 "dscr": dscr, "icr": icr, "output_contract_financing_ratio": output_contract_ratio},
            ),
```

Also add the overall-conclusion override right before the existing `credit_readiness`/`recommendation` block:
```python
        if overview_summary["pending"] > 0:
            overall_conclusion = "Chưa đủ căn cứ xác định điều kiện áp dụng"
        else:
            overall_conclusion = None  # falls through to existing credit_readiness-derived text
```
and add `"overall_conclusion": overall_conclusion,` to `computed`.

Add a new test to `tests/agents/eb/test_router.py`:

```python
def test_assess_endpoint_includes_overview_and_never_shows_ready_without_full_checklist(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test11.db"))
    monkeypatch.setenv("CASE_FILES_DIR", str(tmp_path / "eb_files"))
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(eb_router, "generate_narrative", lambda computed: {"why": [], "credit_memo": ""})

    files = {"files": ("bctc.csv", io.BytesIO(b"Von chu so huu: 500.000.000\n"), "text/csv")}
    with TestClient(app) as client:
        resp = client.post("/api/eb/assess", data={"customer_name": "A", "tax_id": "0100000001"}, files=files)
    body = resp.json()
    assert len(body["overview"]) == 11
    assert body["overview_summary"]["pending"] > 0
    assert body["overall_conclusion"] == "Chưa đủ căn cứ xác định điều kiện áp dụng"
    assert "credit_engine" in body and "output_contract_financing_ratio" in body["credit_engine"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/usr/local/bin/python -m pytest tests/agents/eb -v`
Expected: PASS (all)

- [ ] **Step 5: Run full suite and commit**

Run: `/usr/local/bin/python -m pytest -q`

```bash
git add app/agents/eb/document_status.py app/agents/eb/router.py \
        tests/agents/eb/test_document_status.py tests/agents/eb/test_router.py
git commit -m "feat: wire overview checklist, 4th metric, and document status into EB response"
```

---

## Task 18: Cross-sell opportunities inside EB (adapter over the existing Cross-sell engine)

**Files:**
- Create: `app/agents/eb/crosssell_adapter.py`
- Modify: `app/agents/eb/router.py`
- Test: `tests/agents/eb/test_crosssell_adapter.py`
- Test: `tests/agents/eb/test_router.py` (add)

**Interfaces:**
- Consumes: `parse_statement_documents` (`app/agents/crosssell/statement_parser.py`), `evaluate_rule1_payroll`, `evaluate_rule6_loan_elsewhere` (`rule1_rule6.py`), `evaluate_rule2_top_partners` (`rule2_partners.py`), `evaluate_rule4_fx` (`rule3_rule4.py`) — all existing, unmodified.
- Produces: `adapt_to_opportunity_card(rule_result: RuleResult) -> dict`; `evaluate_crosssell_opportunities(documents) -> list[dict]`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/agents/eb/test_crosssell_adapter.py
from app.agents.eb.crosssell_adapter import adapt_to_opportunity_card, evaluate_crosssell_opportunities
from app.engine.core.types import RuleResult
from app.extraction.types import ExtractedDocument, ExtractedTable

HEADER = ["Ngay", "So but toan", "Ghi No", "Ghi Co", "Dien giai", "Doi tac", "TK doi tac", "NH doi tac", "Loai tien", "Nguon"]


def _statement_doc(rows, filename="sao_ke.xlsx"):
    doc = ExtractedDocument(
        filename=filename, doc_type="xlsx", text="", tables=[
            ExtractedTable(rows=rows, sheet_or_page="Sheet1")
        ], extraction_method="spreadsheet", confidence=1.0,
    )
    doc.file_id = filename
    return doc


def test_adapt_never_asserts_a_dollar_estimate():
    rr = RuleResult(
        rule_id="RULE2_SCF", rule_name="Tài trợ chuỗi / Thanh toán (EB)", status="KÍCH HOẠT",
        evidence=["Cong ty A: 5 GD, 1,000,000,000 VND"], observed_value=1_000_000_000,
        recommended_action="Tiếp cận đối tác hàng đầu.",
    )
    card = adapt_to_opportunity_card(rr)
    assert card["estimated_value"] is None
    assert card["product_suggestion"] == "Tài trợ chuỗi / Thanh toán (EB)"
    assert card["basis_documents"] == rr.evidence
    assert card["recommended_action"] == "Tiếp cận đối tác hàng đầu."


def test_no_statement_yields_empty_opportunity_list():
    doc = ExtractedDocument(
        filename="bctc.pdf", doc_type="pdf", text="khong lien quan", tables=[],
        extraction_method="text_layer", confidence=1.0,
    )
    assert evaluate_crosssell_opportunities([doc]) == []


def test_activated_rule_becomes_a_card():
    rows = [
        HEADER,
        ["01/01/2026", "1", "0", "600000000", "thanh toan hang", "Cong ty A", "", "", "VND", ""],
        ["02/01/2026", "2", "0", "600000000", "thanh toan hang", "Cong ty A", "", "", "VND", ""],
        ["03/01/2026", "3", "0", "600000000", "thanh toan hang", "Cong ty A", "", "", "VND", ""],
    ]
    cards = evaluate_crosssell_opportunities([_statement_doc(rows)])
    assert any(c["product_suggestion"] == "Tài trợ chuỗi / Thanh toán (EB)" for c in cards)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/local/bin/python -m pytest tests/agents/eb/test_crosssell_adapter.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

```python
# app/agents/eb/crosssell_adapter.py
from app.agents.crosssell.rule1_rule6 import evaluate_rule1_payroll, evaluate_rule6_loan_elsewhere
from app.agents.crosssell.rule2_partners import evaluate_rule2_top_partners
from app.agents.crosssell.rule3_rule4 import evaluate_rule4_fx
from app.agents.crosssell.statement_parser import parse_statement_documents
from app.engine.core.types import RuleResult
from app.extraction.types import ExtractedDocument

ACTIVATED_STATUS = "KÍCH HOẠT"


def adapt_to_opportunity_card(rule_result: RuleResult) -> dict:
    return {
        "product_suggestion": rule_result.rule_name,
        "basis_documents": rule_result.evidence,
        # Statement-derived signals are never contract/invoice-grounded, so
        # this adapter never asserts a dollar "deal size" — only a
        # qualitative opportunity (spec §E: "chưa có chứng từ thì chỉ nêu
        # cơ hội định tính, không hiện số tiền").
        "estimated_value": None,
        "formula_note": rule_result.comment,
        "unverified_conditions": rule_result.verification_question,
        "priority": rule_result.severity or "MEDIUM",
        "reviewer": "RM/Credit Officer",
        "recommended_action": rule_result.recommended_action,
        "status": rule_result.status,
    }


def evaluate_crosssell_opportunities(documents: list[ExtractedDocument]) -> list[dict]:
    transactions = []
    for doc in documents:
        transactions.extend(parse_statement_documents([doc]))
    if not transactions:
        return []
    results = [
        evaluate_rule1_payroll(transactions),
        evaluate_rule2_top_partners(transactions),
        evaluate_rule4_fx(transactions),
        evaluate_rule6_loan_elsewhere(transactions),
    ]
    activated = [r for r in results if r.status == ACTIVATED_STATUS]
    return [adapt_to_opportunity_card(r) for r in activated]
```

Router change in `app/agents/eb/router.py` — import and call, add to `computed`:

```python
from .crosssell_adapter import evaluate_crosssell_opportunities
...
        opportunities = evaluate_crosssell_opportunities(documents)
```

```python
            "opportunities": opportunities,
```
(added to the `computed` dict literal, alongside `documents`/`overview`.)

Add to `tests/agents/eb/test_router.py`:

```python
def test_assess_endpoint_opportunities_empty_without_statement(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test12.db"))
    monkeypatch.setenv("CASE_FILES_DIR", str(tmp_path / "eb_files"))
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(eb_router, "generate_narrative", lambda computed: {"why": [], "credit_memo": ""})

    files = {"files": ("bctc.csv", io.BytesIO(b"Von chu so huu: 500.000.000\n"), "text/csv")}
    with TestClient(app) as client:
        resp = client.post("/api/eb/assess", data={"customer_name": "A", "tax_id": "0100000001"}, files=files)
    assert resp.json()["opportunities"] == []
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/usr/local/bin/python -m pytest tests/agents/eb -v`
Expected: PASS (all)

- [ ] **Step 5: Run full suite and commit**

Run: `/usr/local/bin/python -m pytest -q`

```bash
git add app/agents/eb/crosssell_adapter.py app/agents/eb/router.py \
        tests/agents/eb/test_crosssell_adapter.py tests/agents/eb/test_router.py
git commit -m "feat: surface cross-sell opportunities inside EB via existing rule engine"
```

---

## Task 19: AI Insight — 5-part structure, cites field/condition ids

**Files:**
- Modify: `app/agents/eb/narrative.py`
- Test: `tests/agents/eb/test_narrative.py` (add)

**Interfaces:**
- Produces: no signature change to `generate_narrative` — only `SYSTEM_PROMPT` content changes, which every `why` entry the LLM returns must follow.

- [ ] **Step 1: Write the failing tests**

Add to `tests/agents/eb/test_narrative.py`:

```python
def test_system_prompt_requires_five_part_structure_and_id_citation():
    for phrase in ("Phát hiện", "Số liệu và nguồn", "Ý nghĩa tín dụng", "Điều chưa chắc chắn", "Việc cán bộ cần làm"):
        assert phrase in narrative.SYSTEM_PROMPT
    assert "field_id" in narrative.SYSTEM_PROMPT or "condition_id" in narrative.SYSTEM_PROMPT


def test_generate_narrative_parses_five_part_why_entry(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    from app.config import get_settings

    get_settings.cache_clear()

    entry = (
        "Phát hiện: NWC âm | Số liệu và nguồn: NWC = -500.000.000 (field_id=nwc) | "
        "Ý nghĩa tín dụng: rủi ro thanh khoản ngắn hạn | Điều chưa chắc chắn: chưa rõ nguyên nhân | "
        "Việc cán bộ cần làm: yêu cầu giải trình"
    )
    payload = {"why": [entry], "credit_memo": "Tóm tắt..."}

    def handler(request):
        import httpx
        return httpx.Response(200, json={"choices": [{"message": {"content": __import__("json").dumps(payload, ensure_ascii=False)}}]})

    import httpx
    monkeypatch.setattr(narrative, "_client", httpx.Client(transport=httpx.MockTransport(handler)))
    result = narrative.generate_narrative({"risk_flags": []})
    assert result["why"][0].startswith("Phát hiện:")
    assert "field_id=nwc" in result["why"][0]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/local/bin/python -m pytest tests/agents/eb/test_narrative.py -v`
Expected: FAIL — the new prompt-content assertions fail against the current `SYSTEM_PROMPT` text.

- [ ] **Step 3: Implement**

Replace `SYSTEM_PROMPT` in `app/agents/eb/narrative.py`:

```python
SYSTEM_PROMPT = (
    "Bạn là Trợ lý AI Thẩm định Tín dụng Khối Doanh nghiệp SME của MSB. "
    "Bạn CHỈ được viết nhận xét dựa trên dữ liệu JSON đã tính toán sẵn — KHÔNG được tự tính "
    "hoặc thay đổi bất kỳ con số hay red-flag nào. "
    "Mỗi phần tử trong \"why\" PHẢI theo đúng cấu trúc 5 phần, nối bằng \" | \": "
    "\"Phát hiện: ... | Số liệu và nguồn: ... | Ý nghĩa tín dụng: ... | "
    "Điều chưa chắc chắn: ... | Việc cán bộ cần làm: ...\". "
    "Mỗi nhận định PHẢI trích dẫn ít nhất một field_id hoặc condition_id có thật trong dữ liệu JSON "
    "được cung cấp — không được nhận định chung chung không có căn cứ cụ thể. "
    "Trả lời DUY NHẤT bằng JSON hợp lệ đúng schema: "
    '{"why": ["..."], "credit_memo": "..."}. '
    "credit_memo kết thúc bằng: \"Agent chỉ chuẩn bị hồ sơ và kiến nghị để cán bộ có thẩm quyền "
    "xem xét; không tự phê duyệt, cam kết cấp hạn mức hoặc thay thế kết luận thẩm định của MSB.\""
)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/usr/local/bin/python -m pytest tests/agents/eb/test_narrative.py -v`
Expected: PASS (all)

- [ ] **Step 5: Run full suite and commit**

Run: `/usr/local/bin/python -m pytest -q`

```bash
git add app/agents/eb/narrative.py tests/agents/eb/test_narrative.py
git commit -m "feat: require 5-part structure and evidence-id citation in EB AI Insight"
```

---

## Task 20: Stress Test endpoint

**Files:**
- Create: `app/agents/eb/stress_test.py`
- Modify: `app/agents/eb/router.py`
- Test: `tests/agents/eb/test_stress_test.py`
- Test: `tests/agents/eb/test_router.py` (add)

**Interfaces:**
- Consumes: `compute_nwc`, `compute_dscr`, `compute_icr` (existing, unchanged signatures).
- Produces: `run_stress_test(inputs: EbFinancialInputs, revenue_pct=0.0, margin_pct=0.0, interest_rate_pct=0.0, collection_speed_pct=0.0) -> dict` (keys `assumptions`, `before`, `after`); `POST /api/eb/stress-test`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/agents/eb/test_stress_test.py
from app.agents.eb.financial_inputs import EbFinancialInputs
from app.agents.eb.stress_test import run_stress_test


def test_stress_test_returns_before_and_after():
    inputs = EbFinancialInputs(
        current_assets_vnd=2_000_000_000, current_liabilities_vnd=1_500_000_000,
        ebit_vnd=800_000_000, interest_expense_vnd=200_000_000,
    )
    result = run_stress_test(inputs, margin_pct=-50)
    assert result["before"]["icr"]["value"] == 4.0
    assert result["after"]["icr"]["value"] == 2.0
    assert "kịch bản giả định" in result["assumptions"]["note"].lower()


def test_stress_test_never_touches_nwc_with_revenue_delta():
    # NWC is a balance-sheet snapshot, not a revenue-driven figure — a
    # revenue stress delta must not silently change it.
    inputs = EbFinancialInputs(current_assets_vnd=2_000_000_000, current_liabilities_vnd=1_500_000_000)
    result = run_stress_test(inputs, revenue_pct=20)
    assert result["before"]["nwc"]["value"] == result["after"]["nwc"]["value"]


def test_stress_test_handles_missing_inputs_gracefully():
    result = run_stress_test(EbFinancialInputs(), interest_rate_pct=10)
    assert result["after"]["dscr"]["status"] == "NEED_MORE_DATA"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/local/bin/python -m pytest tests/agents/eb/test_stress_test.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

```python
# app/agents/eb/stress_test.py
from dataclasses import asdict, replace

from .financial_inputs import EbFinancialInputs
from .liquidity import compute_nwc
from .repayment_capacity import compute_dscr, compute_icr


def run_stress_test(
    inputs: EbFinancialInputs,
    revenue_pct: float = 0.0,
    margin_pct: float = 0.0,
    interest_rate_pct: float = 0.0,
    collection_speed_pct: float = 0.0,
) -> dict:
    before = {"nwc": compute_nwc(inputs), "dscr": compute_dscr(inputs), "icr": compute_icr(inputs)}

    stressed = replace(inputs)
    if stressed.ebit_vnd is not None:
        stressed.ebit_vnd = round(stressed.ebit_vnd * (1 + revenue_pct / 100) * (1 + margin_pct / 100), 2)
    if stressed.interest_expense_vnd is not None:
        stressed.interest_expense_vnd = round(stressed.interest_expense_vnd * (1 + interest_rate_pct / 100), 2)
    if stressed.interest_due_vnd is not None:
        stressed.interest_due_vnd = round(stressed.interest_due_vnd * (1 + interest_rate_pct / 100), 2)
    if stressed.cfads_vnd is not None:
        stressed.cfads_vnd = round(stressed.cfads_vnd * (1 + collection_speed_pct / 100), 2)
    # NWC is a balance-sheet snapshot (current assets/liabilities), not driven
    # by revenue/margin/rate/collection-speed deltas — deliberately untouched.

    after = {"nwc": compute_nwc(stressed), "dscr": compute_dscr(stressed), "icr": compute_icr(stressed)}

    return {
        "assumptions": {
            "revenue_pct": revenue_pct, "margin_pct": margin_pct,
            "interest_rate_pct": interest_rate_pct, "collection_speed_pct": collection_speed_pct,
            "note": "Đây là kịch bản giả định do cán bộ nhập, không phải dự báo tài chính chắc chắn.",
        },
        "before": {k: asdict(v) for k, v in before.items()},
        "after": {k: asdict(v) for k, v in after.items()},
    }
```

Router addition in `app/agents/eb/router.py`:

```python
from .stress_test import run_stress_test

@router.post("/stress-test")
async def stress_test(payload: dict) -> dict:
    raw_inputs = payload.get("inputs", {})
    valid_fields = {f for f in EbFinancialInputs.__dataclass_fields__}
    inputs = EbFinancialInputs(**{k: v for k, v in raw_inputs.items() if k in valid_fields})
    deltas = payload.get("deltas", {})
    return run_stress_test(
        inputs,
        revenue_pct=deltas.get("revenue_pct", 0.0),
        margin_pct=deltas.get("margin_pct", 0.0),
        interest_rate_pct=deltas.get("interest_rate_pct", 0.0),
        collection_speed_pct=deltas.get("collection_speed_pct", 0.0),
    )
```

(No 400 on missing inputs — consistent with the rest of the app's graceful-degradation pattern: metrics resolve to `NEED_MORE_DATA` rather than an error response.)

Add to `tests/agents/eb/test_router.py`:

```python
def test_stress_test_endpoint_recomputes_metrics():
    client = TestClient(app)
    resp = client.post("/api/eb/stress-test", json={
        "inputs": {"ebit_vnd": 800_000_000, "interest_expense_vnd": 200_000_000},
        "deltas": {"margin_pct": -50},
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["before"]["icr"]["value"] == 4.0
    assert body["after"]["icr"]["value"] == 2.0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/usr/local/bin/python -m pytest tests/agents/eb -v`
Expected: PASS (all)

- [ ] **Step 5: Run full suite and commit**

Run: `/usr/local/bin/python -m pytest -q`

```bash
git add app/agents/eb/stress_test.py app/agents/eb/router.py \
        tests/agents/eb/test_stress_test.py tests/agents/eb/test_router.py
git commit -m "feat: add EB stress-test endpoint reusing existing metric formulas"
```

---

## Task 21: MB02a export includes overview checklist, stays in sync with web JSON

**Files:**
- Modify: `app/agents/eb/mb02_export.py`
- Test: `tests/agents/eb/test_mb02_export.py` (add)

**Interfaces:**
- Consumes: `computed["overview"]` (list of `asdict(ConditionRow)`, Task 17).
- Produces: no signature change to `build_mb02_docx` — adds a new "H. Bảng điều kiện tổng quan" section reading directly from `computed["overview"]`.

- [ ] **Step 1: Write the failing test**

Add to `tests/agents/eb/test_mb02_export.py`:

```python
def test_docx_overview_section_matches_json_values():
    import io

    import docx

    computed = {
        "customer_profile": {"customer_name": "CONG TY TNHH TEST", "tax_id": "0100000001"},
        "credit_engine": {}, "risk_flags": [], "missing_data": [],
        "recommendation": "PROCEED_FOR_HUMAN_REVIEW", "why": [], "credit_memo": "",
        "overview": [
            {
                "condition_id": "C08", "condition_name": "Vốn chủ sở hữu",
                "observed": {"value": 500000000.0, "status": "COMPUTED"},
                "compare_rule": "> 0", "result": "PASS", "reason_if_incomplete": None,
            },
            {
                "condition_id": "C11", "condition_name": "Lịch sử quan hệ tín dụng",
                "observed": {"value": None, "status": "MISSING_DATA"},
                "compare_rule": "...", "result": "PENDING_INTERNAL_CHECK",
                "reason_if_incomplete": "Cần dữ liệu CIC.",
            },
        ],
    }
    docx_bytes = build_mb02_docx(computed)
    doc = docx.Document(io.BytesIO(docx_bytes))
    full_text = "\n".join(p.text for p in doc.paragraphs)
    assert "Vốn chủ sở hữu" in full_text
    assert "500000000.0" in full_text
    assert "PASS" in full_text
    assert "Lịch sử quan hệ tín dụng" in full_text
    assert "Cần dữ liệu CIC." in full_text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/usr/local/bin/python -m pytest tests/agents/eb/test_mb02_export.py -v -k overview_section`
Expected: FAIL — `AssertionError` (section doesn't exist yet).

- [ ] **Step 3: Implement**

Add to `app/agents/eb/mb02_export.py`, right before the final `document.add_paragraph(DISCLAIMER)`:

```python
    document.add_heading("H. Bảng điều kiện tổng quan (mục A)", level=2)
    overview = computed.get("overview") or []
    if not overview:
        document.add_paragraph("Chưa có dữ liệu điều kiện tổng quan.")
    for row in overview:
        if not isinstance(row, dict):
            continue
        observed = row.get("observed") or {}
        value = observed.get("value")
        value_text = "Chưa có dữ liệu" if value is None else str(value)
        line = f"{row.get('condition_name', '?')}: {value_text} — Kết quả: {row.get('result', '?')}"
        document.add_paragraph(line, style="List Bullet")
        if row.get("reason_if_incomplete"):
            document.add_paragraph(f"  Lý do: {row['reason_if_incomplete']}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/usr/local/bin/python -m pytest tests/agents/eb/test_mb02_export.py -v`
Expected: PASS (all)

- [ ] **Step 5: Run full suite and commit**

Run: `/usr/local/bin/python -m pytest -q`

```bash
git add app/agents/eb/mb02_export.py tests/agents/eb/test_mb02_export.py
git commit -m "feat: include overview checklist in MB02a export, kept in sync with web JSON"
```

---

## Task 22: End-to-end test fixtures (complete bundle, sparse bundle)

**Files:**
- Create: `tests/agents/eb/test_overview_end_to_end.py`

**Note on fixture form:** the spec (§11) describes these as files under `tests/fixtures/`, generated with `reportlab`/`openpyxl`. Every existing EB router test in this codebase instead posts inline CSV byte content through `TestClient` (see `tests/agents/eb/test_router.py`) — CSV is parsed identically to any other supported format by the same pipeline, so it exercises the same code paths with far less test-fixture machinery. This task follows the codebase's established pattern rather than introducing a second fixture style; the two "hồ sơ kiểm thử" are Python builder functions, not files on disk.

**Interfaces:**
- Consumes: the full `/api/eb/assess` endpoint (Task 17 + all prior tasks).

- [ ] **Step 1: Write the failing tests**

```python
# tests/agents/eb/test_overview_end_to_end.py
import io

from fastapi.testclient import TestClient

from app.agents.eb import router as eb_router
from app.main import app

# Conditions C01 (Đối tượng áp dụng), C03 (Doanh thu 6 tháng qua TKTT), C06
# (03/05 đối tác), C11 (Lịch sử quan hệ tín dụng) are PENDING_INTERNAL_CHECK
# or INSUFFICIENT_DATA *by construction* — no CIF/CIC connection exists, no
# statement window can be verified, and the "03/05" policy reading is
# unresolved (spec §5.2, §5.3, §5.4). These four never resolve PASS/FAIL,
# with or without supporting documents — that is the honest, intended
# behavior this test pins, not a gap in the fixture.
_ALWAYS_PENDING = {"C01", "C03", "C06", "C11"}


def _complete_evidence_files():
    dkkd = (
        "GIAY CHUNG NHAN DANG KY DOANH NGHIEP\n"
        "Ngay thanh lap: 01/01/2020\n"
        "Nganh nghe kinh doanh: Ban le hang tieu dung\n"
        "Tinh trang: dang hoat dong\n"
    ).encode()
    bctc = (
        "BAO CAO TAI CHINH 2025\n"
        "Doanh thu thuan: 50.000.000.000\n"
        "Von chu so huu: 500.000.000\n"
        "Loi nhuan gop: 1.000.000.000\n"
        "Chi phi lai vay: 300.000.000\n"
    ).encode()
    pakd = "PHUONG AN KINH DOANH\nLNST theo PAKD: 200.000.000\n".encode()
    return [
        ("files", ("dkkd.csv", io.BytesIO(dkkd), "text/csv")),
        ("files", ("bctc.csv", io.BytesIO(bctc), "text/csv")),
        ("files", ("pakd.csv", io.BytesIO(pakd), "text/csv")),
    ]


def _sparse_bundle_files():
    # Only a business registration certificate — no BCTC, no PAKD, no CIC.
    dkkd = "GIAY CHUNG NHAN DANG KY DOANH NGHIEP\nNgay thanh lap: 01/01/2020\n".encode()
    return [("files", ("dkkd.csv", io.BytesIO(dkkd), "text/csv"))]


def _post(client, files):
    return client.post(
        "/api/eb/assess",
        data={"customer_name": "CONG TY TNHH TEST", "tax_id": "0100000099"},
        files=files,
    )


def test_complete_evidence_bundle_resolves_every_computable_condition(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "e2e1.db"))
    monkeypatch.setenv("CASE_FILES_DIR", str(tmp_path / "eb_files1"))
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(eb_router, "generate_narrative", lambda computed: {"why": [], "credit_memo": ""})

    with TestClient(app) as client:
        resp = _post(client, _complete_evidence_files())
    body = resp.json()
    for row in body["overview"]:
        if row["condition_id"] in _ALWAYS_PENDING:
            assert row["result"] in ("INSUFFICIENT_DATA", "PENDING_INTERNAL_CHECK")
        else:
            assert row["result"] in ("PASS", "FAIL"), (row["condition_id"], row["result"])


def test_sparse_bundle_never_silently_reports_ready(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "e2e2.db"))
    monkeypatch.setenv("CASE_FILES_DIR", str(tmp_path / "eb_files2"))
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(eb_router, "generate_narrative", lambda computed: {"why": [], "credit_memo": ""})

    with TestClient(app) as client:
        resp = _post(client, _sparse_bundle_files())
    body = resp.json()
    c11 = next(r for r in body["overview"] if r["condition_id"] == "C11")
    assert c11["result"] == "PENDING_INTERNAL_CHECK"
    assert body["overall_conclusion"] == "Chưa đủ căn cứ xác định điều kiện áp dụng"
    assert body["overview_summary"]["pending"] >= 4
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/local/bin/python -m pytest tests/agents/eb/test_overview_end_to_end.py -v`
Expected: FAIL only if any prior task's wiring is incomplete — if Tasks 1–21 all landed, this should largely already pass; treat any failure here as a real bug in an earlier task, not something to patch locally in this test file.

- [ ] **Step 3: Fix whatever the failures reveal**

There is no new production code in this task — if a condition unexpectedly returns `INSUFFICIENT_DATA` instead of `PASS`/`FAIL` (or vice versa), trace it back to the specific `overview/*.py` module from Tasks 9–14 and fix the regex/logic there, then re-run this task's tests.

- [ ] **Step 4: Run tests to verify they pass**

Run: `/usr/local/bin/python -m pytest tests/agents/eb/test_overview_end_to_end.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Run full suite and commit**

Run: `/usr/local/bin/python -m pytest -q`
Expected: all green — this is the point where the entire backend (Tasks 1–22) is proven to work together, not just in isolation per-module.

```bash
git add tests/agents/eb/test_overview_end_to_end.py
git commit -m "test: add end-to-end EB overview fixtures (complete + sparse bundles)"
```

---

## Task 23: Frontend types for evidence-backed fields

**Files:**
- Modify: `web/lib/api.ts`

**Interfaces:**
- Produces: `EvidenceRef`, `EvidencedField`, `ConditionRow`, `DocumentStatus`, `OpportunityCard` TypeScript types; `AssessmentResult` gains `assessed_at?`, `overview?`, `overview_summary?`, `overall_conclusion?`, `documents?`, `opportunities?`; new `runStressTest()` and `evidenceFileUrl()` helpers.

There is no JS/TS test runner in this repo (`web/package.json` has no test script) — verification for every frontend task in this plan is `npm run build` (type-checks + compiles the static export) plus a Playwright screenshot of the running page, the same pattern already used earlier in this project for UI changes.

- [ ] **Step 1: Make the change**

Add to `web/lib/api.ts`, above `export type AssessmentResult`:

```typescript
export type EvidenceRef = {
  file_id: string;
  filename: string;
  location: string;
  original_text: string;
  period?: string | null;
};

export type EvidencedField = {
  field_id: string;
  label: string;
  value: number | string | null;
  unit?: string | null;
  period?: string | null;
  status: "VERIFIED" | "COMPUTED" | "PENDING_REVIEW" | "MISSING_DATA" | "NOT_APPLICABLE";
  evidence: EvidenceRef[];
  formula?: string | null;
  input_fields?: string[];
  policy_version?: string | null;
  last_verified_at?: string | null;
};

export type ConditionRow = {
  condition_id: string;
  condition_name: string;
  observed: EvidencedField;
  compare_rule: string;
  result: "PASS" | "FAIL" | "INSUFFICIENT_DATA" | "PENDING_INTERNAL_CHECK" | "NOT_APPLICABLE";
  reason_if_incomplete?: string | null;
};

export type OverviewSummary = {
  checked: number;
  total: number;
  passed: number;
  failed: number;
  pending: number;
};

export type DocumentStatus = {
  filename: string;
  doc_type?: string;
  status: "KHÔNG_ĐỌC_ĐƯỢC" | "ĐÃ_TRÍCH_XUẤT" | "CHỜ_XÁC_MINH" | "ĐÃ_TẢI_LÊN";
  cited_field_count: number;
  warnings: string[];
};

export type OpportunityCard = {
  product_suggestion: string;
  basis_documents: string[];
  estimated_value: number | null;
  formula_note?: string;
  unverified_conditions?: string | null;
  priority: string;
  reviewer: string;
  recommended_action?: string;
  status: string;
};
```

Extend the existing `RiskFlag` type with the new evidence citations (add one field, do not remove any existing ones):

```typescript
  evidence_refs?: Record<string, EvidenceRef[]>;
```

Extend `AssessmentResult` (add fields, do not remove any existing ones):

```typescript
  case_id?: string;
  assessed_at?: string;
  overview?: ConditionRow[];
  overview_summary?: OverviewSummary;
  overall_conclusion?: string | null;
  documents?: DocumentStatus[];
  opportunities?: OpportunityCard[];
```

Add helper functions at the bottom of the file:

```typescript
export function evidenceFileUrl(caseId: string, fileId: string): string {
  return `/api/eb/files/${encodeURIComponent(caseId)}/${encodeURIComponent(fileId)}`;
}

export type StressTestResult = {
  assumptions: Record<string, unknown>;
  before: Record<string, { value: number | null; status: string }>;
  after: Record<string, { value: number | null; status: string }>;
};

export async function runStressTest(
  inputs: Record<string, number | null>,
  deltas: { revenue_pct?: number; margin_pct?: number; interest_rate_pct?: number; collection_speed_pct?: number }
): Promise<StressTestResult> {
  const resp = await fetch("/api/eb/stress-test", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ inputs, deltas }),
  });
  if (!resp.ok) throw new Error(`Stress test thất bại: HTTP ${resp.status}`);
  return resp.json();
}
```

- [ ] **Step 2: Verify it compiles**

Run: `cd web && npm run build`
Expected: `✓ Compiled successfully` (new types are additive — nothing in `ResultPanel.tsx`/`CrossSellPanel.tsx`/`AssessmentForm.tsx` references them yet, so nothing else can break).

- [ ] **Step 3: Commit**

```bash
git add web/lib/api.ts
git commit -m "feat(web): add evidence-backed field/condition types for EB"
```

---

## Task 24: EbResultPanel.tsx — case header + 11-condition overview table

**Files:**
- Create: `web/components/EbResultPanel.tsx`

**Interfaces:**
- Consumes: `AssessmentResult`, `ConditionRow`, `evidenceFileUrl` (Task 23).
- Produces: `export default function EbResultPanel({ result }: { result: AssessmentResult })` — used by later tasks and wired into `page.tsx` in Task 26.

- [ ] **Step 1: Write the component (header + table)**

```tsx
// web/components/EbResultPanel.tsx
"use client";

import { AssessmentResult, ConditionRow, evidenceFileUrl } from "@/lib/api";

const RESULT_LABEL: Record<string, string> = {
  PASS: "Đạt",
  FAIL: "Không đạt",
  INSUFFICIENT_DATA: "Chưa đủ dữ liệu",
  PENDING_INTERNAL_CHECK: "Chờ kiểm tra trên hệ thống nội bộ",
  NOT_APPLICABLE: "Không áp dụng",
};

const RESULT_STYLE: Record<string, string> = {
  PASS: "bg-green-100 text-green-800",
  FAIL: "bg-red-100 text-red-800",
  INSUFFICIENT_DATA: "bg-gray-100 text-gray-700",
  PENDING_INTERNAL_CHECK: "bg-amber-100 text-amber-800",
  NOT_APPLICABLE: "bg-gray-100 text-gray-500",
};

function ResultBadge({ result }: { result: string }) {
  return (
    <span className={`text-xs font-semibold px-2 py-1 rounded ${RESULT_STYLE[result] ?? "bg-gray-100"}`}>
      {RESULT_LABEL[result] ?? result}
    </span>
  );
}

function formatObservedValue(row: ConditionRow): string {
  const v = row.observed.value;
  if (v === null || v === undefined) return "Chưa có dữ liệu";
  if (typeof v === "number") {
    return row.observed.unit === "VND" ? `${v.toLocaleString("vi-VN")} VND` : v.toLocaleString("vi-VN");
  }
  return String(v);
}

function EvidenceCell({ row, caseId }: { row: ConditionRow; caseId?: string }) {
  if (row.observed.evidence.length === 0) {
    return <span className="text-xs text-gray-400">—</span>;
  }
  return (
    <ul className="text-xs space-y-1">
      {row.observed.evidence.map((ev, i) => (
        <li key={i}>
          {caseId ? (
            <a
              href={evidenceFileUrl(caseId, ev.file_id)}
              target="_blank"
              rel="noopener noreferrer"
              className="text-msb-navy underline"
            >
              {ev.filename} — {ev.location}
            </a>
          ) : (
            <span>{ev.filename} — {ev.location}</span>
          )}
          <div className="text-gray-500 italic">&quot;{ev.original_text}&quot;</div>
        </li>
      ))}
    </ul>
  );
}

function OverviewTable({ rows, caseId }: { rows: ConditionRow[]; caseId?: string }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="text-left border-b bg-msb-bg">
            <th className="py-2 px-2">Tên điều kiện</th>
            <th className="py-2 px-2">Giá trị/hiện trạng thực tế</th>
            <th className="py-2 px-2">Điều kiện đối chiếu</th>
            <th className="py-2 px-2">Kết quả</th>
            <th className="py-2 px-2">Nguồn chứng cứ và ngày dữ liệu</th>
            <th className="py-2 px-2">Lý do/chứng từ còn thiếu</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.condition_id} className="border-b align-top">
              <td className="py-2 px-2 font-medium">{row.condition_name}</td>
              <td className="py-2 px-2">{formatObservedValue(row)}</td>
              <td className="py-2 px-2 text-gray-600">{row.compare_rule}</td>
              <td className="py-2 px-2"><ResultBadge result={row.result} /></td>
              <td className="py-2 px-2"><EvidenceCell row={row} caseId={caseId} /></td>
              <td className="py-2 px-2 text-gray-600">{row.reason_if_incomplete ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function EbResultPanel({ result }: { result: AssessmentResult }) {
  const overview = result.overview ?? [];
  const summary = result.overview_summary;

  return (
    <div className="space-y-6 mt-6">
      <div className="bg-white rounded-lg shadow p-6 space-y-2">
        <div className="flex flex-wrap gap-6 text-sm">
          <div><span className="text-gray-500">Mã hồ sơ</span><p className="font-semibold">{result.case_id ?? "—"}</p></div>
          <div><span className="text-gray-500">Khách hàng</span><p className="font-semibold">{result.customer_profile?.customer_name as string ?? "—"}</p></div>
          <div><span className="text-gray-500">MST</span><p className="font-semibold">{result.customer_profile?.tax_id as string ?? "—"}</p></div>
          <div><span className="text-gray-500">Thời điểm chạy</span><p className="font-semibold">{result.assessed_at ?? "—"}</p></div>
        </div>
        {result.overall_conclusion && (
          <div className="bg-amber-50 border border-amber-300 rounded p-3 text-sm font-semibold text-amber-900">
            {result.overall_conclusion}
          </div>
        )}
      </div>

      <div className="bg-white rounded-lg shadow p-6 space-y-3">
        <h2 className="text-lg font-semibold text-msb-navy">A. Thông tin tổng quan</h2>
        {summary && (
          <p className="text-sm text-gray-600">
            {summary.checked}/{summary.total} điều kiện đã kiểm tra đủ dữ liệu; {summary.passed} đạt,{" "}
            {summary.failed} không đạt, {summary.pending} chờ xác minh.
          </p>
        )}
        <OverviewTable rows={overview} caseId={result.case_id} />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify it compiles**

Run: `cd web && npm run build`
Expected: `✓ Compiled successfully` (component isn't imported anywhere yet, so a type error here would only show up in the build if TypeScript checks unimported files — Next.js's `next build` type-checks the whole project, so this does catch errors even before wiring).

- [ ] **Step 3: Commit**

```bash
git add web/components/EbResultPanel.tsx
git commit -m "feat(web): add EB overview table with clickable evidence citations"
```

---

## Task 25: EbResultPanel.tsx — 4 metric cards, risk flags (3 groups), document panel

**Files:**
- Modify: `web/components/EbResultPanel.tsx`

**Interfaces:**
- Consumes: `result.credit_engine`, `result.risk_flags`, `result.documents` (Task 17), `ACTIVATED_STATUS`/`INSUFFICIENT_DATA_STATUS` (`web/lib/api.ts`, existing).

- [ ] **Step 1: Add metric cards, risk-flag grouping, and document panel**

Add these imports to the top of `web/components/EbResultPanel.tsx`:

```tsx
import { useState } from "react";
import { ACTIVATED_STATUS, DocumentStatus, INSUFFICIENT_DATA_STATUS, RiskFlag } from "@/lib/api";
```

Add these components above `EbResultPanel`:

```tsx
const METRIC_LABELS: Record<string, { label: string; unit: string }> = {
  nwc: { label: "Vốn lưu động ròng (NWC)", unit: "VND" },
  dscr: { label: "Hệ số trả nợ (DSCR)", unit: "lần" },
  icr: { label: "Hệ số bù đắp lãi vay (ICR)", unit: "lần" },
  output_contract_financing_ratio: { label: "Tỷ lệ tài trợ hợp đồng đầu ra", unit: "%" },
};

type MetricValue = {
  value: number | string | null;
  formula?: string;
  input_values?: Record<string, unknown>;
  input_sources?: Record<string, string>;
  status?: string;
  policy_version?: string | null;
};

function MetricCard({ metricKey, metric }: { metricKey: string; metric: MetricValue }) {
  const [open, setOpen] = useState(false);
  const meta = METRIC_LABELS[metricKey] ?? { label: metricKey, unit: "" };
  const hasValue = metric.status === "OK" && metric.value !== null;
  return (
    <div className="bg-white rounded-lg shadow p-4">
      <h3 className="text-sm font-medium text-gray-500">{meta.label}</h3>
      <p className="text-2xl font-bold text-msb-navy">
        {hasValue ? `${metric.value} ${meta.unit}` : "Chưa có dữ liệu"}
      </p>
      {metricKey === "output_contract_financing_ratio" && (
        <p className="text-xs text-gray-500 mt-1">Tỷ lệ đề xuất, chưa phải mức đã phê duyệt.</p>
      )}
      <button className="text-xs text-msb-navy underline mt-2" onClick={() => setOpen((v) => !v)}>
        {open ? "Ẩn giải thích" : "Giải thích"}
      </button>
      {open && (
        <div className="mt-2 text-xs text-gray-600 space-y-1 border-t pt-2">
          <p>Công thức: {metric.formula ?? "—"}</p>
          {metric.input_values &&
            Object.entries(metric.input_values).map(([k, v]) => (
              <p key={k}>
                {k}: {String(v)} ({metric.input_sources?.[k] ?? "—"})
              </p>
            ))}
          <p>{metric.policy_version ?? "Ngưỡng demo – chờ nghiệp vụ xác nhận"}</p>
        </div>
      )}
    </div>
  );
}

function RiskFlagsSection({ flags }: { flags: RiskFlag[] }) {
  const activated = flags.filter((f) => f.status === ACTIVATED_STATUS);
  const undetermined = flags.filter((f) => f.status === INSUFFICIENT_DATA_STATUS);
  const cleared = flags.filter((f) => f.status !== ACTIVATED_STATUS && f.status !== INSUFFICIENT_DATA_STATUS);
  const [showCleared, setShowCleared] = useState(false);

  return (
    <div className="bg-white rounded-lg shadow p-6 space-y-3">
      <h2 className="text-lg font-semibold text-msb-navy">C. Cảnh báo rủi ro ({activated.length})</h2>
      {activated.length > 0 ? (
        <ul className="text-sm space-y-2">
          {activated.map((f, i) => (
            <li key={i} className="border-l-4 border-red-400 pl-3">
              <span className="font-semibold">{f.rule_name ?? f.rule_id}</span> ({f.severity}): {f.impact}
              {f.evidence_refs && Object.keys(f.evidence_refs).length > 0 && (
                <ul className="text-xs text-gray-500 mt-1">
                  {Object.values(f.evidence_refs).flat().map((ev, j) => (
                    <li key={j}>{ev.filename} — {ev.location}: &quot;{ev.original_text}&quot;</li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-gray-500">Không có cảnh báo được kích hoạt trong số các quy tắc đã kiểm tra.</p>
      )}
      {undetermined.length > 0 && (
        <div className="pt-2 border-t">
          <h3 className="text-sm font-medium text-gray-500 mb-1">Chưa thể đánh giá</h3>
          <ul className="text-sm text-gray-500 space-y-1">
            {undetermined.map((f, i) => (
              <li key={i}>{f.rule_name ?? f.rule_id}: {f.impact}</li>
            ))}
          </ul>
        </div>
      )}
      {cleared.length > 0 && (
        <div className="pt-2 border-t">
          <button className="text-xs text-msb-navy underline" onClick={() => setShowCleared((v) => !v)}>
            {showCleared ? "Ẩn" : "Xem"} {cleared.length} quy tắc không kích hoạt
          </button>
          {showCleared && (
            <ul className="text-xs text-gray-400 mt-1 space-y-1">
              {cleared.map((f, i) => <li key={i}>{f.rule_name ?? f.rule_id}</li>)}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

const DOC_STATUS_LABEL: Record<string, string> = {
  "KHÔNG_ĐỌC_ĐƯỢC": "Không đọc được",
  "ĐÃ_TRÍCH_XUẤT": "Đã trích xuất",
  "CHỜ_XÁC_MINH": "Chờ xác minh",
  "ĐÃ_TẢI_LÊN": "Đã tải lên",
};

function DocumentPanel({ documents }: { documents: DocumentStatus[] }) {
  if (documents.length === 0) return null;
  return (
    <div className="bg-white rounded-lg shadow p-6 space-y-2">
      <h2 className="text-lg font-semibold text-msb-navy">D. Hồ sơ khách hàng</h2>
      <ul className="text-sm divide-y">
        {documents.map((d, i) => (
          <li key={i} className="py-2 flex justify-between items-center">
            <div>
              <p className="font-medium">{d.filename}</p>
              <p className="text-xs text-gray-500">{d.doc_type ?? "—"} · {d.cited_field_count} trường đã trích xuất</p>
              {d.warnings.length > 0 && <p className="text-xs text-red-600">{d.warnings.join("; ")}</p>}
            </div>
            <span className="text-xs font-semibold px-2 py-1 rounded bg-gray-100">
              {DOC_STATUS_LABEL[d.status] ?? d.status}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
```

Insert the new sections into `EbResultPanel`'s return, right after the overview table's closing `</div>`:

```tsx
      {result.credit_engine && (
        <div className="bg-white rounded-lg shadow p-6 space-y-3">
          <h2 className="text-lg font-semibold text-msb-navy">B.1 Bốn thẻ chỉ tiêu</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {Object.entries(result.credit_engine).map(([key, metric]) => (
              <MetricCard key={key} metricKey={key} metric={metric as MetricValue} />
            ))}
          </div>
        </div>
      )}

      <RiskFlagsSection flags={result.risk_flags ?? []} />
      <DocumentPanel documents={result.documents ?? []} />
```

- [ ] **Step 2: Verify it compiles**

Run: `cd web && npm run build`
Expected: `✓ Compiled successfully`

- [ ] **Step 3: Commit**

```bash
git add web/components/EbResultPanel.tsx
git commit -m "feat(web): add EB metric cards, grouped risk flags, and document panel"
```

---

## Task 26: EbResultPanel.tsx — cross-sell cards, AI Insight, Stress Test, Soạn tờ trình

**Files:**
- Modify: `web/components/EbResultPanel.tsx`

**Interfaces:**
- Consumes: `result.opportunities` (Task 18), `result.why`/`result.credit_memo` (Task 19), `runStressTest`, `exportMb02` (`web/lib/api.ts`).

- [ ] **Step 1: Add cross-sell cards, AI Insight, Stress Test panel, export button**

Add to the imports at the top of `web/components/EbResultPanel.tsx`:

```tsx
import { OpportunityCard, exportMb02, runStressTest } from "@/lib/api";
```

Add these components above `EbResultPanel`:

```tsx
function CrossSellSection({ opportunities }: { opportunities: OpportunityCard[] }) {
  if (opportunities.length === 0) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-msb-navy mb-2">E. Cơ hội bán chéo</h2>
        <p className="text-sm text-gray-500">Chưa phát hiện dấu hiệu nhu cầu rõ ràng từ chứng từ hiện có.</p>
      </div>
    );
  }
  return (
    <div className="bg-white rounded-lg shadow p-6 space-y-3">
      <h2 className="text-lg font-semibold text-msb-navy">E. Cơ hội bán chéo</h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {opportunities.map((o, i) => (
          <div key={i} className="border rounded p-3 text-sm space-y-1">
            <p className="font-semibold text-msb-navy">{o.product_suggestion}</p>
            <p className="text-gray-600">{o.formula_note}</p>
            {o.basis_documents.length > 0 && (
              <ul className="text-xs text-gray-500 list-disc list-inside">
                {o.basis_documents.map((b, j) => <li key={j}>{b}</li>)}
              </ul>
            )}
            {o.unverified_conditions && (
              <p className="text-xs text-amber-700">Chưa xác minh: {o.unverified_conditions}</p>
            )}
            <p className="text-xs text-gray-500">Mức ưu tiên: {o.priority} · Người rà soát: {o.reviewer}</p>
            {o.recommended_action && <p className="text-xs font-medium">{o.recommended_action}</p>}
          </div>
        ))}
      </div>
    </div>
  );
}

function AiInsightSection({ why, creditMemo }: { why: string[]; creditMemo?: string }) {
  const [showDeepAnalysis, setShowDeepAnalysis] = useState(false);
  return (
    <div className="bg-white rounded-lg shadow p-6 space-y-3">
      <h2 className="text-lg font-semibold text-msb-navy">F. AI Insight</h2>
      {why.length > 0 ? (
        <ul className="text-sm space-y-2 list-disc list-inside">
          {why.map((w, i) => <li key={i}>{w}</li>)}
        </ul>
      ) : (
        <p className="text-sm text-gray-500">Chưa có nhận định AI (có thể do vượt ngân sách thời gian xử lý).</p>
      )}
      <button className="text-xs text-msb-navy underline" onClick={() => setShowDeepAnalysis((v) => !v)}>
        {showDeepAnalysis ? "Ẩn phân tích sâu" : "Phân tích sâu"}
      </button>
      {showDeepAnalysis && (
        <p className="text-sm text-gray-600 border-t pt-2">
          {creditMemo || "Chỉ có 1 kỳ dữ liệu hoặc chưa đủ dữ liệu — chưa đủ để phân tích xu hướng."}
        </p>
      )}
    </div>
  );
}

type StressTestState = {
  revenue_pct: number; margin_pct: number; interest_rate_pct: number; collection_speed_pct: number;
};

function StressTestPanel({ creditEngine }: { creditEngine?: Record<string, MetricValue> }) {
  const [deltas, setDeltas] = useState<StressTestState>({
    revenue_pct: 0, margin_pct: 0, interest_rate_pct: 0, collection_speed_pct: 0,
  });
  const [result, setResult] = useState<Awaited<ReturnType<typeof runStressTest>> | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleRun() {
    setError(null);
    try {
      const inputs: Record<string, number | null> = {};
      for (const key of ["nwc", "dscr", "icr"]) {
        const m = creditEngine?.[key];
        if (m?.input_values) {
          for (const [k, v] of Object.entries(m.input_values)) {
            if (typeof v === "number") inputs[k] = v;
          }
        }
      }
      const r = await runStressTest(inputs, deltas);
      setResult(r);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Stress test thất bại");
    }
  }

  return (
    <div className="bg-white rounded-lg shadow p-6 space-y-3">
      <h2 className="text-lg font-semibold text-msb-navy">Stress Test (kịch bản giả định)</h2>
      <p className="text-xs text-gray-500">
        Đây là kịch bản giả định do cán bộ nhập, không phải dự báo tài chính chắc chắn.
      </p>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {(Object.keys(deltas) as Array<keyof StressTestState>).map((key) => (
          <div key={key}>
            <label className="block text-xs text-gray-500 mb-1">{key} (%)</label>
            <input
              type="number" className="w-full border rounded px-2 py-1 text-sm"
              value={deltas[key]}
              onChange={(e) => setDeltas((prev) => ({ ...prev, [key]: Number(e.target.value) }))}
            />
          </div>
        ))}
      </div>
      <button onClick={handleRun} className="bg-msb-navy text-white text-sm font-semibold px-3 py-1.5 rounded">
        Chạy kịch bản
      </button>
      {error && <p className="text-sm text-red-600">{error}</p>}
      {result && (
        <div className="text-sm grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2 border-t">
          {Object.entries(result.after).map(([key, after]) => (
            <div key={key}>
              <p className="text-gray-500">{key}</p>
              <p>Trước: {result.before[key]?.value ?? "—"} → Sau: {after.value ?? "—"}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

Insert into `EbResultPanel`'s return, after `<DocumentPanel .../>`:

```tsx
      <CrossSellSection opportunities={result.opportunities ?? []} />
      <AiInsightSection why={result.why ?? []} creditMemo={result.credit_memo} />
      <StressTestPanel creditEngine={result.credit_engine as Record<string, MetricValue> | undefined} />

      {result.export_available && (
        <div className="bg-white rounded-lg shadow p-6">
          <button
            onClick={async () => {
              try {
                const blob = await exportMb02(result);
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = "to-trinh-mb02-du-thao.docx";
                a.click();
                URL.revokeObjectURL(url);
              } catch (err) {
                alert(err instanceof Error ? err.message : "Xuất tờ trình thất bại.");
              }
            }}
            className="border border-msb-navy text-msb-navy font-semibold px-4 py-2 rounded"
          >
            Soạn tờ trình MB02a
          </button>
        </div>
      )}
```

- [ ] **Step 2: Verify it compiles**

Run: `cd web && npm run build`
Expected: `✓ Compiled successfully`

- [ ] **Step 3: Commit**

```bash
git add web/components/EbResultPanel.tsx
git commit -m "feat(web): add EB cross-sell cards, AI Insight, Stress Test, and MB02a export"
```

---

## Task 27: Wire EbResultPanel into the app; add manual inputs for the 4th metric

**Files:**
- Modify: `web/app/page.tsx`
- Modify: `web/components/AssessmentForm.tsx`

**Interfaces:**
- Consumes: `EbResultPanel` (Task 26).

- [ ] **Step 1: Route EB to the new panel**

In `web/app/page.tsx`, change:

```tsx
{result && (tab === "crosssell" ? <CrossSellPanel result={result} /> : <ResultPanel result={result} />)}
```

to:

```tsx
{result && tab === "crosssell" && <CrossSellPanel result={result} />}
{result && tab === "eb" && <EbResultPanel result={result} />}
{result && tab === "rb" && <ResultPanel result={result} />}
```

and add the import at the top:

```tsx
import EbResultPanel from "@/components/EbResultPanel";
```

- [ ] **Step 2: Add EB's optional manual-input fields to the form**

In `web/components/AssessmentForm.tsx`, add a new fields array and state, mirroring the existing `CROSSSELL_FIELDS` pattern:

```tsx
const EB_FIELDS: Array<{ key: string; label: string }> = [
  { key: "proposed_limit_vnd", label: "Hạn mức đề xuất cho hợp đồng (VND)" },
  { key: "eligible_contract_value_vnd", label: "Giá trị hợp đồng đủ điều kiện (VND)" },
];
```

Add state:

```tsx
const [ebFields, setEbFields] = useState<Record<string, string>>({});
```

Update `handleSubmit`'s `runAssessment` call:

```tsx
const result = await runAssessment(
  agentType,
  customerName,
  taxId,
  files,
  agentType === "crosssell" ? crosssellFields : agentType === "eb" ? ebFields : undefined
);
```

Add the optional-fields block (after the existing `{agentType === "crosssell" && (...)}` block):

```tsx
{agentType === "eb" && (
  <div className="border-t pt-4 space-y-3">
    <p className="text-sm text-gray-500">
      Số liệu bổ sung (tùy chọn) — dùng để tính tỷ lệ tài trợ hợp đồng đầu ra. Để trống nếu chưa có.
    </p>
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
      {EB_FIELDS.map((f) => (
        <div key={f.key}>
          <label className="block text-xs font-medium text-msb-navy mb-1">{f.label}</label>
          <input
            type="number"
            className="w-full border rounded px-3 py-2 text-sm"
            value={ebFields[f.key] ?? ""}
            onChange={(e) => setEbFields((prev) => ({ ...prev, [f.key]: e.target.value }))}
          />
        </div>
      ))}
    </div>
  </div>
)}
```

- [ ] **Step 3: Verify it compiles and renders**

Run: `cd web && npm run build`
Expected: `✓ Compiled successfully`

Then run the local static-export screenshot check (same pattern used earlier in this session):
```bash
cd web && npm run build
cd out && python3 -m http.server 8899 &
NODE_PATH=/opt/node22/lib/node_modules node /tmp/screenshot_eb.js  # navigate to the EB tab, screenshot
```
Expected: the EB tab shows the case header, 11-row overview table, 4 metric cards, grouped risk flags, document panel, cross-sell section, AI Insight, and Stress Test panel — all readable, no raw `undefined`/`null` text leaking into the page (every render path already guards on `?? "—"`/`"Chưa có dữ liệu"`).

- [ ] **Step 4: Commit**

```bash
git add web/app/page.tsx web/components/AssessmentForm.tsx
git commit -m "feat(web): route EB tab to the new evidence-backed result panel"
```

---

## Final verification (after Task 27)

- [ ] Run `/usr/local/bin/python -m pytest -q` — full backend suite green.
- [ ] Run `cd web && npm run build` — frontend compiles clean.
- [ ] Push to `claude/pensive-hamilton-tu2cdx`, wait for CI (`Deploy to GreenNode AgentBase`) to report `success`.
- [ ] Against the live endpoint, POST `/api/eb/assess` with a real multi-document bundle and confirm: `overview` has 11 rows, at least one `EvidenceRef` resolves via `GET /api/eb/files/{case_id}/{file_id}`, `credit_engine.output_contract_financing_ratio` is present, `opportunities` is `[]` or populated depending on whether a statement was included, and `/api/eb/export` produces a docx whose overview section matches the JSON.
