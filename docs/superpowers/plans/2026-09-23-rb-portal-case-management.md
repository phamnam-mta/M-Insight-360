# RB Portal Case-Management Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current one-shot RB assess flow with a case-based,
multi-tab RB Portal (customer/legal/income/loan/collateral/other data entry,
document upload with checklist, deterministic assessment reused from the
existing credit engine, a Summary tab matching the reference layout, and a
Word export against the real MB01A QT.RR.038 template).

**Architecture:** New backend module `app/agents/rb_portal/` persists case
data section-by-section in SQLite and re-wires the existing (unmodified)
`app/agents/rb/credit_engine.py` / `risk_flags.py` / `readiness.py` to read
from persisted case data instead of one-shot document extraction. New
frontend `web/components/rb-portal/` replaces the RB tab's current
`AssessmentForm`/`ResultPanel` rendering entirely. No login/auth.

**Tech Stack:** FastAPI, SQLite (`app/storage/db.py`), python-docx, Next.js
14 + TypeScript + Tailwind (existing stack, no new dependencies).

**Spec:** `docs/superpowers/specs/2026-09-23-rb-portal-case-management-design.md`

## Global Constraints

- No login/auth/SSO — every endpoint is open, `actor` in audit rows is the
  literal string `"RM"`.
- Never fabricate data: missing metric inputs return `Metric.need_more_data(...)`
  (existing type in `app/engine/core/types.py`), never `0` or a guessed value.
  Missing Word-export fields are left blank, never `"N/A"`/`"chưa có"` text
  baked into the template (that convention is for JSON API responses, not the
  legal document).
- No APPROVE/REJECT anywhere — recommendation values are exactly
  `PRELIMINARY_READY`, `PRELIMINARY_READY_WITH_CONDITIONS`,
  `INSUFFICIENT_DATA`, `MANUAL_REVIEW_REQUIRED` (spec's Nguyên tắc nghiệp vụ).
- AI Insight (`generate_narrative`) failures must never break the
  preliminary/full-assessment response — same `narrative_budget_exceeded`
  pattern already used by `app/agents/eb/router.py` and `app/agents/rb/router.py`.
- All new backend endpoints live under prefix `/api/rb-portal` — never reuse
  `/api/rb` (that stays mounted for its own existing tests until this plan's
  final task removes the frontend's only caller of it).
- Reuse existing shared frontend components (`web/components/shared/MetricCard.tsx`,
  `RiskFlagsSection.tsx`, `AiInsightSection.tsx`, `SectionHeader.tsx`, `InfoBar.tsx`)
  rather than rewriting equivalents.

## Review Focus

- Case created but Income tab never filled (`income_json` is `NULL`) — the
  tax-declaration gate must read as "not yet determined", not silently
  `False` (which would wrongly let a business-income case pass the checklist).
- A document is uploaded before any other section exists on the case —
  upload must not 500; `category` is a required form field with no default.
- `/full-assessment` is called while `mandatory_check.missing` is non-empty —
  must return a clear `INSUFFICIENT_DATA`-style response and NOT silently run
  the engine anyway (full vs preliminary is exactly this gate).
- `/preliminary-assessment` called twice on the same case — must append a
  new row to `rb_case_assessments` (version N+1), never overwrite version N,
  since the History tab depends on every run being kept.
- `/export/mb01a` called on a case where loan/collateral/income were never
  filled in — must return a valid, openable `.docx` with those form regions
  left blank, not raise, not write placeholder text into the legal document.

---

## Task 1: Persistence layer — schema + repository

**Files:**
- Modify: `app/storage/db.py` (append 4 tables to `SCHEMA`)
- Create: `app/storage/rb_case_repository.py`
- Test: `tests/test_storage_rb_case_repository.py`

**Interfaces:**
- Produces: `create_case(db_path, case_id, customer_name, tax_id) -> None`,
  `get_case(db_path, case_id) -> dict | None`, `list_cases(db_path, limit=20) -> list[dict]`,
  `update_case_section(db_path, case_id, section, data) -> None`,
  `update_case_status(db_path, case_id, status) -> None`,
  `add_document(db_path, case_id, file_id, filename, category, document_type, content_type, size_bytes, storage_path) -> int`,
  `update_document_status(db_path, case_id, file_id, status) -> None`,
  `list_documents(db_path, case_id) -> list[dict]`,
  `save_assessment_version(db_path, case_id, kind, computed) -> int`,
  `list_assessment_versions(db_path, case_id) -> list[dict]`,
  `log_audit(db_path, case_id, action, detail="") -> None`.
  `section` is one of `"customer"|"legal"|"income"|"loan"|"collateral"|"other"`.
  A case dict from `get_case`/`list_cases` has keys `case_id`, `status`,
  `customer`, `legal`, `income`, `loan`, `collateral`, `other` (each `dict | None`),
  `created_at`, `updated_at`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_storage_rb_case_repository.py
from app.storage.db import init_db
from app.storage.rb_case_repository import (
    add_document, create_case, get_case, list_assessment_versions, list_cases,
    list_documents, log_audit, save_assessment_version, update_case_section,
    update_case_status, update_document_status,
)


def test_create_and_get_case(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    create_case(db_path, "RB-0100000001-abc123", "NGUYEN VAN A", "0100000001")
    case = get_case(db_path, "RB-0100000001-abc123")
    assert case["case_id"] == "RB-0100000001-abc123"
    assert case["status"] == "RECEIVED"
    assert case["customer"] is None
    assert case["legal"] is None


def test_get_case_returns_none_for_unknown_id(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    assert get_case(db_path, "RB-NOPE") is None


def test_update_case_section_persists_and_merges(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    create_case(db_path, "RB-1", "A", "111")
    update_case_section(db_path, "RB-1", "customer", {"full_name": "A", "gender": "male"})
    case = get_case(db_path, "RB-1")
    assert case["customer"] == {"full_name": "A", "gender": "male"}

    update_case_section(db_path, "RB-1", "income", {"source_type": "business"})
    case = get_case(db_path, "RB-1")
    assert case["income"] == {"source_type": "business"}
    # customer section from the earlier PATCH must still be there
    assert case["customer"] == {"full_name": "A", "gender": "male"}


def test_update_case_status_persists(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    create_case(db_path, "RB-1", "A", "111")
    update_case_status(db_path, "RB-1", "DOCS_ANALYZED")
    assert get_case(db_path, "RB-1")["status"] == "DOCS_ANALYZED"


def test_update_case_section_rejects_unknown_section(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    create_case(db_path, "RB-1", "A", "111")
    try:
        update_case_section(db_path, "RB-1", "bogus", {})
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_list_cases_orders_newest_first(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    create_case(db_path, "RB-1", "A", "111")
    create_case(db_path, "RB-2", "B", "222")
    cases = list_cases(db_path)
    assert [c["case_id"] for c in cases] == ["RB-2", "RB-1"]


def test_add_and_list_documents(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    create_case(db_path, "RB-1", "A", "111")
    doc_id = add_document(
        db_path, "RB-1", "file1", "cccd.pdf", "LEGAL", "LEGAL_IDENTITY",
        "application/pdf", 1024, "/data/RB-1/file1__cccd.pdf",
    )
    assert doc_id > 0
    docs = list_documents(db_path, "RB-1")
    assert len(docs) == 1
    assert docs[0]["filename"] == "cccd.pdf"
    assert docs[0]["status"] == "UPLOADED"

    update_document_status(db_path, "RB-1", "file1", "EXTRACTED")
    docs = list_documents(db_path, "RB-1")
    assert docs[0]["status"] == "EXTRACTED"


def test_save_and_list_assessment_versions_increment(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    create_case(db_path, "RB-1", "A", "111")
    v1 = save_assessment_version(db_path, "RB-1", "PRELIMINARY", {"recommendation": "INSUFFICIENT_DATA"})
    v2 = save_assessment_version(db_path, "RB-1", "PRELIMINARY", {"recommendation": "PRELIMINARY_READY"})
    assert v2 == v1 + 1
    versions = list_assessment_versions(db_path, "RB-1")
    assert [v["version"] for v in versions] == [2, 1]
    assert versions[0]["computed"]["recommendation"] == "PRELIMINARY_READY"


def test_log_audit_records_action(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    create_case(db_path, "RB-1", "A", "111")
    log_audit(db_path, "RB-1", "CASE_CREATED", "customer=A")
    from app.storage.db import get_connection
    conn = get_connection(db_path)
    rows = conn.execute("SELECT * FROM rb_case_audit WHERE case_id = 'RB-1'").fetchall()
    conn.close()
    assert len(rows) == 1
    assert rows[0]["actor"] == "RM"
    assert rows[0]["action"] == "CASE_CREATED"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/local/bin/python -m pytest tests/test_storage_rb_case_repository.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.storage.rb_case_repository'`

- [ ] **Step 3: Add the 4 tables to the schema**

In `app/storage/db.py`, append to the `SCHEMA` string (before the closing
`"""`), right after the existing `eb_stress_scenarios` table:

```sql
CREATE TABLE IF NOT EXISTS rb_cases (
    case_id TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'RECEIVED',
    customer_name TEXT NOT NULL,
    tax_id TEXT NOT NULL,
    customer_json TEXT,
    legal_json TEXT,
    income_json TEXT,
    loan_json TEXT,
    collateral_json TEXT,
    other_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS rb_case_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id TEXT NOT NULL,
    file_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    category TEXT NOT NULL,
    document_type TEXT,
    status TEXT NOT NULL DEFAULT 'UPLOADED',
    content_type TEXT,
    size_bytes INTEGER NOT NULL,
    storage_path TEXT NOT NULL,
    uploaded_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS rb_case_assessments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    kind TEXT NOT NULL,
    computed_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS rb_case_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id TEXT NOT NULL,
    actor TEXT NOT NULL DEFAULT 'RM',
    action TEXT NOT NULL,
    detail TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

- [ ] **Step 4: Write the repository module**

```python
# app/storage/rb_case_repository.py
import json

from .db import get_connection

_SECTIONS = {"customer", "legal", "income", "loan", "collateral", "other"}


def create_case(db_path: str, case_id: str, customer_name: str, tax_id: str) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT INTO rb_cases (case_id, customer_name, tax_id) VALUES (?, ?, ?)",
            (case_id, customer_name, tax_id),
        )
        conn.commit()
    finally:
        conn.close()


def _row_to_case(row) -> dict:
    return {
        "case_id": row["case_id"],
        "status": row["status"],
        "customer_name": row["customer_name"],
        "tax_id": row["tax_id"],
        "customer": json.loads(row["customer_json"]) if row["customer_json"] else None,
        "legal": json.loads(row["legal_json"]) if row["legal_json"] else None,
        "income": json.loads(row["income_json"]) if row["income_json"] else None,
        "loan": json.loads(row["loan_json"]) if row["loan_json"] else None,
        "collateral": json.loads(row["collateral_json"]) if row["collateral_json"] else None,
        "other": json.loads(row["other_json"]) if row["other_json"] else None,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def get_case(db_path: str, case_id: str) -> dict | None:
    conn = get_connection(db_path)
    try:
        row = conn.execute("SELECT * FROM rb_cases WHERE case_id = ?", (case_id,)).fetchone()
        return _row_to_case(row) if row else None
    finally:
        conn.close()


def list_cases(db_path: str, limit: int = 20) -> list[dict]:
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM rb_cases ORDER BY created_at DESC, rowid DESC LIMIT ?", (limit,)
        ).fetchall()
        return [_row_to_case(r) for r in rows]
    finally:
        conn.close()


def update_case_status(db_path: str, case_id: str, status: str) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute(
            "UPDATE rb_cases SET status = ?, updated_at = datetime('now') WHERE case_id = ?",
            (status, case_id),
        )
        conn.commit()
    finally:
        conn.close()


def update_case_section(db_path: str, case_id: str, section: str, data: dict) -> None:
    if section not in _SECTIONS:
        raise ValueError(f"unknown section: {section}")
    conn = get_connection(db_path)
    try:
        conn.execute(
            f"UPDATE rb_cases SET {section}_json = ?, updated_at = datetime('now') WHERE case_id = ?",
            (json.dumps(data, ensure_ascii=False), case_id),
        )
        conn.commit()
    finally:
        conn.close()


def add_document(
    db_path: str, case_id: str, file_id: str, filename: str, category: str,
    document_type: str | None, content_type: str | None, size_bytes: int, storage_path: str,
) -> int:
    conn = get_connection(db_path)
    try:
        cur = conn.execute(
            "INSERT INTO rb_case_documents "
            "(case_id, file_id, filename, category, document_type, content_type, size_bytes, storage_path) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (case_id, file_id, filename, category, document_type, content_type, size_bytes, storage_path),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_document_status(db_path: str, case_id: str, file_id: str, status: str) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute(
            "UPDATE rb_case_documents SET status = ? WHERE case_id = ? AND file_id = ?",
            (status, case_id, file_id),
        )
        conn.commit()
    finally:
        conn.close()


def list_documents(db_path: str, case_id: str) -> list[dict]:
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM rb_case_documents WHERE case_id = ? ORDER BY uploaded_at", (case_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def save_assessment_version(db_path: str, case_id: str, kind: str, computed: dict) -> int:
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT MAX(version) AS m FROM rb_case_assessments WHERE case_id = ?", (case_id,)
        ).fetchone()
        next_version = (row["m"] or 0) + 1
        conn.execute(
            "INSERT INTO rb_case_assessments (case_id, version, kind, computed_json) VALUES (?, ?, ?, ?)",
            (case_id, next_version, kind, json.dumps(computed, ensure_ascii=False)),
        )
        conn.commit()
        return next_version
    finally:
        conn.close()


def list_assessment_versions(db_path: str, case_id: str) -> list[dict]:
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM rb_case_assessments WHERE case_id = ? ORDER BY version DESC", (case_id,)
        ).fetchall()
        return [
            {"version": r["version"], "kind": r["kind"], "computed": json.loads(r["computed_json"]),
             "created_at": r["created_at"]}
            for r in rows
        ]
    finally:
        conn.close()


def log_audit(db_path: str, case_id: str, action: str, detail: str = "") -> None:
    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT INTO rb_case_audit (case_id, action, detail) VALUES (?, ?, ?)",
            (case_id, action, detail),
        )
        conn.commit()
    finally:
        conn.close()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `/usr/local/bin/python -m pytest tests/test_storage_rb_case_repository.py -v`
Expected: 9/9 PASS

- [ ] **Step 6: Run full backend suite**

Run: `/usr/local/bin/python -m pytest -q`
Expected: all pass (503 baseline + 9 new = 512)

- [ ] **Step 7: Commit**

```bash
git add app/storage/db.py app/storage/rb_case_repository.py tests/test_storage_rb_case_repository.py
git commit -m "feat(rb-portal): add case persistence schema and repository"
```

---

## Task 2: Section dataclasses

**Files:**
- Create: `app/agents/rb_portal/__init__.py` (empty)
- Create: `app/agents/rb_portal/models.py`
- Test: `tests/agents/rb_portal/__init__.py` (empty)
- Test: `tests/agents/rb_portal/test_models.py`

**Interfaces:**
- Produces: `RbCustomer`, `RbLegal`, `RbIncome`, `RbLoan`, `RbCollateral`,
  `RbOther` dataclasses (all fields `X | None = None`, plain `@dataclass`,
  `asdict()`-safe). `RbIncome.source_type: str | None` takes one of
  `"salary" | "business" | "self_employed" | "household_business" | None`.
  `RbCollateral` holds a **list** of asset dicts (`items: list[dict]`), since
  the reference form supports multiple TSBĐ rows.
- Consumes: nothing (leaf module).

- [ ] **Step 1: Write the failing test**

```python
# tests/agents/rb_portal/test_models.py
from dataclasses import asdict

from app.agents.rb_portal.models import (
    RbCollateral, RbCustomer, RbIncome, RbLegal, RbLoan, RbOther,
)


def test_rb_customer_all_fields_default_to_none():
    c = RbCustomer()
    d = asdict(c)
    assert d["full_name"] is None
    assert d["gender"] is None
    assert d["marital_status"] is None


def test_rb_customer_round_trips_through_asdict():
    c = RbCustomer(full_name="NGUYEN VAN A", gender="male", tax_id="0100000001")
    assert asdict(c)["full_name"] == "NGUYEN VAN A"


def test_rb_income_source_type_field():
    i = RbIncome(source_type="business", business_name="Quan Com A")
    assert asdict(i)["source_type"] == "business"


def test_rb_collateral_items_default_to_empty_list():
    col = RbCollateral()
    assert asdict(col)["items"] == []


def test_rb_legal_and_loan_and_other_construct_empty():
    assert asdict(RbLegal())["id_type"] is None
    assert asdict(RbLoan())["product"] is None
    assert asdict(RbOther())["notes"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/usr/local/bin/python -m pytest tests/agents/rb_portal/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.agents.rb_portal'`

- [ ] **Step 3: Write the models**

```python
# app/agents/rb_portal/models.py
from dataclasses import dataclass, field


@dataclass
class RbCustomer:
    full_name: str | None = None
    gender: str | None = None  # "male" | "female"
    date_of_birth: str | None = None  # ISO "YYYY-MM-DD"
    nationality: str | None = None
    id_number: str | None = None
    tax_id: str | None = None
    permanent_address: str | None = None
    temporary_address: str | None = None
    contact_address: str | None = None
    phone_mobile: str | None = None
    phone_home: str | None = None
    email: str | None = None
    marital_status: str | None = None  # "single"|"married"|"divorced"|"widowed"
    education_level: str | None = None


@dataclass
class RbLegal:
    id_type: str | None = None  # "CCCD" | "CMND" | "PASSPORT"
    id_issue_date: str | None = None
    id_issue_place: str | None = None
    business_registration_number: str | None = None
    business_registration_issue_date: str | None = None
    business_registration_issue_place: str | None = None


@dataclass
class RbIncome:
    source_type: str | None = None  # salary|business|self_employed|household_business
    # Nguồn thu từ kinh doanh
    business_name: str | None = None
    business_sector: str | None = None
    business_years: float | None = None
    business_address: str | None = None
    # Nguồn thu từ lương
    employer_name: str | None = None
    employer_address: str | None = None
    position: str | None = None
    employment_years: float | None = None
    # Tài chính (khớp mục "1. Thu nhập / 2. Chi phí" của form MB01A)
    income_salary_vnd: float | None = None
    income_rental_vnd: float | None = None
    income_business_vnd: float | None = None
    income_guarantor_vnd: float | None = None
    expense_living_vnd: float | None = None
    expense_other_debt_vnd: float | None = None
    expense_other_vnd: float | None = None
    dependents_count: int | None = None
    tax_declaration_present: bool = False


@dataclass
class RbLoan:
    product: str | None = None  # "vay_von" — luồng vay vốn (khoản vay), phạm vi bản này
    purpose: str | None = None
    amount_vnd: float | None = None
    tenor_months: int | None = None
    annual_rate: float | None = None
    existing_monthly_obligation_vnd: float | None = None
    repayment_method: str | None = None


@dataclass
class RbCollateral:
    items: list[dict] = field(default_factory=list)
    # mỗi item: {"asset_type": str, "ownership_status": str, "estimated_value_vnd": float}


@dataclass
class RbOther:
    notes: str | None = None
    existing_credit_relationships: list[dict] = field(default_factory=list)
    # mỗi item: {"institution": str, "credit_type": str, "amount_vnd": float,
    #            "outstanding_vnd": float, "monthly_payment_vnd": float}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/usr/local/bin/python -m pytest tests/agents/rb_portal/test_models.py -v`
Expected: 5/5 PASS

- [ ] **Step 5: Commit**

```bash
git add app/agents/rb_portal/ tests/agents/rb_portal/
git commit -m "feat(rb-portal): add case section dataclasses"
```

---

## Task 3: mandatory_check.py — checklist + tax-declaration gate

**Files:**
- Create: `app/agents/rb_portal/mandatory_check.py`
- Test: `tests/agents/rb_portal/test_mandatory_check.py`

**Interfaces:**
- Consumes: `RbCustomer, RbLegal, RbIncome, RbLoan` from Task 2 (as plain
  `dict | None`, exactly the shape `rb_case_repository.get_case()` returns —
  this module never imports the dataclasses, it reads case dicts directly,
  since that is what the router will have on hand).
- Produces: `check_mandatory(customer: dict | None, legal: dict | None, income: dict | None, loan: dict | None, documents: list[dict]) -> dict`
  returning
  `{"legal": [...missing item names...], "income": [...], "loan": [...],
    "other": [...], "tax_declaration_required": bool | None,
    "tax_declaration_present": bool, "missing": [...all missing, flattened...]}`.
  `tax_declaration_required` is `None` (not `True`/`False`) when
  `income` itself is `None` — Review Focus item 1: an unset Income tab must
  read as "not yet determined", never as a silent `False` that would let a
  business-income case wrongly pass.

- [ ] **Step 1: Write the failing tests**

```python
# tests/agents/rb_portal/test_mandatory_check.py
from app.agents.rb_portal.mandatory_check import check_mandatory


def test_all_sections_missing_reports_full_checklist():
    result = check_mandatory(customer=None, legal=None, income=None, loan=None, documents=[])
    assert "legal_identity" in result["legal"]
    assert "loan_request" in result["loan"]
    assert result["tax_declaration_required"] is None
    assert result["tax_declaration_present"] is False
    assert result["missing"]  # non-empty


def test_tax_declaration_required_for_business_income_without_document():
    result = check_mandatory(
        customer={"full_name": "A"}, legal={"id_type": "CCCD"},
        income={"source_type": "business", "tax_declaration_present": False},
        loan={"product": "vay_von", "purpose": "kinh doanh"}, documents=[],
    )
    assert result["tax_declaration_required"] is True
    assert result["tax_declaration_present"] is False
    assert "tax_declaration" in result["income"]
    assert "tax_declaration" in result["missing"]


def test_tax_declaration_not_required_for_salary_income():
    result = check_mandatory(
        customer={"full_name": "A"}, legal={"id_type": "CCCD"},
        income={"source_type": "salary"},
        loan={"product": "vay_von", "purpose": "tieu dung"}, documents=[],
    )
    assert result["tax_declaration_required"] is False
    assert "tax_declaration" not in result["income"]


def test_tax_declaration_satisfied_when_present_flag_true():
    result = check_mandatory(
        customer={"full_name": "A"}, legal={"id_type": "CCCD"},
        income={"source_type": "household_business", "tax_declaration_present": True},
        loan={"product": "vay_von", "purpose": "x"}, documents=[],
    )
    assert result["tax_declaration_required"] is True
    assert result["tax_declaration_present"] is True
    assert "tax_declaration" not in result["income"]
    assert "tax_declaration" not in result["missing"]


def test_fully_filled_case_has_empty_missing_list():
    result = check_mandatory(
        customer={"full_name": "A"}, legal={"id_type": "CCCD"},
        income={"source_type": "salary", "employer_name": "Cong ty B"},
        loan={"product": "vay_von", "purpose": "tieu dung", "amount_vnd": 100_000_000},
        documents=[],
    )
    assert result["missing"] == []
    assert result["legal"] == []
    assert result["income"] == []
    assert result["loan"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/local/bin/python -m pytest tests/agents/rb_portal/test_mandatory_check.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write the module**

```python
# app/agents/rb_portal/mandatory_check.py

_BUSINESS_SOURCE_TYPES = {"business", "self_employed", "household_business"}


def check_mandatory(
    customer: dict | None, legal: dict | None, income: dict | None,
    loan: dict | None, documents: list[dict],
) -> dict:
    legal_missing: list[str] = []
    if not customer or not customer.get("full_name"):
        legal_missing.append("legal_identity")
    if not legal or not legal.get("id_type"):
        legal_missing.append("id_document")

    income_missing: list[str] = []
    tax_declaration_required: bool | None
    tax_declaration_present = bool(income and income.get("tax_declaration_present"))
    if income is None:
        income_missing.append("income_section")
        tax_declaration_required = None
    else:
        source_type = income.get("source_type")
        if not source_type:
            income_missing.append("income_source_type")
        tax_declaration_required = source_type in _BUSINESS_SOURCE_TYPES
        if tax_declaration_required and not tax_declaration_present:
            income_missing.append("tax_declaration")

    loan_missing: list[str] = []
    if not loan or not loan.get("product"):
        loan_missing.append("loan_request")
    if not loan or not loan.get("purpose"):
        loan_missing.append("loan_purpose")

    other_missing: list[str] = []

    missing = legal_missing + income_missing + loan_missing + other_missing
    return {
        "legal": legal_missing,
        "income": income_missing,
        "loan": loan_missing,
        "other": other_missing,
        "tax_declaration_required": tax_declaration_required,
        "tax_declaration_present": tax_declaration_present,
        "missing": missing,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/usr/local/bin/python -m pytest tests/agents/rb_portal/test_mandatory_check.py -v`
Expected: 5/5 PASS

- [ ] **Step 5: Commit**

```bash
git add app/agents/rb_portal/mandatory_check.py tests/agents/rb_portal/test_mandatory_check.py
git commit -m "feat(rb-portal): add mandatory-document checklist with tax-declaration gate"
```

---

## Task 4: assessment.py — bridge case data into the existing credit engine

**Files:**
- Create: `app/agents/rb_portal/assessment.py`
- Test: `tests/agents/rb_portal/test_assessment.py`

**Interfaces:**
- Consumes: `app.agents.rb.loan_inputs.RbLoanInputs` (existing dataclass —
  fields `avg_monthly_revenue_vnd, eligible_income_margin, gross_monthly_income_vnd,
  existing_monthly_obligation_vnd, loan_amount_vnd, tenor_months, annual_rate,
  collateral_value_vnd`), `app.agents.rb.credit_engine.run_credit_engine(inputs, existing_monthly_obligation_vnd) -> dict[str, Metric]`,
  `app.agents.rb.risk_flags.compute_risk_flags(mandatory_check, tax_id_result, dti_metric, classified_documents=None) -> list[RuleResult]`,
  `app.agents.rb.readiness.determine_readiness(mandatory_check, risk_flags) -> tuple[str, str]`
  (all unmodified — read `app/agents/rb/credit_engine.py`, `risk_flags.py`,
  `readiness.py` before writing this task if anything is unclear), and
  `app.agents.rb_portal.mandatory_check.check_mandatory` from Task 3.
- Produces: `build_loan_inputs(case: dict) -> RbLoanInputs`,
  `run_case_assessment(case: dict, documents: list[dict]) -> dict` — the
  full `computed` dict for a case (credit_engine, risk_flags, missing_data,
  credit_readiness, recommendation — same key names the EB/RB routers
  already use elsewhere in this codebase, so the frontend's existing
  `MetricCard`/`RiskFlagsSection` components work unmodified).

- [ ] **Step 1: Write the failing tests**

```python
# tests/agents/rb_portal/test_assessment.py
from app.agents.rb_portal.assessment import build_loan_inputs, run_case_assessment


def test_build_loan_inputs_from_business_income_case():
    case = {
        "income": {"source_type": "business", "income_business_vnd": 30_000_000},
        "loan": {"amount_vnd": 200_000_000, "tenor_months": 24, "annual_rate": 0.12,
                  "existing_monthly_obligation_vnd": 2_000_000},
        "collateral": {"items": [{"estimated_value_vnd": 500_000_000}]},
    }
    inputs = build_loan_inputs(case)
    assert inputs.avg_monthly_revenue_vnd == 30_000_000
    assert inputs.loan_amount_vnd == 200_000_000
    assert inputs.tenor_months == 24
    assert inputs.annual_rate == 0.12
    assert inputs.existing_monthly_obligation_vnd == 2_000_000
    assert inputs.collateral_value_vnd == 500_000_000


def test_build_loan_inputs_from_salary_income_case_uses_gross_income():
    case = {
        "income": {"source_type": "salary", "income_salary_vnd": 25_000_000},
        "loan": {"amount_vnd": 100_000_000, "tenor_months": 12, "annual_rate": 0.1},
        "collateral": None,
    }
    inputs = build_loan_inputs(case)
    assert inputs.gross_monthly_income_vnd == 25_000_000
    assert inputs.avg_monthly_revenue_vnd is None
    assert inputs.collateral_value_vnd is None


def test_build_loan_inputs_missing_sections_yields_all_none():
    inputs = build_loan_inputs({"income": None, "loan": None, "collateral": None})
    assert inputs.loan_amount_vnd is None
    assert inputs.avg_monthly_revenue_vnd is None


def test_run_case_assessment_insufficient_data_when_mandatory_missing():
    case = {"customer": None, "legal": None, "income": None, "loan": None, "collateral": None}
    computed = run_case_assessment(case, documents=[])
    assert computed["credit_readiness"] == "INSUFFICIENT_DATA"
    assert computed["missing_data"]
    assert "credit_engine" in computed
    assert "risk_flags" in computed


def test_run_case_assessment_computes_dti_when_data_complete():
    case = {
        "customer": {"full_name": "A"}, "legal": {"id_type": "CCCD"},
        "income": {"source_type": "salary", "income_salary_vnd": 25_000_000},
        "loan": {"product": "vay_von", "purpose": "tieu dung", "amount_vnd": 100_000_000,
                  "tenor_months": 12, "annual_rate": 0.1, "existing_monthly_obligation_vnd": 1_000_000},
        "collateral": None,
    }
    computed = run_case_assessment(case, documents=[])
    assert computed["credit_engine"]["dti"]["status"] == "OK"
    assert computed["credit_readiness"] in (
        "PRELIMINARY_READY", "PRELIMINARY_READY_WITH_CONDITIONS", "MANUAL_REVIEW_REQUIRED",
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/local/bin/python -m pytest tests/agents/rb_portal/test_assessment.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write the module**

```python
# app/agents/rb_portal/assessment.py
from dataclasses import asdict

from app.agents.rb.credit_engine import run_credit_engine
from app.agents.rb.loan_inputs import RbLoanInputs
from app.agents.rb.readiness import determine_readiness
from app.agents.rb.risk_flags import compute_risk_flags
from app.engine.core.types import RuleResult

from .mandatory_check import check_mandatory

# Same demo value the old one-shot RB flow used (app/agents/rb/loan_inputs.py
# default) — kept identical so eligible-income math doesn't silently drift
# between the two flows during the cutover.
_ELIGIBLE_INCOME_MARGIN = 0.08


def build_loan_inputs(case: dict) -> RbLoanInputs:
    income = case.get("income") or {}
    loan = case.get("loan") or {}
    collateral = case.get("collateral") or {}

    source_type = income.get("source_type")
    avg_monthly_revenue_vnd = income.get("income_business_vnd") if source_type in (
        "business", "self_employed", "household_business"
    ) else None
    gross_monthly_income_vnd = income.get("income_salary_vnd") if source_type == "salary" else None

    collateral_items = collateral.get("items") or []
    collateral_value_vnd = (
        sum(item.get("estimated_value_vnd") or 0 for item in collateral_items)
        if collateral_items else None
    )

    return RbLoanInputs(
        avg_monthly_revenue_vnd=avg_monthly_revenue_vnd,
        eligible_income_margin=_ELIGIBLE_INCOME_MARGIN,
        gross_monthly_income_vnd=gross_monthly_income_vnd,
        existing_monthly_obligation_vnd=loan.get("existing_monthly_obligation_vnd"),
        loan_amount_vnd=loan.get("amount_vnd"),
        tenor_months=loan.get("tenor_months"),
        annual_rate=loan.get("annual_rate"),
        collateral_value_vnd=collateral_value_vnd,
    )


def run_case_assessment(case: dict, documents: list[dict]) -> dict:
    mandatory = check_mandatory(
        case.get("customer"), case.get("legal"), case.get("income"), case.get("loan"), documents,
    )
    inputs = build_loan_inputs(case)
    engine_metrics = run_credit_engine(inputs, inputs.existing_monthly_obligation_vnd)

    # RB Portal has no document-classification-confidence signal of its own
    # (documents are RM-categorized on upload, not AI-classified) and no
    # separate tax-id-mismatch check yet — pass a clean placeholder RuleResult
    # so compute_risk_flags's required positional arg is satisfied without
    # fabricating a finding.
    tax_id_result = RuleResult(rule_id="TAX_ID_MISMATCH", rule_name="Đối chiếu mã số thuế", status="CHƯA ĐÁNH GIÁ")
    risk_flags = compute_risk_flags(mandatory, tax_id_result, engine_metrics["dti"])

    if mandatory["missing"]:
        credit_readiness, recommendation = "INSUFFICIENT_DATA", "ADDITIONAL_DATA_REQUIRED"
    else:
        readiness, _old_recommendation = determine_readiness(mandatory, risk_flags)
        # Map the existing RB readiness vocabulary onto the RB Portal's own
        # (spec §"Nguyên tắc nghiệp vụ" forbids APPROVE/REJECT, and the brief's
        # exact vocabulary differs from the older one-shot flow's).
        credit_readiness = {
            "READY": "PRELIMINARY_READY",
            "READY_WITH_CONDITIONS": "PRELIMINARY_READY_WITH_CONDITIONS",
            "MANUAL_REVIEW_REQUIRED": "MANUAL_REVIEW_REQUIRED",
        }[readiness]
        recommendation = {
            "PRELIMINARY_READY": "PROCEED_FOR_HUMAN_REVIEW",
            "PRELIMINARY_READY_WITH_CONDITIONS": "PROCEED_WITH_CONDITIONS",
            "MANUAL_REVIEW_REQUIRED": "REQUIRES_CREDIT_OFFICER_REVIEW",
        }[credit_readiness]

    return {
        "credit_engine": {name: asdict(metric) for name, metric in engine_metrics.items()},
        "risk_flags": [
            {**asdict(flag), "impact": flag.comment} for flag in risk_flags
        ],
        "mandatory_check": mandatory,
        "missing_data": mandatory["missing"],
        "credit_readiness": credit_readiness,
        "recommendation": recommendation,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/usr/local/bin/python -m pytest tests/agents/rb_portal/test_assessment.py -v`
Expected: 5/5 PASS

- [ ] **Step 5: Run full backend suite**

Run: `/usr/local/bin/python -m pytest -q`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add app/agents/rb_portal/assessment.py tests/agents/rb_portal/test_assessment.py
git commit -m "feat(rb-portal): bridge case data into existing RB credit engine"
```

---

## Task 5: router.py — case CRUD endpoints

**Files:**
- Create: `app/agents/rb_portal/router.py`
- Test: `tests/agents/rb_portal/test_router.py`

**Interfaces:**
- Consumes: everything from Tasks 1–4 (`app.storage.rb_case_repository`,
  `app.agents.rb_portal.models`), `app.config.get_settings()`,
  `app.storage.db.init_db`.
- Produces: `router = APIRouter(prefix="/api/rb-portal", tags=["rb-portal"])`
  with `POST /cases`, `GET /cases`, `GET /cases/{case_id}`,
  `PATCH /cases/{case_id}/{section}` for `section` in
  `customer|legal|income|loan|collateral|other`. This task's router object
  is the one every later router task adds routes to — do not create a second
  `APIRouter()` instance in a later task.

- [ ] **Step 1: Write the failing tests**

```python
# tests/agents/rb_portal/test_router.py
from fastapi.testclient import TestClient

from app.main import app


def test_create_case_returns_case_id(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    from app.config import get_settings
    get_settings.cache_clear()
    client = TestClient(app)
    resp = client.post("/api/rb-portal/cases", json={"customer_name": "NGUYEN VAN A", "tax_id": "0100000001"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["case_id"].startswith("RB-0100000001-")


def test_get_case_after_create(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    from app.config import get_settings
    get_settings.cache_clear()
    client = TestClient(app)
    case_id = client.post("/api/rb-portal/cases", json={"customer_name": "A", "tax_id": "111"}).json()["case_id"]
    resp = client.get(f"/api/rb-portal/cases/{case_id}")
    assert resp.status_code == 200
    assert resp.json()["case_id"] == case_id
    assert resp.json()["customer"] is None


def test_get_case_404_for_unknown_id(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    from app.config import get_settings
    get_settings.cache_clear()
    client = TestClient(app)
    resp = client.get("/api/rb-portal/cases/RB-NOPE")
    assert resp.status_code == 404


def test_list_cases_returns_recent_first(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    from app.config import get_settings
    get_settings.cache_clear()
    client = TestClient(app)
    client.post("/api/rb-portal/cases", json={"customer_name": "A", "tax_id": "111"})
    client.post("/api/rb-portal/cases", json={"customer_name": "B", "tax_id": "222"})
    resp = client.get("/api/rb-portal/cases")
    assert resp.status_code == 200
    names = [c["customer_name"] for c in resp.json()["cases"]]
    assert names == ["B", "A"]


def test_patch_customer_section_persists(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    from app.config import get_settings
    get_settings.cache_clear()
    client = TestClient(app)
    case_id = client.post("/api/rb-portal/cases", json={"customer_name": "A", "tax_id": "111"}).json()["case_id"]
    resp = client.patch(f"/api/rb-portal/cases/{case_id}/customer", json={"full_name": "A", "gender": "male"})
    assert resp.status_code == 200
    case = client.get(f"/api/rb-portal/cases/{case_id}").json()
    assert case["customer"]["full_name"] == "A"


def test_patch_unknown_section_returns_404(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    from app.config import get_settings
    get_settings.cache_clear()
    client = TestClient(app)
    case_id = client.post("/api/rb-portal/cases", json={"customer_name": "A", "tax_id": "111"}).json()["case_id"]
    resp = client.patch(f"/api/rb-portal/cases/{case_id}/bogus", json={})
    assert resp.status_code == 404


def test_patch_on_unknown_case_returns_404(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    from app.config import get_settings
    get_settings.cache_clear()
    client = TestClient(app)
    resp = client.patch("/api/rb-portal/cases/RB-NOPE/customer", json={"full_name": "A"})
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/local/bin/python -m pytest tests/agents/rb_portal/test_router.py -v`
Expected: FAIL — `ModuleNotFoundError` (router.py doesn't exist; app.main doesn't mount it yet either, but that's Task 12 — these tests fail at import/collection until Task 12 wires the router into `app.main.app`, which is expected and resolves itself once Task 12 lands. To keep this task's tests genuinely RED→GREEN on their own, temporarily add `app.include_router(rb_portal_router)` to `app/main.py` as part of THIS task's Step 3, and leave it in place — Task 12 will only need to add the remaining sub-routers' imports, not a second `include_router` call.)

- [ ] **Step 3: Write the router (case CRUD) and mount it**

```python
# app/agents/rb_portal/router.py
import uuid

from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.storage.db import init_db
from app.storage.rb_case_repository import (
    create_case, get_case, list_cases, update_case_section,
)
from .mandatory_check import check_mandatory  # noqa: F401  (used by later tasks in this file)

router = APIRouter(prefix="/api/rb-portal", tags=["rb-portal"])

_VALID_SECTIONS = {"customer", "legal", "income", "loan", "collateral", "other"}


@router.post("/cases")
async def create_case_endpoint(payload: dict) -> dict:
    settings = get_settings()
    init_db(settings.db_path)
    customer_name = payload["customer_name"]
    tax_id = payload["tax_id"]
    case_id = f"RB-{tax_id}-{uuid.uuid4().hex[:8]}"
    create_case(settings.db_path, case_id, customer_name, tax_id)
    return {"case_id": case_id}


@router.get("/cases")
async def list_cases_endpoint(limit: int = 20) -> dict:
    settings = get_settings()
    init_db(settings.db_path)
    return {"cases": list_cases(settings.db_path, limit)}


@router.get("/cases/{case_id}")
async def get_case_endpoint(case_id: str) -> dict:
    settings = get_settings()
    init_db(settings.db_path)
    case = get_case(settings.db_path, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy hồ sơ")
    return case


@router.patch("/cases/{case_id}/{section}")
async def update_section_endpoint(case_id: str, section: str, payload: dict) -> dict:
    if section not in _VALID_SECTIONS:
        raise HTTPException(status_code=404, detail=f"Không có mục '{section}'")
    settings = get_settings()
    init_db(settings.db_path)
    if get_case(settings.db_path, case_id) is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy hồ sơ")
    update_case_section(settings.db_path, case_id, section, payload)
    return {"status": "ok"}
```

In `app/main.py`, add the import and `include_router` call next to the
existing three (`rb_router`, `eb_router`, `crosssell_router`):

```python
from .agents.rb_portal.router import router as rb_portal_router  # noqa: E402
...
app.include_router(rb_portal_router)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/usr/local/bin/python -m pytest tests/agents/rb_portal/test_router.py -v`
Expected: 7/7 PASS

- [ ] **Step 5: Run full backend suite**

Run: `/usr/local/bin/python -m pytest -q`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add app/agents/rb_portal/router.py app/main.py tests/agents/rb_portal/test_router.py
git commit -m "feat(rb-portal): add case CRUD endpoints"
```

---

## Task 6: router.py — document upload endpoints

**Files:**
- Modify: `app/agents/rb_portal/router.py` (append to the same `router`)
- Modify: `tests/agents/rb_portal/test_router.py` (append)

**Interfaces:**
- Consumes: `app.storage.files.save_case_file(base_dir, case_id, file_id, filename, content) -> str`,
  `app.storage.rb_case_repository.add_document(...)`/`list_documents(...)` (Task 1),
  `app.extraction.pipeline.extract_document(path, name, file_id=file_id)`,
  `app.agents.rb.document_classifier.classify_document(doc) -> tuple[str, float]`
  (both existing, unmodified — reused only to SUGGEST `document_type`, never
  to override the RM-chosen `category`).
- Produces: `POST /cases/{case_id}/documents` (multipart: `file`, form field
  `category` required, one of `LEGAL|INCOME|LOAN|COLLATERAL|OTHER`),
  `GET /cases/{case_id}/documents`.

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/agents/rb_portal/test_router.py
import io


def test_upload_document_requires_category(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("CASE_FILES_DIR", str(tmp_path / "files"))
    from app.config import get_settings
    get_settings.cache_clear()
    client = TestClient(app)
    case_id = client.post("/api/rb-portal/cases", json={"customer_name": "A", "tax_id": "111"}).json()["case_id"]
    resp = client.post(
        f"/api/rb-portal/cases/{case_id}/documents",
        files={"file": ("cccd.csv", io.BytesIO(b"CCCD SO 001234567890"), "text/csv")},
    )
    assert resp.status_code == 422  # category missing


def test_upload_document_and_list(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("CASE_FILES_DIR", str(tmp_path / "files"))
    from app.config import get_settings
    get_settings.cache_clear()
    client = TestClient(app)
    case_id = client.post("/api/rb-portal/cases", json={"customer_name": "A", "tax_id": "111"}).json()["case_id"]
    resp = client.post(
        f"/api/rb-portal/cases/{case_id}/documents",
        data={"category": "LEGAL"},
        files={"file": ("cccd.csv", io.BytesIO(b"CCCD SO 001234567890"), "text/csv")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "EXTRACTED"

    resp = client.get(f"/api/rb-portal/cases/{case_id}/documents")
    docs = resp.json()["documents"]
    assert len(docs) == 1
    assert docs[0]["filename"] == "cccd.csv"
    assert docs[0]["category"] == "LEGAL"


def test_upload_unreadable_file_marks_failed_not_500(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("CASE_FILES_DIR", str(tmp_path / "files"))
    from app.config import get_settings
    get_settings.cache_clear()
    client = TestClient(app)
    case_id = client.post("/api/rb-portal/cases", json={"customer_name": "A", "tax_id": "111"}).json()["case_id"]
    resp = client.post(
        f"/api/rb-portal/cases/{case_id}/documents",
        data={"category": "OTHER"},
        files={"file": ("photo.jpg", io.BytesIO(b"\xff\xd8\xff not a real image"), "image/jpeg")},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "FAILED"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/local/bin/python -m pytest tests/agents/rb_portal/test_router.py -k document -v`
Expected: FAIL — no `/documents` route yet (404 instead of the asserted codes)

- [ ] **Step 3: Append the document endpoints**

```python
# append to app/agents/rb_portal/router.py — add these imports at the top:
import os
import tempfile

from fastapi import File, Form, UploadFile

from app.extraction.pipeline import extract_document
from app.agents.rb.document_classifier import classify_document
from app.storage.files import save_case_file
from app.storage.rb_case_repository import add_document, list_documents

_VALID_CATEGORIES = {"LEGAL", "INCOME", "LOAN", "COLLATERAL", "OTHER"}


@router.post("/cases/{case_id}/documents")
async def upload_document_endpoint(
    case_id: str, category: str = Form(...), file: UploadFile = File(...),
) -> dict:
    if category not in _VALID_CATEGORIES:
        raise HTTPException(status_code=422, detail=f"category phải thuộc {_VALID_CATEGORIES}")
    settings = get_settings()
    init_db(settings.db_path)
    if get_case(settings.db_path, case_id) is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy hồ sơ")

    file_id = uuid.uuid4().hex[:10]
    content = await file.read()
    storage_path = save_case_file(settings.case_files_dir, case_id, file_id, file.filename, content)

    document_type = None
    status = "UPLOADED"
    with tempfile.TemporaryDirectory() as tmp_dir:
        path = os.path.join(tmp_dir, file.filename)
        with open(path, "wb") as out:
            out.write(content)
        try:
            doc = extract_document(path, file.filename, file_id=file_id)
            document_type, _confidence = classify_document(doc)
            status = "EXTRACTED"
        except Exception:  # noqa: BLE001 - a broken upload must not 500 the request
            status = "FAILED"

    add_document(
        settings.db_path, case_id, file_id, file.filename, category,
        document_type, file.content_type, len(content), storage_path,
    )
    from app.storage.rb_case_repository import update_case_status, update_document_status
    update_document_status(settings.db_path, case_id, file_id, status)
    case = get_case(settings.db_path, case_id)
    if case["status"] == "RECEIVED":
        update_case_status(settings.db_path, case_id, "DOCS_ANALYZED")
    return {"file_id": file_id, "filename": file.filename, "category": category, "status": status}


@router.get("/cases/{case_id}/documents")
async def list_documents_endpoint(case_id: str) -> dict:
    settings = get_settings()
    init_db(settings.db_path)
    if get_case(settings.db_path, case_id) is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy hồ sơ")
    return {"documents": list_documents(settings.db_path, case_id)}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/usr/local/bin/python -m pytest tests/agents/rb_portal/test_router.py -k document -v`
Expected: 3/3 PASS

- [ ] **Step 5: Run full backend suite**

Run: `/usr/local/bin/python -m pytest -q`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add app/agents/rb_portal/router.py tests/agents/rb_portal/test_router.py
git commit -m "feat(rb-portal): add document upload endpoints"
```

---

## Task 7: router.py — assessment run endpoints + Summary + History

**Files:**
- Modify: `app/agents/rb_portal/router.py`
- Modify: `tests/agents/rb_portal/test_router.py`

**Interfaces:**
- Consumes: `app.agents.rb_portal.assessment.run_case_assessment` (Task 4),
  `app.agents.rb.narrative.generate_narrative(computed) -> dict` (existing,
  unmodified — same `{"why": [...], "credit_memo": "..."}` shape used by EB/RB
  today), `app.engine.core.timing.narrative_budget_exceeded(request_start) -> bool`
  (existing), `save_assessment_version`/`list_assessment_versions`/
  `update_case_status`/`list_documents` (Task 1).
- Produces: `POST /cases/{case_id}/preliminary-assessment`,
  `POST /cases/{case_id}/full-assessment` (gated on `mandatory_check.missing == []`,
  returns 409 with the missing list when not satisfied — Review Focus item 3),
  `GET /cases/{case_id}/summary`, `GET /cases/{case_id}/history`.
  `GET .../summary` ALWAYS recomputes `credit_engine`/`risk_flags`/
  `credit_readiness` fresh from current case data (deterministic, no LLM
  call, so it is safe to call on every tab load) and layers in `why`/
  `credit_memo`/`ai_status` from the most recent **saved** assessment version
  if one exists, `{"why": [], "credit_memo": "", "ai_status": "UNAVAILABLE"}`
  otherwise — so opening the Summary tab never re-triggers the LLM call that
  only `POST .../preliminary-assessment` or `.../full-assessment` performs.

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/agents/rb_portal/test_router.py

def _make_ready_case(client, monkeypatch) -> str:
    case_id = client.post("/api/rb-portal/cases", json={"customer_name": "A", "tax_id": "111"}).json()["case_id"]
    client.patch(f"/api/rb-portal/cases/{case_id}/customer", json={"full_name": "A"})
    client.patch(f"/api/rb-portal/cases/{case_id}/legal", json={"id_type": "CCCD"})
    client.patch(f"/api/rb-portal/cases/{case_id}/income", json={"source_type": "salary", "income_salary_vnd": 25_000_000})
    client.patch(f"/api/rb-portal/cases/{case_id}/loan", json={
        "product": "vay_von", "purpose": "tieu dung", "amount_vnd": 100_000_000,
        "tenor_months": 12, "annual_rate": 0.1, "existing_monthly_obligation_vnd": 1_000_000,
    })
    return case_id


def test_preliminary_assessment_runs_and_saves_a_version(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    from app.config import get_settings
    get_settings.cache_clear()
    import app.agents.rb_portal.router as rb_portal_router
    monkeypatch.setattr(rb_portal_router, "generate_narrative", lambda computed: {"why": [], "credit_memo": ""})
    client = TestClient(app)
    case_id = _make_ready_case(client, monkeypatch)

    resp = client.post(f"/api/rb-portal/cases/{case_id}/preliminary-assessment")
    assert resp.status_code == 200
    body = resp.json()
    assert body["credit_engine"]["dti"]["status"] == "OK"

    history = client.get(f"/api/rb-portal/cases/{case_id}/history").json()["versions"]
    assert len(history) == 1
    assert history[0]["kind"] == "PRELIMINARY"


def test_full_assessment_blocked_when_mandatory_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    from app.config import get_settings
    get_settings.cache_clear()
    import app.agents.rb_portal.router as rb_portal_router
    monkeypatch.setattr(rb_portal_router, "generate_narrative", lambda computed: {"why": [], "credit_memo": ""})
    client = TestClient(app)
    case_id = client.post("/api/rb-portal/cases", json={"customer_name": "A", "tax_id": "111"}).json()["case_id"]

    resp = client.post(f"/api/rb-portal/cases/{case_id}/full-assessment")
    assert resp.status_code == 409
    # FastAPI wraps a dict `detail=` under the top-level "detail" key —
    # web/lib/rb-portal-api.ts's runFullAssessment() reads body.detail?.missing,
    # so this must stay in sync with that shape.
    assert resp.json()["detail"]["missing"]


def test_full_assessment_runs_when_mandatory_satisfied(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    from app.config import get_settings
    get_settings.cache_clear()
    import app.agents.rb_portal.router as rb_portal_router
    monkeypatch.setattr(rb_portal_router, "generate_narrative", lambda computed: {"why": [], "credit_memo": ""})
    client = TestClient(app)
    case_id = _make_ready_case(client, monkeypatch)

    resp = client.post(f"/api/rb-portal/cases/{case_id}/full-assessment")
    assert resp.status_code == 200
    assert client.get(f"/api/rb-portal/cases/{case_id}").json()["status"] == "FULL_DONE"


def test_two_preliminary_runs_create_two_history_versions(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    from app.config import get_settings
    get_settings.cache_clear()
    import app.agents.rb_portal.router as rb_portal_router
    monkeypatch.setattr(rb_portal_router, "generate_narrative", lambda computed: {"why": [], "credit_memo": ""})
    client = TestClient(app)
    case_id = _make_ready_case(client, monkeypatch)

    client.post(f"/api/rb-portal/cases/{case_id}/preliminary-assessment")
    client.post(f"/api/rb-portal/cases/{case_id}/preliminary-assessment")
    versions = client.get(f"/api/rb-portal/cases/{case_id}/history").json()["versions"]
    assert [v["version"] for v in versions] == [2, 1]


def test_summary_available_before_any_assessment_run(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    from app.config import get_settings
    get_settings.cache_clear()
    client = TestClient(app)
    case_id = client.post("/api/rb-portal/cases", json={"customer_name": "A", "tax_id": "111"}).json()["case_id"]

    resp = client.get(f"/api/rb-portal/cases/{case_id}/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["missing_data"]
    assert body["ai_status"] == "UNAVAILABLE"
    assert body["why"] == []


def test_summary_reflects_latest_saved_narrative(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    from app.config import get_settings
    get_settings.cache_clear()
    import app.agents.rb_portal.router as rb_portal_router
    monkeypatch.setattr(
        rb_portal_router, "generate_narrative",
        lambda computed: {"why": ["DTI trong ngưỡng an toàn"], "credit_memo": "Đủ điều kiện sơ bộ."},
    )
    client = TestClient(app)
    case_id = _make_ready_case(client, monkeypatch)
    client.post(f"/api/rb-portal/cases/{case_id}/preliminary-assessment")

    body = client.get(f"/api/rb-portal/cases/{case_id}/summary").json()
    assert body["why"] == ["DTI trong ngưỡng an toàn"]
    assert body["ai_status"] == "AVAILABLE"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/local/bin/python -m pytest tests/agents/rb_portal/test_router.py -k "assessment or summary or history" -v`
Expected: FAIL — 404s, no such routes

- [ ] **Step 3: Append the endpoints**

```python
# append to app/agents/rb_portal/router.py — add these imports at the top:
import time

from app.agents.rb.narrative import generate_narrative
from app.engine.core.timing import narrative_budget_exceeded
from app.storage.rb_case_repository import (
    list_assessment_versions, save_assessment_version, update_case_status,
)

from .assessment import run_case_assessment

_TOTAL_CHECKLIST_ITEMS = 6  # nominal denominator for document_overview.completion_percent


def _run_and_maybe_narrate(case_id: str, settings, request_start: float, kind: str) -> dict:
    case = get_case(settings.db_path, case_id)
    documents = list_documents(settings.db_path, case_id)
    computed = run_case_assessment(case, documents)

    if narrative_budget_exceeded(request_start):
        narrative = {"why": [], "credit_memo": ""}
    else:
        narrative = generate_narrative(computed)
    computed["why"] = narrative["why"]
    computed["credit_memo"] = narrative["credit_memo"]

    save_assessment_version(settings.db_path, case_id, kind, computed)
    return computed


@router.post("/cases/{case_id}/preliminary-assessment")
async def run_preliminary_assessment_endpoint(case_id: str) -> dict:
    request_start = time.monotonic()
    settings = get_settings()
    init_db(settings.db_path)
    if get_case(settings.db_path, case_id) is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy hồ sơ")
    computed = _run_and_maybe_narrate(case_id, settings, request_start, "PRELIMINARY")
    update_case_status(settings.db_path, case_id, "PRELIM_DONE")
    return computed


@router.post("/cases/{case_id}/full-assessment")
async def run_full_assessment_endpoint(case_id: str) -> dict:
    request_start = time.monotonic()
    settings = get_settings()
    init_db(settings.db_path)
    case = get_case(settings.db_path, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy hồ sơ")
    documents = list_documents(settings.db_path, case_id)
    mandatory = check_mandatory(case.get("customer"), case.get("legal"), case.get("income"), case.get("loan"), documents)
    if mandatory["missing"]:
        raise HTTPException(status_code=409, detail={"missing": mandatory["missing"]})
    computed = _run_and_maybe_narrate(case_id, settings, request_start, "FULL")
    update_case_status(settings.db_path, case_id, "FULL_DONE")
    return computed


_TIMELINE_STEPS = [
    ("RECEIVED", "Đã tiếp nhận hồ sơ"),
    ("DOCS_ANALYZED", "Đã phân tích chứng từ"),
    ("PRELIM_DONE", "Thẩm định sơ bộ"),
    ("FULL_DONE", "Thẩm định đầy đủ"),
]
_STATUS_ORDER = [s for s, _ in _TIMELINE_STEPS]


def _build_timeline(status: str) -> list[dict]:
    current_index = _STATUS_ORDER.index(status) if status in _STATUS_ORDER else 0
    return [
        {"status": s, "label": label, "reached": i <= current_index}
        for i, (s, label) in enumerate(_TIMELINE_STEPS)
    ]


@router.get("/cases/{case_id}/summary")
async def get_summary_endpoint(case_id: str) -> dict:
    settings = get_settings()
    init_db(settings.db_path)
    case = get_case(settings.db_path, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy hồ sơ")

    documents = list_documents(settings.db_path, case_id)
    computed = run_case_assessment(case, documents)

    versions = list_assessment_versions(settings.db_path, case_id)
    if versions:
        latest = versions[0]["computed"]
        why, credit_memo, ai_status = latest.get("why", []), latest.get("credit_memo", ""), "AVAILABLE"
    else:
        why, credit_memo, ai_status = [], "", "UNAVAILABLE"

    missing_count = len(computed["mandatory_check"]["missing"])
    completion_percent = max(0, round(100 * (_TOTAL_CHECKLIST_ITEMS - missing_count) / _TOTAL_CHECKLIST_ITEMS))

    return {
        **case,
        **computed,
        "document_overview": {
            "total_documents": len(documents),
            "completion_percent": completion_percent,
            "missing_count": missing_count,
        },
        "documents": documents,
        "timeline": _build_timeline(case["status"]),
        "why": why,
        "credit_memo": credit_memo,
        "ai_status": ai_status,
    }


@router.get("/cases/{case_id}/history")
async def get_history_endpoint(case_id: str) -> dict:
    settings = get_settings()
    init_db(settings.db_path)
    if get_case(settings.db_path, case_id) is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy hồ sơ")
    return {"versions": list_assessment_versions(settings.db_path, case_id)}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/usr/local/bin/python -m pytest tests/agents/rb_portal/test_router.py -v`
Expected: all PASS (17/17 across the whole file so far)

- [ ] **Step 5: Run full backend suite**

Run: `/usr/local/bin/python -m pytest -q`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add app/agents/rb_portal/router.py tests/agents/rb_portal/test_router.py
git commit -m "feat(rb-portal): add assessment run, summary, and history endpoints"
```

---

## Task 8: mb01a_export.py — write/checkbox helpers + customer identity section

**Files:**
- Create: `app/agents/rb_portal/mb01a_export.py`
- Test: `tests/agents/rb_portal/test_mb01a_export.py`

**Background (already verified against the real template during design —
do not re-derive, just implement):**
- The template's single big table (`document.tables[0]`) is 134 rows.
  Row 3 ("Họ tên:") is ONE merged cell (`cells[0]`) whose paragraph has runs
  `["Họ", " ", "tên", ": "]` with NO placeholder run after the label — a
  value is written by **appending a new run** to that paragraph
  (`paragraph.add_run(value)`), confirmed to round-trip correctly through
  `python-docx` (`cell.text` reads back `"Họ tên: <value>"`).
- Checkboxes are **legacy `FORMCHECKBOX` fields** (OOXML `<w:ffData><w:checkBox>
  <w:default w:val="0|1"/></w:checkBox></w:ffData>`). Bookmark names (e.g.
  `Check9`) are **not unique** across the document (confirmed: the Nam/Nữ
  pair on row 4 both use the name `Check9`) — a checkbox must be located by
  **(row_index, cell_index, occurrence-within-cell)**, never by name. "Check"
  a box by setting `<w:default w:val="1"/>` on its `occurrence`-th
  `w:checkBox` element within that cell (0-indexed in document order).
- **Known verification gap, state this honestly when the export task is
  reported done:** `libreoffice --headless --convert-to pdf` fails to load
  even the untouched original template in this container
  (`Error: source file could not be loaded`, reproduced before writing this
  plan) — there is no way to visually confirm a checked box *renders*
  checked in this environment. Verification here is at the OOXML level only
  (`w:default/@w:val` reads back as `"1"`, `cell.text` contains the written
  value) — this is a real, load-bearing limitation of the CI/dev container,
  not something to paper over. Note it again in the final task's report.

**Interfaces:**
- Produces: `write_value_after_label(table, row_idx, cell_idx, value) -> None`
  (no-op when `value` is falsy — never writes the literal string `"None"`),
  `check_box(table, row_idx, cell_idx, occurrence=0) -> None`,
  `build_mb01a_docx(case: dict) -> bytes` (case dict shape = exactly what
  `get_case()`/the summary endpoint return: `customer`, `legal`, `income`,
  `loan`, `collateral`, `other` keys, each `dict | None`). This task fills
  ONLY the customer-identity rows (2–19); Task 9 extends the same function.

- [ ] **Step 1: Write the failing tests**

```python
# tests/agents/rb_portal/test_mb01a_export.py
import io

import docx

from app.agents.rb_portal.mb01a_export import build_mb01a_docx, check_box, write_value_after_label

TEMPLATE_PATH = "docs/templates/MB01A_QT.RR.038_lan_3.docx"


def test_write_value_after_label_appends_to_the_cell():
    document = docx.Document(TEMPLATE_PATH)
    table = document.tables[0]
    write_value_after_label(table, 3, 0, "NGUYEN VAN A")
    assert table.rows[3].cells[0].text == "Họ tên: NGUYEN VAN A"


def test_write_value_after_label_is_noop_for_falsy_value():
    document = docx.Document(TEMPLATE_PATH)
    table = document.tables[0]
    original = table.rows[3].cells[0].text
    write_value_after_label(table, 3, 0, None)
    assert table.rows[3].cells[0].text == original


def test_check_box_sets_default_to_1_for_the_targeted_occurrence_only():
    document = docx.Document(TEMPLATE_PATH)
    table = document.tables[0]
    check_box(table, 4, 0, occurrence=0)  # "Nam"
    xml = table.rows[4].cells[0]._tc.xml
    # exactly one w:default now reads val="1" within this cell (Nữ stays "0")
    assert xml.count('w:default w:val="1"') == 1
    assert xml.count('w:default w:val="0"') == 1


def test_build_mb01a_docx_returns_openable_bytes_with_customer_name():
    case = {
        "customer": {"full_name": "NGUYEN VAN A", "gender": "male", "id_number": "001234567890"},
        "legal": None, "income": None, "loan": None, "collateral": None, "other": None,
    }
    result = build_mb01a_docx(case)
    assert isinstance(result, bytes)
    document = docx.Document(io.BytesIO(result))
    assert "NGUYEN VAN A" in document.tables[0].rows[3].cells[0].text


def test_build_mb01a_docx_leaves_fields_blank_for_empty_case():
    case = {"customer": None, "legal": None, "income": None, "loan": None, "collateral": None, "other": None}
    result = build_mb01a_docx(case)
    document = docx.Document(io.BytesIO(result))
    assert document.tables[0].rows[3].cells[0].text == "Họ tên: "
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/local/bin/python -m pytest tests/agents/rb_portal/test_mb01a_export.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write the module**

```python
# app/agents/rb_portal/mb01a_export.py
import io

import docx

_TEMPLATE_PATH = "docs/templates/MB01A_QT.RR.038_lan_3.docx"
_W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def write_value_after_label(table, row_idx: int, cell_idx: int, value) -> None:
    if not value:
        return
    cell = table.rows[row_idx].cells[cell_idx]
    cell.paragraphs[0].add_run(str(value))


def check_box(table, row_idx: int, cell_idx: int, occurrence: int = 0) -> None:
    cell = table.rows[row_idx].cells[cell_idx]
    checkboxes = cell._tc.findall(f".//{_W_NS}checkBox")
    box = checkboxes[occurrence]
    default = box.find(f"{_W_NS}default")
    default.set(f"{_W_NS}val", "1")


_GENDER_ROW = 4
_MARITAL_ROW = 14
# Unlike the gender checkboxes (row 4), the 4 marital-status boxes each live
# in their OWN cell (verified: cells 9/26/40/53 each contain exactly one
# w:checkBox) rather than 4 occurrences within one cell — map to cell index,
# occurrence is always 0.
_MARITAL_CELL = {"single": 9, "married": 26, "divorced": 40, "widowed": 53}


def build_mb01a_docx(case: dict) -> bytes:
    document = docx.Document(_TEMPLATE_PATH)
    table = document.tables[0]

    customer = case.get("customer") or {}
    write_value_after_label(table, 3, 0, customer.get("full_name"))
    if customer.get("gender") == "male":
        check_box(table, _GENDER_ROW, 0, occurrence=0)
    elif customer.get("gender") == "female":
        check_box(table, _GENDER_ROW, 0, occurrence=1)
    write_value_after_label(table, 5, 0, customer.get("id_number"))
    write_value_after_label(table, 9, 0, customer.get("permanent_address"))
    write_value_after_label(table, 10, 0, customer.get("temporary_address"))
    write_value_after_label(table, 11, 0, customer.get("contact_address"))
    write_value_after_label(table, 13, 0, customer.get("email"))
    marital_cell = _MARITAL_CELL.get(customer.get("marital_status"))
    if marital_cell is not None:
        check_box(table, _MARITAL_ROW, marital_cell, occurrence=0)

    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/usr/local/bin/python -m pytest tests/agents/rb_portal/test_mb01a_export.py -v`
Expected: 5/5 PASS

- [ ] **Step 5: Best-effort visual spot-check (do not block on failure)**

Run: `mkdir -p /tmp/lo_profile && libreoffice --headless -env:UserInstallation=file:///tmp/lo_profile --convert-to pdf docs/templates/MB01A_QT.RR.038_lan_3.docx --outdir /tmp/`

If this fails with `Error: source file could not be loaded` (reproduced
during design — likely a container-level LibreOffice/font issue, not
specific to your changes), record that in the task's commit message body
and move on; do not spend further time trying to fix the container's
LibreOffice install as part of this plan.

- [ ] **Step 6: Commit**

```bash
git add app/agents/rb_portal/mb01a_export.py tests/agents/rb_portal/test_mb01a_export.py
git commit -m "feat(rb-portal): add MB01A export helpers + customer identity mapping

LibreOffice headless PDF conversion is not available in this container
(fails even on the untouched template) — verified at the OOXML level only
(w:default/@w:val, cell text). Needs a manual open-in-Word spot-check
before this export is trusted for real use."
```

---

## Task 9: mb01a_export.py — business/employment, financial, loan, collateral, credit-relations

**Files:**
- Modify: `app/agents/rb_portal/mb01a_export.py`
- Modify: `tests/agents/rb_portal/test_mb01a_export.py`

**Background (verified row/cell positions — reuse as-is, don't re-derive):**
- Rows 21/22/29/33/34/36/74 are each a single merged cell per field — same
  "label: " pattern as row 3, so `write_value_after_label` (Task 8) applies
  directly: business name → `(21, 0)`, sector → `(22, 0)`, business address
  → `(29, 0)`, employer name → `(33, 0)`, employer address → `(34, 0)`,
  position (`Chức vụ hiện tại*:`) → `(36, 32)`, dependents count → `(74, 0)`.
- Rows 25 and 37 ("Thời gian kinh doanh/làm việc... năm ... tháng") have
  TWO blank slots inside one cell's run sequence — needs a new helper,
  `insert_run_before`, since the blank isn't at the end of the paragraph.
- Rows 68/69/70/71 are clean two-column "label cell | empty value cell"
  pairs: income → `(68, 17)` lương, `(69, 17)` cho thuê, `(70, 17)` kinh
  doanh, `(71, 17)` từ người bảo lãnh; expense → `(68, 56)` sinh hoạt,
  `(69, 56)` nợ khác, `(71, 56)` chi phí khác. **`(70, 56)` "Nghĩa vụ khoản
  tín dụng lần này" is deliberately left blank** — that cell wants the NEW
  loan's own computed monthly payment (a `credit_engine` metric, not a raw
  case field), and wiring the computed engine result into the export
  function is out of scope for this task; leaving it blank is honest
  (no fabricated number), not a bug.
- Row 85 (first/only loan line item) and rows 124/125 (collateral items 1–2)
  and row 131 (first credit-relationship item) are pure empty data cells —
  `write_value_after_label` still applies (it only appends a run; nothing
  about it requires a label to already be present).
- **The template pre-draws exactly 2 collateral rows and 1 credit-relationship
  row.** `RbCollateral.items`/`RbOther.existing_credit_relationships` beyond
  that many entries are **not exported** — document this limit in the
  function's own comment, don't silently truncate without saying so.
- Row 128's checkbox for "quan hệ tín dụng với MSB" lives in cell 25
  ("Chưa có") / cell 41 ("Đã/đang có") — NOT cell 0 (cell 0 is the label).

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/agents/rb_portal/test_mb01a_export.py

def test_business_income_case_fills_business_section():
    case = {
        "customer": None, "legal": None,
        "income": {"source_type": "business", "business_name": "Quan Com A",
                     "business_sector": "An uong", "business_address": "123 Le Loi",
                     "income_business_vnd": 30_000_000, "expense_living_vnd": 8_000_000,
                     "dependents_count": 2},
        "loan": None, "collateral": None, "other": None,
    }
    document = docx.Document(io.BytesIO(build_mb01a_docx(case)))
    t = document.tables[0]
    assert "Quan Com A" in t.rows[21].cells[0].text
    assert "An uong" in t.rows[22].cells[0].text
    assert "30000000" in t.rows[70].cells[17].text or "30000000.0" in t.rows[70].cells[17].text
    assert "8000000" in t.rows[68].cells[56].text or "8000000.0" in t.rows[68].cells[56].text
    assert "2" in t.rows[74].cells[0].text


def test_salary_income_case_fills_employment_section_not_business():
    case = {
        "customer": None, "legal": None,
        "income": {"source_type": "salary", "employer_name": "Cong ty B",
                     "position": "Ke toan truong", "income_salary_vnd": 25_000_000},
        "loan": None, "collateral": None, "other": None,
    }
    document = docx.Document(io.BytesIO(build_mb01a_docx(case)))
    t = document.tables[0]
    assert "Cong ty B" in t.rows[33].cells[0].text
    assert "Ke toan truong" in t.rows[36].cells[32].text
    assert t.rows[21].cells[0].text == "Tên cơ sở kinh doanh*: "  # business section untouched


def test_loan_and_collateral_and_credit_relationship_rows_filled():
    case = {
        "customer": None, "legal": None, "income": None,
        "loan": {"product": "Vay vốn", "purpose": "Bổ sung vốn kinh doanh",
                   "amount_vnd": 200_000_000, "tenor_months": 24},
        "collateral": {"items": [
            {"asset_type": "Bất động sản", "estimated_value_vnd": 800_000_000},
            {"asset_type": "Ô tô", "estimated_value_vnd": 500_000_000},
        ]},
        "other": {"existing_credit_relationships": [
            {"institution": "Vietcombank", "credit_type": "Vay tiêu dùng", "outstanding_vnd": 50_000_000},
        ]},
    }
    document = docx.Document(io.BytesIO(build_mb01a_docx(case)))
    t = document.tables[0]
    assert "Vay vốn" in t.rows[85].cells[2].text
    assert "Bổ sung vốn kinh doanh" in t.rows[85].cells[12].text
    assert "Bất động sản" in t.rows[124].cells[1].text
    assert "Ô tô" in t.rows[125].cells[1].text
    assert "Vietcombank" in t.rows[131].cells[0].text
    xml = t.rows[128].cells[41]._tc.xml  # "Đã/đang có" box checked
    assert 'w:default w:val="1"' in xml


def test_no_existing_credit_relationship_checks_the_chua_co_box():
    case = {
        "customer": None, "legal": None, "income": None, "loan": None, "collateral": None,
        "other": {"existing_credit_relationships": []},
    }
    document = docx.Document(io.BytesIO(build_mb01a_docx(case)))
    t = document.tables[0]
    xml = t.rows[128].cells[25]._tc.xml  # "Chưa có" box checked
    assert 'w:default w:val="1"' in xml
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/local/bin/python -m pytest tests/agents/rb_portal/test_mb01a_export.py -k "business or salary or loan_and_collateral or no_existing" -v`
Expected: FAIL — `AttributeError`/`AssertionError` (fields not yet mapped)

- [ ] **Step 3: Extend the module**

```python
# append to app/agents/rb_portal/mb01a_export.py

def insert_run_before(paragraph, run_index: int, text: str) -> None:
    target = paragraph.runs[run_index]
    new_run = paragraph.add_run(text)
    new_elem = new_run._element
    new_elem.getparent().remove(new_elem)
    target._element.addprevious(new_elem)


def _write_years_months(table, row_idx: int, cell_idx: int, years_run_idx: int, months_run_idx: int, years_value) -> None:
    if not years_value:
        return
    whole_years = int(years_value)
    months = round((years_value - whole_years) * 12)
    para = table.rows[row_idx].cells[cell_idx].paragraphs[0]
    insert_run_before(para, months_run_idx, f"{months} ")
    insert_run_before(para, years_run_idx, f"{whole_years} ")


def _fill_business_or_employment(table, income: dict) -> None:
    source_type = income.get("source_type")
    if source_type in ("business", "self_employed", "household_business"):
        write_value_after_label(table, 21, 0, income.get("business_name"))
        write_value_after_label(table, 22, 0, income.get("business_sector"))
        write_value_after_label(table, 29, 0, income.get("business_address"))
        _write_years_months(table, 25, 0, years_run_idx=10, months_run_idx=13, years_value=income.get("business_years"))
    elif source_type == "salary":
        write_value_after_label(table, 33, 0, income.get("employer_name"))
        write_value_after_label(table, 34, 0, income.get("employer_address"))
        write_value_after_label(table, 36, 32, income.get("position"))
        _write_years_months(table, 37, 0, years_run_idx=10, months_run_idx=13, years_value=income.get("employment_years"))


def _fill_financial(table, income: dict) -> None:
    write_value_after_label(table, 68, 17, income.get("income_salary_vnd"))
    write_value_after_label(table, 69, 17, income.get("income_rental_vnd"))
    write_value_after_label(table, 70, 17, income.get("income_business_vnd"))
    write_value_after_label(table, 71, 17, income.get("income_guarantor_vnd"))
    write_value_after_label(table, 68, 56, income.get("expense_living_vnd"))
    write_value_after_label(table, 69, 56, income.get("expense_other_debt_vnd"))
    # (70, 56) "Nghĩa vụ khoản tín dụng lần này" intentionally left blank — see Task 9 notes.
    write_value_after_label(table, 71, 56, income.get("expense_other_vnd"))
    write_value_after_label(table, 74, 0, income.get("dependents_count"))


def _fill_loan(table, loan: dict) -> None:
    write_value_after_label(table, 85, 2, loan.get("product"))
    write_value_after_label(table, 85, 12, loan.get("purpose"))
    write_value_after_label(table, 85, 32, loan.get("amount_vnd"))
    write_value_after_label(table, 85, 47, loan.get("amount_vnd"))
    write_value_after_label(table, 85, 63, loan.get("tenor_months"))


_COLLATERAL_ROWS = (124, 125)  # template pre-draws exactly 2 asset rows


def _fill_collateral(table, collateral: dict) -> None:
    items = (collateral or {}).get("items") or []
    for row_idx, item in zip(_COLLATERAL_ROWS, items):
        write_value_after_label(table, row_idx, 1, item.get("asset_type"))
        write_value_after_label(table, row_idx, 62, item.get("estimated_value_vnd"))
    # items beyond len(_COLLATERAL_ROWS) are not exported — the legal form has no more rows.


def _fill_credit_relationships(table, other: dict) -> None:
    relationships = (other or {}).get("existing_credit_relationships")
    if relationships:
        check_box(table, 128, 41, occurrence=0)  # "Đã/đang có khoản tín dụng tại MSB"
        first = relationships[0]
        write_value_after_label(table, 131, 0, first.get("institution"))
        write_value_after_label(table, 131, 3, first.get("credit_type"))
        write_value_after_label(table, 131, 42, first.get("outstanding_vnd"))
        write_value_after_label(table, 131, 57, first.get("monthly_payment_vnd"))
        # entries beyond the first are not exported — the legal form has only 1 pre-drawn row.
    elif other is not None:
        check_box(table, 128, 25, occurrence=0)  # "Chưa có"
```

- [ ] **Step 4: Wire the new fillers into `build_mb01a_docx`**

```python
# Replace build_mb01a_docx's body in app/agents/rb_portal/mb01a_export.py with:
def build_mb01a_docx(case: dict) -> bytes:
    document = docx.Document(_TEMPLATE_PATH)
    table = document.tables[0]

    customer = case.get("customer") or {}
    write_value_after_label(table, 3, 0, customer.get("full_name"))
    if customer.get("gender") == "male":
        check_box(table, _GENDER_ROW, 0, occurrence=0)
    elif customer.get("gender") == "female":
        check_box(table, _GENDER_ROW, 0, occurrence=1)
    write_value_after_label(table, 5, 0, customer.get("id_number"))
    write_value_after_label(table, 9, 0, customer.get("permanent_address"))
    write_value_after_label(table, 10, 0, customer.get("temporary_address"))
    write_value_after_label(table, 11, 0, customer.get("contact_address"))
    write_value_after_label(table, 13, 0, customer.get("email"))
    marital_cell = _MARITAL_CELL.get(customer.get("marital_status"))
    if marital_cell is not None:
        check_box(table, _MARITAL_ROW, marital_cell, occurrence=0)

    income = case.get("income")
    if income:
        _fill_business_or_employment(table, income)
        _fill_financial(table, income)
    if case.get("loan"):
        _fill_loan(table, case["loan"])
    if case.get("collateral"):
        _fill_collateral(table, case["collateral"])
    _fill_credit_relationships(table, case.get("other"))

    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `/usr/local/bin/python -m pytest tests/agents/rb_portal/test_mb01a_export.py -v`
Expected: 9/9 PASS

- [ ] **Step 6: Run full backend suite**

Run: `/usr/local/bin/python -m pytest -q`
Expected: all pass

- [ ] **Step 7: Commit**

```bash
git add app/agents/rb_portal/mb01a_export.py tests/agents/rb_portal/test_mb01a_export.py
git commit -m "feat(rb-portal): map business/financial/loan/collateral/credit-relations into MB01A export"
```

---

## Task 10: router.py — export endpoint + Zalo placeholder endpoint

**Files:**
- Create: `app/agents/rb_portal/zalo.py`
- Modify: `app/agents/rb_portal/router.py`
- Modify: `tests/agents/rb_portal/test_router.py`

**Interfaces:**
- Consumes: `app.agents.rb_portal.mb01a_export.build_mb01a_docx` (Task 9).
- Produces: `zalo.py`'s `get_zalo_qr_status() -> dict` (pure function, no
  I/O — trivially testable and swappable later without touching the route),
  `POST /cases/{case_id}/export/mb01a` (returns the `.docx` as a file
  response, `Content-Disposition` filename `MB01A_QT.RR.038_lan_3_{case_id}.docx`),
  `GET /zalo-bot/qr`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/agents/rb_portal/test_zalo.py
from app.agents.rb_portal.zalo import get_zalo_qr_status


def test_get_zalo_qr_status_reports_not_connected():
    status = get_zalo_qr_status()
    assert status["status"] == "NOT_CONNECTED"
    assert status["qr_url"] is None
    assert "Chưa kết nối" in status["message"]
```

```python
# append to tests/agents/rb_portal/test_router.py

def test_export_mb01a_returns_docx_bytes(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    from app.config import get_settings
    get_settings.cache_clear()
    client = TestClient(app)
    case_id = client.post("/api/rb-portal/cases", json={"customer_name": "NGUYEN VAN A", "tax_id": "111"}).json()["case_id"]
    client.patch(f"/api/rb-portal/cases/{case_id}/customer", json={"full_name": "NGUYEN VAN A"})

    resp = client.post(f"/api/rb-portal/cases/{case_id}/export/mb01a")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert len(resp.content) > 0


def test_export_mb01a_404_for_unknown_case(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    from app.config import get_settings
    get_settings.cache_clear()
    client = TestClient(app)
    resp = client.post("/api/rb-portal/cases/RB-NOPE/export/mb01a")
    assert resp.status_code == 404


def test_zalo_qr_endpoint_returns_placeholder(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    from app.config import get_settings
    get_settings.cache_clear()
    client = TestClient(app)
    resp = client.get("/api/rb-portal/zalo-bot/qr")
    assert resp.status_code == 200
    assert resp.json()["status"] == "NOT_CONNECTED"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/usr/local/bin/python -m pytest tests/agents/rb_portal/test_zalo.py tests/agents/rb_portal/test_router.py -k "export or zalo" -v`
Expected: FAIL — `ModuleNotFoundError` / 404s

- [ ] **Step 3: Write zalo.py**

```python
# app/agents/rb_portal/zalo.py

def get_zalo_qr_status() -> dict:
    return {
        "status": "NOT_CONNECTED",
        "qr_url": None,
        "message": "Chưa kết nối Zalo OA — liên hệ IT để cấu hình bot chính thức.",
    }
```

- [ ] **Step 4: Append the endpoints to router.py**

```python
# append to app/agents/rb_portal/router.py — add these imports at the top:
from fastapi import Response

from .mb01a_export import build_mb01a_docx
from .zalo import get_zalo_qr_status


@router.post("/cases/{case_id}/export/mb01a")
async def export_mb01a_endpoint(case_id: str) -> Response:
    settings = get_settings()
    init_db(settings.db_path)
    case = get_case(settings.db_path, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy hồ sơ")
    docx_bytes = build_mb01a_docx(case)
    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f"attachment; filename=MB01A_QT.RR.038_lan_3_{case_id}.docx"},
    )


@router.get("/zalo-bot/qr")
async def get_zalo_qr_endpoint() -> dict:
    return get_zalo_qr_status()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `/usr/local/bin/python -m pytest tests/agents/rb_portal/ -v`
Expected: all PASS (full `rb_portal` test package green)

- [ ] **Step 6: Run full backend suite**

Run: `/usr/local/bin/python -m pytest -q`
Expected: all pass — this is the last backend task, so also sanity-check the
route list: `/usr/local/bin/python -c "from app.main import app; print(sorted(r.path for r in app.routes if 'rb-portal' in r.path))"`
Expected output includes all 15 endpoints from the spec's API Contract table.

- [ ] **Step 7: Commit**

```bash
git add app/agents/rb_portal/zalo.py app/agents/rb_portal/router.py tests/agents/rb_portal/test_zalo.py tests/agents/rb_portal/test_router.py
git commit -m "feat(rb-portal): add MB01A export endpoint and Zalo placeholder endpoint"
```

---

## Task 11: Frontend — `lib/rb-portal-api.ts` types and fetch functions

**Files:**
- Create: `web/lib/rb-portal-api.ts`

**Interfaces:**
- Consumes: nothing (leaf module, mirrors how `web/lib/api.ts` has no
  internal deps either). Kept in its own file rather than appended to
  `web/lib/api.ts` — that file is already large and none of its existing
  exports are needed here (RB Portal has its own response shapes, not
  `AssessmentResult`).
- Produces: `RbCaseSection` type union, `RbCase`, `RbDocument`,
  `RbSummary`, `RbHistoryVersion` types, and:
  `createCase(customerName, taxId) -> Promise<{case_id: string}>`,
  `listCases(limit?) -> Promise<RbCase[]>`,
  `getCase(caseId) -> Promise<RbCase>`,
  `updateCaseSection(caseId, section: RbCaseSection, data: Record<string, unknown>) -> Promise<void>`,
  `uploadDocument(caseId, file: File, category: string) -> Promise<RbDocument>`,
  `listDocuments(caseId) -> Promise<RbDocument[]>`,
  `runPreliminaryAssessment(caseId) -> Promise<RbSummary>`,
  `runFullAssessment(caseId) -> Promise<RbSummary | {missing: string[]}>`,
  `getSummary(caseId) -> Promise<RbSummary>`,
  `getHistory(caseId) -> Promise<RbHistoryVersion[]>`,
  `exportMb01a(caseId) -> Promise<Blob>`,
  `getZaloQrStatus() -> Promise<{status: string; qr_url: string | null; message: string}>`.
  These mirror the shape of `RiskFlag`/`MetricValue` already exported from
  `web/lib/api.ts`/`web/components/shared/MetricCard.tsx` — this file
  imports those two types rather than redefining them.

No automated frontend test suite exists in this repo (confirmed by every
other frontend task in this codebase's history — verification is
`npx tsc --noEmit`, `npm run build`, and manual Playwright). Skip the
write-test/run-test steps for this task; go straight to writing the file,
then typecheck.

- [ ] **Step 1: Write the file**

```typescript
// web/lib/rb-portal-api.ts
import { RiskFlag } from "./api";
import { MetricValue } from "../components/shared/MetricCard";

export type RbCaseSection = "customer" | "legal" | "income" | "loan" | "collateral" | "other";

export type RbCase = {
  case_id: string;
  status: string;
  customer_name: string;
  tax_id: string;
  customer: Record<string, unknown> | null;
  legal: Record<string, unknown> | null;
  income: Record<string, unknown> | null;
  loan: Record<string, unknown> | null;
  collateral: { items: Record<string, unknown>[] } | null;
  other: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
};

export type RbDocument = {
  id: number;
  case_id: string;
  file_id: string;
  filename: string;
  category: string;
  document_type: string | null;
  status: "UPLOADED" | "PROCESSING" | "EXTRACTED" | "FAILED" | "NEED_OCR_VLM";
  content_type: string | null;
  size_bytes: number;
  storage_path: string;
  uploaded_at: string;
};

export type RbMandatoryCheck = {
  legal: string[];
  income: string[];
  loan: string[];
  other: string[];
  tax_declaration_required: boolean | null;
  tax_declaration_present: boolean;
  missing: string[];
};

export type RbTimelineStep = { status: string; label: string; reached: boolean };

// Exactly what run_case_assessment() (app/agents/rb_portal/assessment.py)
// returns, plus why/credit_memo — this is also exactly what gets persisted
// into rb_case_assessments.computed_json on each run, so it is the type of
// RbHistoryVersion.computed too. RbSummary below extends it with the extra
// fields the summary endpoint layers on top (document_overview, documents,
// timeline, ai_status) that are NOT part of the persisted blob — keep this
// split; giving RbHistoryVersion.computed the full RbSummary type would
// silently lie about fields (e.g. .document_overview) that are undefined
// at runtime on a history entry.
export type RbAssessmentComputed = {
  credit_engine: Record<string, MetricValue>;
  risk_flags: RiskFlag[];
  mandatory_check: RbMandatoryCheck;
  missing_data: string[];
  credit_readiness: string;
  recommendation: string;
  why: string[];
  credit_memo: string;
};

export type RbSummary = RbCase & RbAssessmentComputed & {
  document_overview: { total_documents: number; completion_percent: number; missing_count: number };
  documents: RbDocument[];
  timeline: RbTimelineStep[];
  ai_status: "AVAILABLE" | "UNAVAILABLE";
};

export type RbHistoryVersion = { version: number; kind: "PRELIMINARY" | "FULL"; computed: RbAssessmentComputed; created_at: string };

const BASE = "/api/rb-portal";

async function asJson<T>(resp: Response): Promise<T> {
  if (!resp.ok) throw new Error(`RB Portal request thất bại: HTTP ${resp.status}`);
  return resp.json();
}

export async function createCase(customerName: string, taxId: string): Promise<{ case_id: string }> {
  return asJson(
    await fetch(`${BASE}/cases`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ customer_name: customerName, tax_id: taxId }),
    })
  );
}

export async function listCases(limit = 20): Promise<RbCase[]> {
  const body = await asJson<{ cases: RbCase[] }>(await fetch(`${BASE}/cases?limit=${limit}`));
  return body.cases;
}

export async function getCase(caseId: string): Promise<RbCase> {
  return asJson(await fetch(`${BASE}/cases/${encodeURIComponent(caseId)}`));
}

export async function updateCaseSection(
  caseId: string, section: RbCaseSection, data: Record<string, unknown>
): Promise<void> {
  const resp = await fetch(`${BASE}/cases/${encodeURIComponent(caseId)}/${section}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!resp.ok) throw new Error(`Lưu ${section} thất bại: HTTP ${resp.status}`);
}

export async function uploadDocument(caseId: string, file: File, category: string): Promise<RbDocument> {
  const form = new FormData();
  form.append("file", file);
  form.append("category", category);
  return asJson(
    await fetch(`${BASE}/cases/${encodeURIComponent(caseId)}/documents`, { method: "POST", body: form })
  );
}

export async function listDocuments(caseId: string): Promise<RbDocument[]> {
  const body = await asJson<{ documents: RbDocument[] }>(
    await fetch(`${BASE}/cases/${encodeURIComponent(caseId)}/documents`)
  );
  return body.documents;
}

export async function runPreliminaryAssessment(caseId: string): Promise<RbSummary> {
  return asJson(await fetch(`${BASE}/cases/${encodeURIComponent(caseId)}/preliminary-assessment`, { method: "POST" }));
}

export async function runFullAssessment(caseId: string): Promise<RbSummary> {
  const resp = await fetch(`${BASE}/cases/${encodeURIComponent(caseId)}/full-assessment`, { method: "POST" });
  if (resp.status === 409) {
    const body = await resp.json();
    throw new Error(`Chưa đủ hồ sơ bắt buộc: ${(body.detail?.missing ?? []).join(", ")}`);
  }
  return asJson(resp);
}

export async function getSummary(caseId: string): Promise<RbSummary> {
  return asJson(await fetch(`${BASE}/cases/${encodeURIComponent(caseId)}/summary`));
}

export async function getHistory(caseId: string): Promise<RbHistoryVersion[]> {
  const body = await asJson<{ versions: RbHistoryVersion[] }>(
    await fetch(`${BASE}/cases/${encodeURIComponent(caseId)}/history`)
  );
  return body.versions;
}

export async function exportMb01a(caseId: string): Promise<Blob> {
  const resp = await fetch(`${BASE}/cases/${encodeURIComponent(caseId)}/export/mb01a`, { method: "POST" });
  if (!resp.ok) throw new Error(`Xuất MB01A thất bại: HTTP ${resp.status}`);
  return resp.blob();
}

export async function getZaloQrStatus(): Promise<{ status: string; qr_url: string | null; message: string }> {
  return asJson(await fetch(`${BASE}/zalo-bot/qr`));
}
```

- [ ] **Step 2: Typecheck**

Run: `cd web && npx tsc --noEmit -p .`
Expected: clean (no errors)

- [ ] **Step 3: Commit**

```bash
git add web/lib/rb-portal-api.ts
git commit -m "feat(rb-portal): add frontend API client for RB Portal"
```

---

## Task 12: Frontend — `RbPortal.tsx` shell + `OverviewTab.tsx`

**Files:**
- Create: `web/components/rb-portal/RbPortal.tsx`
- Create: `web/components/rb-portal/tabs/OverviewTab.tsx`

**Interfaces:**
- Consumes: everything from Task 11 (`web/lib/rb-portal-api.ts`).
- Produces: `export default function RbPortal(): JSX.Element` — the only
  export `page.tsx` (Task 20) needs. Owns `activeCaseId: string | null` and
  `activeTab: string` state; every tab component below is a **named**
  export taking `{ caseId: string }` (all tabs except Overview, which takes
  `{ onSelectCase: (caseId: string) => void }`) so `RbPortal` can render them
  uniformly. `OverviewTab` produces `OverviewTab({ onSelectCase })`.

- [ ] **Step 1: Write `OverviewTab.tsx`**

```typescript
// web/components/rb-portal/tabs/OverviewTab.tsx
"use client";

import { useEffect, useState } from "react";
import { Plus } from "lucide-react";
import { RbCase, createCase, listCases } from "@/lib/rb-portal-api";

export function OverviewTab({ onSelectCase }: { onSelectCase: (caseId: string) => void }) {
  const [cases, setCases] = useState<RbCase[]>([]);
  const [customerName, setCustomerName] = useState("");
  const [taxId, setTaxId] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listCases().then(setCases).catch(() => setCases([]));
  }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!customerName.trim() || !taxId.trim()) return;
    setCreating(true);
    setError(null);
    try {
      const { case_id } = await createCase(customerName.trim(), taxId.trim());
      onSelectCase(case_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Tạo hồ sơ thất bại");
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="space-y-5">
      <form onSubmit={handleCreate} className="bg-white rounded-xl border border-gray-100 p-5 space-y-3">
        <h3 className="text-sm font-semibold text-msb-navy">Tạo hồ sơ mới</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <input
            className="border border-gray-200 rounded-lg px-3 py-2 text-sm"
            placeholder="Tên khách hàng"
            value={customerName}
            onChange={(e) => setCustomerName(e.target.value)}
          />
          <input
            className="border border-gray-200 rounded-lg px-3 py-2 text-sm"
            placeholder="Mã số thuế / CCCD"
            value={taxId}
            onChange={(e) => setTaxId(e.target.value)}
          />
        </div>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button
          type="submit"
          disabled={creating}
          className="inline-flex items-center gap-1.5 bg-msb-orange text-white text-sm font-semibold px-4 py-2 rounded-lg disabled:opacity-50"
        >
          <Plus className="h-4 w-4" />
          {creating ? "Đang tạo..." : "Tạo hồ sơ"}
        </button>
      </form>

      <div className="bg-white rounded-xl border border-gray-100 p-5">
        <h3 className="text-sm font-semibold text-msb-navy mb-3">Hồ sơ gần đây</h3>
        {cases.length === 0 ? (
          <p className="text-sm text-gray-500">Chưa có hồ sơ nào.</p>
        ) : (
          <ul className="divide-y">
            {cases.map((c) => (
              <li key={c.case_id} className="py-2.5">
                <button
                  onClick={() => onSelectCase(c.case_id)}
                  className="w-full text-left hover:bg-msb-bg rounded-lg px-2 py-1 -mx-2 transition-colors"
                >
                  <p className="text-sm font-medium text-msb-navy">{c.customer_name}</p>
                  <p className="text-xs text-gray-500">
                    {c.case_id} · MST {c.tax_id} · {c.status}
                  </p>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Write `RbPortal.tsx`** (stub tabs for now — Tasks 13–19 fill them in)

```typescript
// web/components/rb-portal/RbPortal.tsx
"use client";

import { useState } from "react";
import {
  Banknote, ClipboardCheck, FileText, FolderOpen, Home, IdCard, Landmark,
  ListChecks, PiggyBank, ScrollText, UploadCloud, MessageCircle,
} from "lucide-react";
import { OverviewTab } from "./tabs/OverviewTab";
import { ZaloBotModal } from "./ZaloBotModal";

const TABS = [
  { key: "overview", label: "Tổng quan", icon: Home },
  { key: "customer", label: "Hồ sơ khách hàng", icon: IdCard },
  { key: "legal", label: "Pháp lý", icon: ScrollText },
  { key: "income", label: "Nguồn thu", icon: Banknote },
  { key: "loan", label: "Khoản vay", icon: Landmark },
  { key: "collateral", label: "Tài sản bảo đảm", icon: PiggyBank },
  { key: "other", label: "Hồ sơ khác", icon: FolderOpen },
  { key: "documents", label: "Tải lên chứng từ", icon: UploadCloud },
  { key: "assessment", label: "Thẩm định", icon: ClipboardCheck },
  { key: "summary", label: "Tổng hợp", icon: FileText },
  { key: "history", label: "Lịch sử", icon: ListChecks },
] as const;

type TabKey = (typeof TABS)[number]["key"];

export default function RbPortal() {
  const [caseId, setCaseId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabKey>("overview");
  const [zaloOpen, setZaloOpen] = useState(false);

  function selectCase(id: string) {
    setCaseId(id);
    setActiveTab("customer");
  }

  return (
    <div className="mt-6 grid grid-cols-1 lg:grid-cols-[220px_1fr] gap-5">
      <aside className="bg-white rounded-xl border border-gray-100 p-3 space-y-1 h-fit">
        {TABS.map(({ key, label, icon: Icon }) => {
          const disabled = key !== "overview" && !caseId;
          return (
            <button
              key={key}
              disabled={disabled}
              onClick={() => setActiveTab(key)}
              className={`w-full flex items-center gap-2.5 text-left text-sm px-3 py-2 rounded-lg transition-colors ${
                activeTab === key ? "bg-msb-orange text-white" : "text-msb-navy hover:bg-msb-bg"
              } ${disabled ? "opacity-40 cursor-not-allowed" : ""}`}
            >
              <Icon className="h-4 w-4 shrink-0" />
              {label}
            </button>
          );
        })}
        <button
          onClick={() => setZaloOpen(true)}
          className="w-full flex items-center gap-2.5 text-left text-sm px-3 py-2 rounded-lg text-msb-navy hover:bg-msb-bg mt-2 border-t border-gray-100 pt-3"
        >
          <MessageCircle className="h-4 w-4 shrink-0" />
          Zalo Chat Bot
        </button>
      </aside>

      <div className="min-w-0">
        {activeTab === "overview" && <OverviewTab onSelectCase={selectCase} />}
        {activeTab !== "overview" && !caseId && (
          <p className="text-sm text-gray-500">Chọn hoặc tạo hồ sơ ở tab Tổng quan trước.</p>
        )}
        {/* Tasks 13-19 render the remaining tabs here, keyed by activeTab + caseId */}
      </div>

      <ZaloBotModal open={zaloOpen} onClose={() => setZaloOpen(false)} />
    </div>
  );
}
```

- [ ] **Step 2: Write a minimal `ZaloBotModal.tsx` stub so the import resolves**
      (Task 19 fills in the real QR-status fetch)

```typescript
// web/components/rb-portal/ZaloBotModal.tsx
"use client";

export function ZaloBotModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30" onClick={onClose}>
      <div className="bg-white rounded-xl p-6 max-w-sm w-full mx-4" onClick={(e) => e.stopPropagation()}>
        <p className="text-sm text-gray-500">Đang tải...</p>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Typecheck**

Run: `cd web && npx tsc --noEmit -p .`
Expected: clean

- [ ] **Step 4: Commit**

```bash
git add web/components/rb-portal/
git commit -m "feat(rb-portal): add RB Portal sidebar shell and Overview tab"
```

---

## Task 13: Frontend — generic `SectionForm` + `CustomerTab.tsx` + `LegalTab.tsx`

**Files:**
- Create: `web/components/rb-portal/tabs/SectionForm.tsx`
- Create: `web/components/rb-portal/tabs/CustomerTab.tsx`
- Create: `web/components/rb-portal/tabs/LegalTab.tsx`
- Modify: `web/components/rb-portal/RbPortal.tsx`

**Interfaces:**
- Consumes: `getCase`, `updateCaseSection` (Task 11).
- Produces: `SectionForm({ caseId, section, title, fields }): JSX.Element`
  where `fields: {key: string; label: string; type: "text"|"number"|"select"|"date"; options?: {value: string; label: string}[]}[]`
  — a reusable "load section → edit → Save button → PATCH" form used by this
  task's Customer/Legal tabs and Task 15's Loan/Other tabs (Income and
  Collateral need bespoke UIs and do NOT use this component). Each of
  `CustomerTab`, `LegalTab` takes `{ caseId: string }` and is a thin
  `SectionForm` wrapper with a fixed `fields` list.

- [ ] **Step 1: Write `SectionForm.tsx`**

```typescript
// web/components/rb-portal/tabs/SectionForm.tsx
"use client";

import { useEffect, useState } from "react";
import { RbCaseSection, getCase, updateCaseSection } from "@/lib/rb-portal-api";

export type SectionField = {
  key: string;
  label: string;
  type: "text" | "number" | "select" | "date";
  options?: { value: string; label: string }[];
};

export function SectionForm({
  caseId, section, title, fields,
}: { caseId: string; section: RbCaseSection; title: string; fields: SectionField[] }) {
  const [values, setValues] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    getCase(caseId)
      .then((c) => {
        const section_data = (c[section] as Record<string, unknown> | null) ?? {};
        const asStrings: Record<string, string> = {};
        for (const f of fields) {
          const v = section_data[f.key];
          asStrings[f.key] = v === null || v === undefined ? "" : String(v);
        }
        setValues(asStrings);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Không tải được dữ liệu"))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId, section]);

  async function handleSave() {
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      const payload: Record<string, unknown> = {};
      for (const f of fields) {
        const raw = values[f.key] ?? "";
        payload[f.key] = f.type === "number" ? (raw === "" ? null : Number(raw)) : raw || null;
      }
      await updateCaseSection(caseId, section, payload);
      setSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Lưu thất bại");
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <p className="text-sm text-gray-500">Đang tải...</p>;

  return (
    <div className="bg-white rounded-xl border border-gray-100 p-5 space-y-4">
      <h3 className="text-sm font-semibold text-msb-navy">{title}</h3>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {fields.map((f) => (
          <div key={f.key}>
            <label className="block text-xs font-medium text-msb-navy mb-1">{f.label}</label>
            {f.type === "select" ? (
              <select
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
                value={values[f.key] ?? ""}
                onChange={(e) => setValues((v) => ({ ...v, [f.key]: e.target.value }))}
              >
                <option value="">— Chọn —</option>
                {f.options?.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            ) : (
              <input
                type={f.type === "date" ? "date" : f.type === "number" ? "number" : "text"}
                className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
                value={values[f.key] ?? ""}
                onChange={(e) => setValues((v) => ({ ...v, [f.key]: e.target.value }))}
              />
            )}
          </div>
        ))}
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}
      <div className="flex items-center gap-3">
        <button
          onClick={handleSave}
          disabled={saving}
          className="bg-msb-orange text-white text-sm font-semibold px-4 py-2 rounded-lg disabled:opacity-50"
        >
          {saving ? "Đang lưu..." : "Lưu"}
        </button>
        {saved && <span className="text-xs text-green-600">Đã lưu.</span>}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Write `CustomerTab.tsx` and `LegalTab.tsx`**

```typescript
// web/components/rb-portal/tabs/CustomerTab.tsx
"use client";

import { SectionForm } from "./SectionForm";

export function CustomerTab({ caseId }: { caseId: string }) {
  return (
    <SectionForm
      caseId={caseId}
      section="customer"
      title="Hồ sơ khách hàng"
      fields={[
        { key: "full_name", label: "Họ tên", type: "text" },
        {
          key: "gender", label: "Giới tính", type: "select",
          options: [{ value: "male", label: "Nam" }, { value: "female", label: "Nữ" }],
        },
        { key: "date_of_birth", label: "Ngày sinh", type: "date" },
        { key: "nationality", label: "Quốc tịch", type: "text" },
        { key: "id_number", label: "Số CCCD/Hộ chiếu", type: "text" },
        { key: "tax_id", label: "Mã số thuế", type: "text" },
        { key: "permanent_address", label: "Địa chỉ thường trú", type: "text" },
        { key: "temporary_address", label: "Địa chỉ tạm trú", type: "text" },
        { key: "contact_address", label: "Địa chỉ liên lạc", type: "text" },
        { key: "phone_mobile", label: "Điện thoại di động", type: "text" },
        { key: "phone_home", label: "Điện thoại nhà riêng", type: "text" },
        { key: "email", label: "Email", type: "text" },
        {
          key: "marital_status", label: "Tình trạng hôn nhân", type: "select",
          options: [
            { value: "single", label: "Độc thân" }, { value: "married", label: "Có gia đình" },
            { value: "divorced", label: "Ly hôn" }, { value: "widowed", label: "Góa" },
          ],
        },
        { key: "education_level", label: "Trình độ học vấn", type: "text" },
      ]}
    />
  );
}
```

```typescript
// web/components/rb-portal/tabs/LegalTab.tsx
"use client";

import { SectionForm } from "./SectionForm";

export function LegalTab({ caseId }: { caseId: string }) {
  return (
    <SectionForm
      caseId={caseId}
      section="legal"
      title="Pháp lý"
      fields={[
        {
          key: "id_type", label: "Loại giấy tờ định danh", type: "select",
          options: [
            { value: "CCCD", label: "CCCD" }, { value: "CMND", label: "CMND" },
            { value: "PASSPORT", label: "Hộ chiếu" },
          ],
        },
        { key: "id_issue_date", label: "Ngày cấp", type: "date" },
        { key: "id_issue_place", label: "Nơi cấp", type: "text" },
        { key: "business_registration_number", label: "Số đăng ký kinh doanh", type: "text" },
        { key: "business_registration_issue_date", label: "Ngày cấp ĐKKD", type: "date" },
        { key: "business_registration_issue_place", label: "Nơi cấp ĐKKD", type: "text" },
      ]}
    />
  );
}
```

- [ ] **Step 3: Wire both tabs into `RbPortal.tsx`**

```typescript
// In web/components/rb-portal/RbPortal.tsx: add imports
import { CustomerTab } from "./tabs/CustomerTab";
import { LegalTab } from "./tabs/LegalTab";

// Replace the placeholder comment with:
        {activeTab === "customer" && caseId && <CustomerTab caseId={caseId} />}
        {activeTab === "legal" && caseId && <LegalTab caseId={caseId} />}
        {/* Tasks 14-19 render the remaining tabs here */}
```

- [ ] **Step 4: Typecheck**

Run: `cd web && npx tsc --noEmit -p .`
Expected: clean

- [ ] **Step 5: Commit**

```bash
git add web/components/rb-portal/
git commit -m "feat(rb-portal): add generic SectionForm, Customer and Legal tabs"
```

---

## Task 14: Frontend — `IncomeTab.tsx` (source-type-conditional + tax-declaration gate)

**Files:**
- Create: `web/components/rb-portal/tabs/IncomeTab.tsx`
- Modify: `web/components/rb-portal/RbPortal.tsx`

**Interfaces:**
- Consumes: `getCase`, `updateCaseSection` (Task 11). Does NOT use
  `SectionForm` (Task 13) — the business/employment fields are conditional
  on `source_type` and the tax-declaration flag is a checkbox with
  explanatory copy, neither of which fits the generic form's shape.

- [ ] **Step 1: Write the component**

```typescript
// web/components/rb-portal/tabs/IncomeTab.tsx
"use client";

import { useEffect, useState } from "react";
import { getCase, updateCaseSection } from "@/lib/rb-portal-api";

const SOURCE_TYPES = [
  { value: "salary", label: "Lương" },
  { value: "business", label: "Kinh doanh" },
  { value: "self_employed", label: "Tự doanh" },
  { value: "household_business", label: "Hộ kinh doanh" },
];

const _BUSINESS_TYPES = new Set(["business", "self_employed", "household_business"]);

type IncomeState = Record<string, string> & { tax_declaration_present: string };

export function IncomeTab({ caseId }: { caseId: string }) {
  const [values, setValues] = useState<IncomeState>({ tax_declaration_present: "false" });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    getCase(caseId)
      .then((c) => {
        const income = (c.income as Record<string, unknown> | null) ?? {};
        const asStrings: IncomeState = { tax_declaration_present: "false" };
        for (const [k, v] of Object.entries(income)) {
          asStrings[k] = v === null || v === undefined ? "" : String(v);
        }
        setValues(asStrings);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Không tải được dữ liệu"))
      .finally(() => setLoading(false));
  }, [caseId]);

  const sourceType = values.source_type ?? "";
  const isBusiness = _BUSINESS_TYPES.has(sourceType);

  function set(key: string, value: string) {
    setValues((v) => ({ ...v, [key]: value }));
  }

  async function handleSave() {
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      const numberKeys = [
        "business_years", "employment_years", "income_salary_vnd", "income_rental_vnd",
        "income_business_vnd", "income_guarantor_vnd", "expense_living_vnd",
        "expense_other_debt_vnd", "expense_other_vnd", "dependents_count",
      ];
      const payload: Record<string, unknown> = {};
      for (const [k, v] of Object.entries(values)) {
        if (k === "tax_declaration_present") { payload[k] = v === "true"; continue; }
        if (numberKeys.includes(k)) { payload[k] = v === "" ? null : Number(v); continue; }
        payload[k] = v || null;
      }
      await updateCaseSection(caseId, "income", payload);
      setSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Lưu thất bại");
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <p className="text-sm text-gray-500">Đang tải...</p>;

  return (
    <div className="bg-white rounded-xl border border-gray-100 p-5 space-y-4">
      <h3 className="text-sm font-semibold text-msb-navy">Nguồn thu</h3>

      <div>
        <label className="block text-xs font-medium text-msb-navy mb-1">Nguồn thu nhập chính</label>
        <select
          className="w-full sm:w-64 border border-gray-200 rounded-lg px-3 py-2 text-sm"
          value={sourceType}
          onChange={(e) => set("source_type", e.target.value)}
        >
          <option value="">— Chọn —</option>
          {SOURCE_TYPES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
        </select>
      </div>

      {isBusiness && (
        <div className="border-t pt-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-medium text-msb-navy mb-1">Tên cơ sở kinh doanh</label>
            <input className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" value={values.business_name ?? ""} onChange={(e) => set("business_name", e.target.value)} />
          </div>
          <div>
            <label className="block text-xs font-medium text-msb-navy mb-1">Ngành nghề kinh doanh</label>
            <input className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" value={values.business_sector ?? ""} onChange={(e) => set("business_sector", e.target.value)} />
          </div>
          <div>
            <label className="block text-xs font-medium text-msb-navy mb-1">Thời gian kinh doanh (năm)</label>
            <input type="number" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" value={values.business_years ?? ""} onChange={(e) => set("business_years", e.target.value)} />
          </div>
          <div>
            <label className="block text-xs font-medium text-msb-navy mb-1">Địa điểm kinh doanh</label>
            <input className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" value={values.business_address ?? ""} onChange={(e) => set("business_address", e.target.value)} />
          </div>

          <div className="sm:col-span-2 bg-amber-50 border border-amber-200 rounded-lg p-3 flex items-start gap-2">
            <input
              type="checkbox"
              className="mt-0.5"
              checked={values.tax_declaration_present === "true"}
              onChange={(e) => set("tax_declaration_present", String(e.target.checked))}
            />
            <div>
              <p className="text-sm font-medium text-amber-900">Đã có tờ khai thuế</p>
              <p className="text-xs text-amber-700">
                Bắt buộc với khách hàng có nguồn thu kinh doanh/tự doanh/hộ kinh doanh — nếu chưa
                tick, hồ sơ sẽ hiện thiếu ở tab Tổng hợp và không đủ điều kiện thẩm định đầy đủ.
              </p>
            </div>
          </div>
        </div>
      )}

      {sourceType === "salary" && (
        <div className="border-t pt-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label className="block text-xs font-medium text-msb-navy mb-1">Tên đơn vị công tác</label>
            <input className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" value={values.employer_name ?? ""} onChange={(e) => set("employer_name", e.target.value)} />
          </div>
          <div>
            <label className="block text-xs font-medium text-msb-navy mb-1">Chức vụ hiện tại</label>
            <input className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" value={values.position ?? ""} onChange={(e) => set("position", e.target.value)} />
          </div>
          <div>
            <label className="block text-xs font-medium text-msb-navy mb-1">Địa chỉ cơ quan</label>
            <input className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" value={values.employer_address ?? ""} onChange={(e) => set("employer_address", e.target.value)} />
          </div>
          <div>
            <label className="block text-xs font-medium text-msb-navy mb-1">Thời gian làm việc (năm)</label>
            <input type="number" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" value={values.employment_years ?? ""} onChange={(e) => set("employment_years", e.target.value)} />
          </div>
        </div>
      )}

      <div className="border-t pt-4 space-y-2">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide">Thông tin tài chính (VND/tháng)</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {[
            ["income_salary_vnd", "Thu nhập từ lương"], ["income_rental_vnd", "Thu nhập từ cho thuê tài sản"],
            ["income_business_vnd", "Thu nhập từ kinh doanh"], ["income_guarantor_vnd", "Thu nhập người bảo lãnh"],
            ["expense_living_vnd", "Chi phí sinh hoạt, tiêu dùng"], ["expense_other_debt_vnd", "Nghĩa vụ trả nợ khác"],
            ["expense_other_vnd", "Chi phí khác"], ["dependents_count", "Số người phụ thuộc"],
          ].map(([key, label]) => (
            <div key={key}>
              <label className="block text-xs font-medium text-msb-navy mb-1">{label}</label>
              <input type="number" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" value={values[key] ?? ""} onChange={(e) => set(key, e.target.value)} />
            </div>
          ))}
        </div>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}
      <div className="flex items-center gap-3">
        <button onClick={handleSave} disabled={saving} className="bg-msb-orange text-white text-sm font-semibold px-4 py-2 rounded-lg disabled:opacity-50">
          {saving ? "Đang lưu..." : "Lưu"}
        </button>
        {saved && <span className="text-xs text-green-600">Đã lưu.</span>}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Wire into `RbPortal.tsx`**

```typescript
// add import
import { IncomeTab } from "./tabs/IncomeTab";
// add render line
        {activeTab === "income" && caseId && <IncomeTab caseId={caseId} />}
```

- [ ] **Step 3: Typecheck**

Run: `cd web && npx tsc --noEmit -p .`
Expected: clean

- [ ] **Step 4: Commit**

```bash
git add web/components/rb-portal/
git commit -m "feat(rb-portal): add Income tab with source-type fields and tax-declaration gate"
```

---

## Task 15: Frontend — `LoanTab.tsx`, `CollateralTab.tsx`, `OtherDocsTab.tsx`

**Files:**
- Create: `web/components/rb-portal/tabs/LoanTab.tsx`
- Create: `web/components/rb-portal/tabs/CollateralTab.tsx`
- Create: `web/components/rb-portal/tabs/OtherDocsTab.tsx`
- Modify: `web/components/rb-portal/RbPortal.tsx`

**Interfaces:**
- Consumes: `SectionForm` (Task 13) for `LoanTab`; `getCase`/
  `updateCaseSection` (Task 11) directly for `CollateralTab`/`OtherDocsTab`
  (both edit a `items`/`existing_credit_relationships` **array**, which
  `SectionForm` doesn't support).

- [ ] **Step 1: Write `LoanTab.tsx`**

```typescript
// web/components/rb-portal/tabs/LoanTab.tsx
"use client";

import { SectionForm } from "./SectionForm";

export function LoanTab({ caseId }: { caseId: string }) {
  return (
    <SectionForm
      caseId={caseId}
      section="loan"
      title="Khoản vay"
      fields={[
        { key: "product", label: "Sản phẩm", type: "text" },
        { key: "purpose", label: "Mục đích vay", type: "text" },
        { key: "amount_vnd", label: "Số tiền đề nghị (VND)", type: "number" },
        { key: "tenor_months", label: "Thời hạn (tháng)", type: "number" },
        { key: "annual_rate", label: "Lãi suất dự kiến (thập phân, vd 0.1 = 10%/năm)", type: "number" },
        { key: "existing_monthly_obligation_vnd", label: "Nghĩa vụ trả nợ hiện tại (VND/tháng)", type: "number" },
        { key: "repayment_method", label: "Phương thức trả nợ", type: "text" },
      ]}
    />
  );
}
```

- [ ] **Step 2: Write `CollateralTab.tsx`**

```typescript
// web/components/rb-portal/tabs/CollateralTab.tsx
"use client";

import { useEffect, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { getCase, updateCaseSection } from "@/lib/rb-portal-api";

type CollateralItem = { asset_type: string; ownership_status: string; estimated_value_vnd: string };

const EMPTY_ITEM: CollateralItem = { asset_type: "", ownership_status: "", estimated_value_vnd: "" };

export function CollateralTab({ caseId }: { caseId: string }) {
  const [items, setItems] = useState<CollateralItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    getCase(caseId)
      .then((c) => {
        const raw = (c.collateral?.items ?? []) as Record<string, unknown>[];
        setItems(
          raw.map((it) => ({
            asset_type: String(it.asset_type ?? ""), ownership_status: String(it.ownership_status ?? ""),
            estimated_value_vnd: it.estimated_value_vnd == null ? "" : String(it.estimated_value_vnd),
          }))
        );
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Không tải được dữ liệu"))
      .finally(() => setLoading(false));
  }, [caseId]);

  function updateItem(i: number, patch: Partial<CollateralItem>) {
    setItems((prev) => prev.map((it, idx) => (idx === i ? { ...it, ...patch } : it)));
  }

  async function handleSave() {
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      const payload = {
        items: items
          .filter((it) => it.asset_type.trim() !== "")
          .map((it) => ({
            asset_type: it.asset_type,
            ownership_status: it.ownership_status,
            estimated_value_vnd: it.estimated_value_vnd === "" ? null : Number(it.estimated_value_vnd),
          })),
      };
      await updateCaseSection(caseId, "collateral", payload);
      setSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Lưu thất bại");
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <p className="text-sm text-gray-500">Đang tải...</p>;

  return (
    <div className="bg-white rounded-xl border border-gray-100 p-5 space-y-4">
      <h3 className="text-sm font-semibold text-msb-navy">Tài sản bảo đảm</h3>
      <div className="space-y-3">
        {items.map((it, i) => (
          <div key={i} className="grid grid-cols-1 sm:grid-cols-[1fr_1fr_1fr_auto] gap-2 items-end border-b border-gray-50 pb-3">
            <div>
              <label className="block text-xs text-gray-500 mb-1">Loại tài sản</label>
              <input className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" value={it.asset_type} onChange={(e) => updateItem(i, { asset_type: e.target.value })} />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Tình trạng sở hữu</label>
              <input className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" value={it.ownership_status} onChange={(e) => updateItem(i, { ownership_status: e.target.value })} />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Giá trị ước tính (VND)</label>
              <input type="number" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" value={it.estimated_value_vnd} onChange={(e) => updateItem(i, { estimated_value_vnd: e.target.value })} />
            </div>
            <button onClick={() => setItems((prev) => prev.filter((_, idx) => idx !== i))} className="text-red-500 p-2">
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        ))}
      </div>
      <button
        onClick={() => setItems((prev) => [...prev, { ...EMPTY_ITEM }])}
        className="inline-flex items-center gap-1.5 text-sm text-msb-navy underline"
      >
        <Plus className="h-4 w-4" /> Thêm tài sản
      </button>
      {error && <p className="text-sm text-red-600">{error}</p>}
      <div className="flex items-center gap-3 border-t pt-3">
        <button onClick={handleSave} disabled={saving} className="bg-msb-orange text-white text-sm font-semibold px-4 py-2 rounded-lg disabled:opacity-50">
          {saving ? "Đang lưu..." : "Lưu"}
        </button>
        {saved && <span className="text-xs text-green-600">Đã lưu.</span>}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Write `OtherDocsTab.tsx`**

```typescript
// web/components/rb-portal/tabs/OtherDocsTab.tsx
"use client";

import { useEffect, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { getCase, updateCaseSection } from "@/lib/rb-portal-api";

type Relationship = { institution: string; credit_type: string; outstanding_vnd: string; monthly_payment_vnd: string };

const EMPTY_REL: Relationship = { institution: "", credit_type: "", outstanding_vnd: "", monthly_payment_vnd: "" };

export function OtherDocsTab({ caseId }: { caseId: string }) {
  const [notes, setNotes] = useState("");
  const [relationships, setRelationships] = useState<Relationship[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    getCase(caseId)
      .then((c) => {
        const other = (c.other as Record<string, unknown> | null) ?? {};
        setNotes(String(other.notes ?? ""));
        const raw = (other.existing_credit_relationships ?? []) as Record<string, unknown>[];
        setRelationships(
          raw.map((r) => ({
            institution: String(r.institution ?? ""), credit_type: String(r.credit_type ?? ""),
            outstanding_vnd: r.outstanding_vnd == null ? "" : String(r.outstanding_vnd),
            monthly_payment_vnd: r.monthly_payment_vnd == null ? "" : String(r.monthly_payment_vnd),
          }))
        );
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Không tải được dữ liệu"))
      .finally(() => setLoading(false));
  }, [caseId]);

  function updateRel(i: number, patch: Partial<Relationship>) {
    setRelationships((prev) => prev.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));
  }

  async function handleSave() {
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      const payload = {
        notes: notes || null,
        existing_credit_relationships: relationships
          .filter((r) => r.institution.trim() !== "")
          .map((r) => ({
            institution: r.institution, credit_type: r.credit_type,
            outstanding_vnd: r.outstanding_vnd === "" ? null : Number(r.outstanding_vnd),
            monthly_payment_vnd: r.monthly_payment_vnd === "" ? null : Number(r.monthly_payment_vnd),
          })),
      };
      await updateCaseSection(caseId, "other", payload);
      setSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Lưu thất bại");
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <p className="text-sm text-gray-500">Đang tải...</p>;

  return (
    <div className="bg-white rounded-xl border border-gray-100 p-5 space-y-4">
      <h3 className="text-sm font-semibold text-msb-navy">Hồ sơ khác</h3>

      <div>
        <label className="block text-xs font-medium text-msb-navy mb-1">Ghi chú</label>
        <textarea
          className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
          rows={3}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
        />
      </div>

      <div className="border-t pt-4 space-y-3">
        <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide">
          Quan hệ tín dụng hiện có tại MSB/tổ chức khác
        </p>
        {relationships.map((r, i) => (
          <div key={i} className="grid grid-cols-1 sm:grid-cols-[1fr_1fr_1fr_1fr_auto] gap-2 items-end border-b border-gray-50 pb-3">
            <div>
              <label className="block text-xs text-gray-500 mb-1">Tổ chức tín dụng</label>
              <input className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" value={r.institution} onChange={(e) => updateRel(i, { institution: e.target.value })} />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Hình thức cấp tín dụng</label>
              <input className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" value={r.credit_type} onChange={(e) => updateRel(i, { credit_type: e.target.value })} />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Dư nợ còn lại (VND)</label>
              <input type="number" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" value={r.outstanding_vnd} onChange={(e) => updateRel(i, { outstanding_vnd: e.target.value })} />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">Trả hàng tháng (VND)</label>
              <input type="number" className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" value={r.monthly_payment_vnd} onChange={(e) => updateRel(i, { monthly_payment_vnd: e.target.value })} />
            </div>
            <button onClick={() => setRelationships((prev) => prev.filter((_, idx) => idx !== i))} className="text-red-500 p-2">
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        ))}
        <button
          onClick={() => setRelationships((prev) => [...prev, { ...EMPTY_REL }])}
          className="inline-flex items-center gap-1.5 text-sm text-msb-navy underline"
        >
          <Plus className="h-4 w-4" /> Thêm quan hệ tín dụng
        </button>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}
      <div className="flex items-center gap-3 border-t pt-3">
        <button onClick={handleSave} disabled={saving} className="bg-msb-orange text-white text-sm font-semibold px-4 py-2 rounded-lg disabled:opacity-50">
          {saving ? "Đang lưu..." : "Lưu"}
        </button>
        {saved && <span className="text-xs text-green-600">Đã lưu.</span>}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Wire all three into `RbPortal.tsx`**

```typescript
// add imports
import { LoanTab } from "./tabs/LoanTab";
import { CollateralTab } from "./tabs/CollateralTab";
import { OtherDocsTab } from "./tabs/OtherDocsTab";
// add render lines
        {activeTab === "loan" && caseId && <LoanTab caseId={caseId} />}
        {activeTab === "collateral" && caseId && <CollateralTab caseId={caseId} />}
        {activeTab === "other" && caseId && <OtherDocsTab caseId={caseId} />}
```

- [ ] **Step 5: Typecheck**

Run: `cd web && npx tsc --noEmit -p .`
Expected: clean

- [ ] **Step 6: Commit**

```bash
git add web/components/rb-portal/
git commit -m "feat(rb-portal): add Loan, Collateral, and Other-docs tabs"
```

---

## Task 16: Frontend — `DocumentsTab.tsx`

**Files:**
- Create: `web/components/rb-portal/tabs/DocumentsTab.tsx`
- Modify: `web/components/rb-portal/RbPortal.tsx`

**Interfaces:**
- Consumes: `uploadDocument`, `listDocuments`, `RbDocument` (Task 11).

- [ ] **Step 1: Write the component**

```typescript
// web/components/rb-portal/tabs/DocumentsTab.tsx
"use client";

import { useEffect, useState } from "react";
import { UploadCloud } from "lucide-react";
import { RbDocument, listDocuments, uploadDocument } from "@/lib/rb-portal-api";

const CATEGORIES = [
  { value: "LEGAL", label: "Pháp lý" }, { value: "INCOME", label: "Nguồn thu" },
  { value: "LOAN", label: "Khoản vay" }, { value: "COLLATERAL", label: "Tài sản bảo đảm" },
  { value: "OTHER", label: "Khác" },
];

const STATUS_LABEL: Record<string, string> = {
  UPLOADED: "Đã tải lên", PROCESSING: "Đang xử lý", EXTRACTED: "Đã trích xuất",
  FAILED: "Không đọc được", NEED_OCR_VLM: "Cần OCR thủ công",
};
const STATUS_STYLE: Record<string, string> = {
  UPLOADED: "bg-gray-100 text-gray-600", PROCESSING: "bg-amber-100 text-amber-700",
  EXTRACTED: "bg-green-100 text-green-700", FAILED: "bg-red-100 text-red-700",
  NEED_OCR_VLM: "bg-amber-100 text-amber-700",
};

export function DocumentsTab({ caseId }: { caseId: string }) {
  const [docs, setDocs] = useState<RbDocument[]>([]);
  const [category, setCategory] = useState("LEGAL");
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function reload() {
    listDocuments(caseId).then(setDocs).catch(() => setDocs([]));
  }

  useEffect(reload, [caseId]);

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      await uploadDocument(caseId, file, category);
      reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Tải lên thất bại");
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  }

  return (
    <div className="bg-white rounded-xl border border-gray-100 p-5 space-y-4">
      <h3 className="text-sm font-semibold text-msb-navy">Tải lên chứng từ</h3>

      <div className="flex flex-wrap items-center gap-3 border border-dashed border-gray-300 rounded-lg p-3 bg-gray-50/60">
        <select
          className="border border-gray-200 rounded-lg px-3 py-2 text-sm"
          value={category}
          onChange={(e) => setCategory(e.target.value)}
        >
          {CATEGORIES.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
        </select>
        <label className="inline-flex items-center gap-1.5 text-xs font-semibold text-msb-navy bg-white border border-msb-navy/10 rounded-full px-3.5 py-1.5 cursor-pointer hover:bg-msb-bg">
          <UploadCloud className="h-3.5 w-3.5" />
          {uploading ? "Đang tải..." : "Chọn tệp"}
          <input type="file" className="hidden" onChange={handleUpload} disabled={uploading} />
        </label>
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}

      {docs.length === 0 ? (
        <p className="text-sm text-gray-500">Chưa có chứng từ nào.</p>
      ) : (
        <ul className="divide-y">
          {docs.map((d) => (
            <li key={d.id} className="py-2.5 flex items-center justify-between gap-3">
              <div className="min-w-0">
                <p className="text-sm font-medium text-msb-navy truncate">{d.filename}</p>
                <p className="text-xs text-gray-500">
                  {CATEGORIES.find((c) => c.value === d.category)?.label ?? d.category}
                  {d.document_type ? ` · ${d.document_type}` : ""}
                </p>
              </div>
              <span className={`text-xs font-semibold px-2.5 py-1 rounded-full shrink-0 ${STATUS_STYLE[d.status] ?? "bg-gray-100 text-gray-600"}`}>
                {STATUS_LABEL[d.status] ?? d.status}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Wire into `RbPortal.tsx`**

```typescript
// add import
import { DocumentsTab } from "./tabs/DocumentsTab";
// add render line
        {activeTab === "documents" && caseId && <DocumentsTab caseId={caseId} />}
```

- [ ] **Step 3: Typecheck**

Run: `cd web && npx tsc --noEmit -p .`
Expected: clean

- [ ] **Step 4: Commit**

```bash
git add web/components/rb-portal/
git commit -m "feat(rb-portal): add Documents tab with category upload and status badges"
```

---

## Task 17: Frontend — `AssessmentTab.tsx`

**Files:**
- Create: `web/components/rb-portal/tabs/AssessmentTab.tsx`
- Modify: `web/components/rb-portal/RbPortal.tsx`

**Interfaces:**
- Consumes: `runPreliminaryAssessment`, `runFullAssessment`, `RbSummary`
  (Task 11).

- [ ] **Step 1: Write the component**

```typescript
// web/components/rb-portal/tabs/AssessmentTab.tsx
"use client";

import { useState } from "react";
import { RbSummary, runFullAssessment, runPreliminaryAssessment } from "@/lib/rb-portal-api";

export function AssessmentTab({ caseId }: { caseId: string }) {
  const [loading, setLoading] = useState<"preliminary" | "full" | null>(null);
  const [result, setResult] = useState<RbSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run(kind: "preliminary" | "full") {
    setLoading(kind);
    setError(null);
    setResult(null);
    try {
      const body = kind === "preliminary" ? await runPreliminaryAssessment(caseId) : await runFullAssessment(caseId);
      setResult(body);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Thẩm định thất bại");
    } finally {
      setLoading(null);
    }
  }

  return (
    <div className="bg-white rounded-xl border border-gray-100 p-5 space-y-4">
      <h3 className="text-sm font-semibold text-msb-navy">Thẩm định</h3>
      <p className="text-xs text-gray-500">
        Thẩm định sơ bộ chạy được ngay khi có dữ liệu tối thiểu. Thẩm định đầy đủ yêu cầu đủ
        checklist bắt buộc (xem tab Tổng hợp) — nếu thiếu sẽ báo lỗi thay vì chạy ngầm.
      </p>
      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => run("preliminary")}
          disabled={loading !== null}
          className="bg-msb-orange text-white text-sm font-semibold px-4 py-2 rounded-lg disabled:opacity-50"
        >
          {loading === "preliminary" ? "Đang chạy..." : "Chạy thẩm định sơ bộ"}
        </button>
        <button
          onClick={() => run("full")}
          disabled={loading !== null}
          className="border border-msb-navy text-msb-navy text-sm font-semibold px-4 py-2 rounded-lg disabled:opacity-50"
        >
          {loading === "full" ? "Đang chạy..." : "Chạy thẩm định đầy đủ"}
        </button>
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}
      {result && (
        <div className="border-t pt-3 space-y-1 text-sm">
          <p><span className="font-medium">Kết quả:</span> {result.credit_readiness}</p>
          <p><span className="font-medium">Khuyến nghị:</span> {result.recommendation}</p>
          <p className="text-xs text-gray-500">Xem chi tiết đầy đủ ở tab Tổng hợp.</p>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Wire into `RbPortal.tsx`**

```typescript
// add import
import { AssessmentTab } from "./tabs/AssessmentTab";
// add render line
        {activeTab === "assessment" && caseId && <AssessmentTab caseId={caseId} />}
```

- [ ] **Step 3: Typecheck**

Run: `cd web && npx tsc --noEmit -p .`
Expected: clean

- [ ] **Step 4: Commit**

```bash
git add web/components/rb-portal/
git commit -m "feat(rb-portal): add Assessment tab with preliminary/full run buttons"
```

---

## Task 18: Frontend — `SummaryTab.tsx` (the reference-layout tab)

**Files:**
- Create: `web/components/rb-portal/tabs/SummaryTab.tsx`
- Modify: `web/components/rb-portal/RbPortal.tsx`

**Interfaces:**
- Consumes: `getSummary`, `exportMb01a`, `RbSummary` (Task 11);
  `MetricCard`, `MetricValue` from `web/components/shared/MetricCard.tsx`;
  `RiskFlagsSection` from `web/components/shared/RiskFlagsSection.tsx`;
  `AiInsightSection` from `web/components/shared/AiInsightSection.tsx`;
  `SectionHeader` from `web/components/shared/SectionHeader.tsx` (all
  existing, unmodified — read them if any prop is unclear, they were
  written for the EB/RB result panels and take the exact same shapes this
  task produces).
- Produces: `SummaryTab({ caseId, onEditSection }: { caseId: string; onEditSection: (tab: string) => void })`.

- [ ] **Step 1: Write the component**

```typescript
// web/components/rb-portal/tabs/SummaryTab.tsx
"use client";

import { useEffect, useState } from "react";
import { Banknote, CheckCircle2, ClipboardList, FileDown, FileText, FolderOpen, IdCard } from "lucide-react";
import { RbSummary, exportMb01a, getSummary } from "@/lib/rb-portal-api";
import { AiInsightSection } from "../../shared/AiInsightSection";
import { RiskFlagsSection } from "../../shared/RiskFlagsSection";
import { MetricCard, MetricValue } from "../../shared/MetricCard";
import { SectionHeader } from "../../shared/SectionHeader";

const METRIC_LABELS: Record<string, { label: string; unit: string }> = {
  eligible_monthly_income: { label: "Thu nhập đủ điều kiện", unit: "VND" },
  new_loan_first_month_payment: { label: "Trả nợ tháng đầu (khoản vay mới)", unit: "VND" },
  total_monthly_obligation: { label: "Tổng nghĩa vụ trả nợ hàng tháng", unit: "VND" },
  dti: { label: "Tỷ lệ nợ trên thu nhập (DTI)", unit: "" },
  dsr: { label: "Tỷ lệ trả nợ (DSR)", unit: "" },
  remaining_disposable_income: { label: "Thu nhập khả dụng còn lại", unit: "VND" },
};

const MISSING_LABEL: Record<string, string> = {
  legal_identity: "Giấy tờ định danh", id_document: "Giấy tờ pháp lý (CCCD/ĐKKD)",
  income_section: "Thông tin nguồn thu", income_source_type: "Nguồn thu nhập chính",
  tax_declaration: "Tờ khai thuế", loan_request: "Thông tin nhu cầu vay",
  loan_purpose: "Mục đích vay",
};

const READINESS_LABEL: Record<string, string> = {
  PRELIMINARY_READY: "Sẵn sàng thẩm định sơ bộ",
  PRELIMINARY_READY_WITH_CONDITIONS: "Sẵn sàng có điều kiện",
  INSUFFICIENT_DATA: "Chưa đủ dữ liệu",
  MANUAL_REVIEW_REQUIRED: "Cần thẩm định thủ công",
};

export function SummaryTab({ caseId, onEditSection }: { caseId: string; onEditSection: (tab: string) => void }) {
  const [summary, setSummary] = useState<RbSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);

  function reload() {
    getSummary(caseId).then(setSummary).catch((err) => setError(err instanceof Error ? err.message : "Không tải được"));
  }

  useEffect(reload, [caseId]);

  async function handleExport() {
    setExporting(true);
    try {
      const blob = await exportMb01a(caseId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `MB01A_QT.RR.038_lan_3_${caseId}.docx`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Xuất tờ trình thất bại.");
    } finally {
      setExporting(false);
    }
  }

  if (error) return <p className="text-sm text-red-600">{error}</p>;
  if (!summary) return <p className="text-sm text-gray-500">Đang tải...</p>;

  const customer = (summary.customer ?? {}) as Record<string, unknown>;
  const loan = (summary.loan ?? {}) as Record<string, unknown>;

  return (
    <div className="space-y-5">
      <div className="bg-white rounded-xl border border-gray-100 p-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs text-gray-400">Hồ sơ &gt; {summary.case_id} &gt; Tổng hợp</p>
          <h2 className="text-lg font-bold text-msb-navy">Kết quả thẩm định sơ bộ</h2>
        </div>
        <button
          onClick={handleExport}
          disabled={exporting}
          className="inline-flex items-center gap-1.5 bg-msb-navy text-white text-sm font-semibold px-4 py-2 rounded-lg disabled:opacity-50"
        >
          <FileDown className="h-4 w-4" />
          {exporting ? "Đang xuất..." : "Xuất MB01A QT.RR.038 (lần 3)"}
        </button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
        <div className="bg-white rounded-xl border border-gray-100 p-5 space-y-2">
          <div className="flex items-center justify-between">
            <SectionHeader icon={IdCard} title="Thông tin khách hàng" />
            <button onClick={() => onEditSection("customer")} className="text-xs text-msb-navy underline shrink-0">Chỉnh sửa</button>
          </div>
          <p className="text-sm"><span className="text-gray-500">Họ tên:</span> {String(customer.full_name ?? "—")}</p>
          <p className="text-sm"><span className="text-gray-500">MST:</span> {summary.tax_id}</p>
        </div>
        <div className="bg-white rounded-xl border border-gray-100 p-5 space-y-2">
          <div className="flex items-center justify-between">
            <SectionHeader icon={Banknote} title="Thông tin khoản vay đề nghị" />
            <button onClick={() => onEditSection("loan")} className="text-xs text-msb-navy underline shrink-0">Chỉnh sửa</button>
          </div>
          <p className="text-sm"><span className="text-gray-500">Sản phẩm:</span> {String(loan.product ?? "—")}</p>
          <p className="text-sm"><span className="text-gray-500">Số tiền:</span> {loan.amount_vnd ? `${loan.amount_vnd} VND` : "—"}</p>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-gray-100 p-5 space-y-3">
        <SectionHeader icon={ClipboardList} title="Chỉ tiêu tài chính sơ bộ" />
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {Object.entries(summary.credit_engine)
            .filter(([key]) => key in METRIC_LABELS)
            .map(([key, metric]) => (
              <MetricCard key={key} label={METRIC_LABELS[key].label} unit={METRIC_LABELS[key].unit} metric={metric as MetricValue} />
            ))}
        </div>
      </div>

      <div className="bg-white rounded-xl border border-gray-100 p-5 space-y-1">
        <SectionHeader icon={CheckCircle2} title="Đánh giá & Khuyến nghị" />
        <p className="text-sm font-semibold text-msb-navy">{READINESS_LABEL[summary.credit_readiness] ?? summary.credit_readiness}</p>
        <p className="text-xs text-gray-500">{summary.recommendation}</p>
      </div>

      <RiskFlagsSection flags={summary.risk_flags} title="Điểm cần lưu ý" />

      <div className="bg-white rounded-xl border border-gray-100 p-5 space-y-2">
        <SectionHeader icon={ClipboardList} title="Trạng thái hồ sơ" />
        <ol className="flex flex-wrap gap-3 text-xs">
          {summary.timeline.map((step) => (
            <li key={step.status} className={`px-3 py-1.5 rounded-full ${step.reached ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-400"}`}>
              {step.label}
            </li>
          ))}
        </ol>
      </div>

      <div className="bg-white rounded-xl border border-gray-100 p-5 space-y-2">
        <SectionHeader icon={FileText} title={`Hồ sơ còn thiếu (${summary.missing_data.length})`} />
        {summary.missing_data.length === 0 ? (
          <p className="text-sm text-gray-500">Không có.</p>
        ) : (
          <ul className="text-sm list-disc list-inside space-y-1">
            {summary.missing_data.map((m, i) => (
              <li key={i}>
                {MISSING_LABEL[m] ?? m} <span className="text-xs text-gray-400">({m})</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="bg-white rounded-xl border border-gray-100 p-5 space-y-2">
        <SectionHeader icon={FolderOpen} title={`Hồ sơ đã tải lên (${summary.documents.length})`} />
        {summary.documents.length === 0 ? (
          <p className="text-sm text-gray-500">Chưa có tệp nào.</p>
        ) : (
          <ul className="text-sm divide-y">
            {summary.documents.map((d) => (
              <li key={d.id} className="py-2 flex justify-between gap-3">
                <span className="truncate">{d.filename}</span>
                <span className="text-xs text-gray-400 shrink-0">{d.category} · {d.status}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <AiInsightSection why={summary.why} creditMemo={summary.credit_memo} title="AI Insight" />
    </div>
  );
}
```

- [ ] **Step 2: Wire into `RbPortal.tsx`**

```typescript
// add import
import { SummaryTab } from "./tabs/SummaryTab";
// add render line
        {activeTab === "summary" && caseId && <SummaryTab caseId={caseId} onEditSection={(tab) => setActiveTab(tab as TabKey)} />}
```

- [ ] **Step 3: Typecheck**

Run: `cd web && npx tsc --noEmit -p .`
Expected: clean

- [ ] **Step 4: Commit**

```bash
git add web/components/rb-portal/
git commit -m "feat(rb-portal): add Summary tab matching the reference layout"
```

---

## Task 19: Frontend — `HistoryTab.tsx` + real `ZaloBotModal.tsx`

**Files:**
- Create: `web/components/rb-portal/tabs/HistoryTab.tsx`
- Modify: `web/components/rb-portal/ZaloBotModal.tsx` (replace Task 12's stub)
- Modify: `web/components/rb-portal/RbPortal.tsx`

**Interfaces:**
- Consumes: `getHistory`, `RbHistoryVersion`, `getZaloQrStatus` (Task 11).

- [ ] **Step 1: Write `HistoryTab.tsx`**

```typescript
// web/components/rb-portal/tabs/HistoryTab.tsx
"use client";

import { useEffect, useState } from "react";
import { RbHistoryVersion, getHistory } from "@/lib/rb-portal-api";

const KIND_LABEL: Record<string, string> = { PRELIMINARY: "Thẩm định sơ bộ", FULL: "Thẩm định đầy đủ" };

export function HistoryTab({ caseId }: { caseId: string }) {
  const [versions, setVersions] = useState<RbHistoryVersion[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getHistory(caseId).then(setVersions).catch((err) => setError(err instanceof Error ? err.message : "Không tải được"));
  }, [caseId]);

  if (error) return <p className="text-sm text-red-600">{error}</p>;

  return (
    <div className="bg-white rounded-xl border border-gray-100 p-5 space-y-3">
      <h3 className="text-sm font-semibold text-msb-navy">Lịch sử thẩm định</h3>
      {versions.length === 0 ? (
        <p className="text-sm text-gray-500">Chưa có lần thẩm định nào.</p>
      ) : (
        <ul className="divide-y">
          {versions.map((v) => (
            <li key={v.version} className="py-2.5">
              <p className="text-sm font-medium text-msb-navy">
                Phiên bản {v.version} — {KIND_LABEL[v.kind] ?? v.kind}
              </p>
              <p className="text-xs text-gray-500">
                {new Date(v.created_at).toLocaleString("vi-VN")} · {v.computed.credit_readiness}
              </p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Replace `ZaloBotModal.tsx`'s stub with the real QR fetch**

```typescript
// web/components/rb-portal/ZaloBotModal.tsx
"use client";

import { useEffect, useState } from "react";
import { X, MessageCircle } from "lucide-react";
import { getZaloQrStatus } from "@/lib/rb-portal-api";

export function ZaloBotModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [status, setStatus] = useState<{ status: string; qr_url: string | null; message: string } | null>(null);

  useEffect(() => {
    if (open) getZaloQrStatus().then(setStatus).catch(() => setStatus(null));
  }, [open]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30" onClick={onClose}>
      <div className="bg-white rounded-xl p-6 max-w-sm w-full mx-4 space-y-3 text-center" onClick={(e) => e.stopPropagation()}>
        <div className="flex justify-end">
          <button onClick={onClose}><X className="h-5 w-5 text-gray-400" /></button>
        </div>
        <MessageCircle className="h-10 w-10 text-msb-navy mx-auto" />
        <h3 className="text-sm font-semibold text-msb-navy">Trợ lý Zalo M-Insight360</h3>
        {status?.qr_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={status.qr_url} alt="Zalo QR" className="mx-auto w-40 h-40" />
        ) : (
          <div className="mx-auto w-40 h-40 rounded-lg bg-gray-100 flex items-center justify-center text-xs text-gray-400 px-3">
            Chưa có mã QR
          </div>
        )}
        <p className="text-xs text-gray-500">{status?.message ?? "Đang tải..."}</p>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Wire `HistoryTab` into `RbPortal.tsx`**

```typescript
// add import
import { HistoryTab } from "./tabs/HistoryTab";
// add render line
        {activeTab === "history" && caseId && <HistoryTab caseId={caseId} />}
```

- [ ] **Step 4: Typecheck**

Run: `cd web && npx tsc --noEmit -p .`
Expected: clean

- [ ] **Step 5: Commit**

```bash
git add web/components/rb-portal/
git commit -m "feat(rb-portal): add History tab and wire real Zalo QR placeholder modal"
```

---

## Task 20: Frontend — wire `RbPortal` into `page.tsx`, remove old RB flow

**Files:**
- Modify: `web/app/page.tsx`

**Interfaces:**
- Consumes: `RbPortal` (default export, Task 12).
- Produces: RB tab renders `<RbPortal />` exclusively; the existing
  `AssessmentForm`/`HistoryPanel`/`ResultPanel` trio, currently shared
  across all three tabs, is rendered **only** for `tab === "eb"` and
  `tab === "crosssell"` — never for `"rb"`. `ResultPanel.tsx` itself
  (`web/components/ResultPanel.tsx`, the old RB result view) is left on
  disk but has no remaining caller once this task lands — read
  `web/app/page.tsx` in full before editing, since `handleRerunWithPeriod`
  and `lastEbFiles` state must stay untouched (EB-only, unrelated to this
  change).

- [ ] **Step 1: Edit `page.tsx`**

Replace the current unconditional `<AssessmentForm ... />` +
`<HistoryPanel ... />` block plus the three result-panel conditionals with:

```typescript
// add import
import dynamic from "next/dynamic";
const RbPortal = dynamic(() => import("@/components/rb-portal/RbPortal"), { ssr: false });
```

```typescript
// Replace the existing block that starts with
//   <AssessmentForm
//     agentType={tab}
//     ...
//   />
//   <HistoryPanel agentType={tab} onSelect={setResult} refreshKey={historyRefreshKey} />
//   {result && tab === "crosssell" && <CrossSellPanel result={result} />}
//   {result && tab === "eb" && <EbResultPanel result={result} onRerunWithPeriod={handleRerunWithPeriod} />}
//   {result && tab === "rb" && <ResultPanel result={result} />}
// with:
        {tab === "rb" ? (
          <RbPortal />
        ) : (
          <>
            <AssessmentForm
              agentType={tab}
              onStart={(customerName, taxId) => {
                const id = startHistoryPlaceholder(tab, customerName, taxId);
                setHistoryRefreshKey((k) => k + 1);
                return id;
              }}
              onResult={(r, historyId) => {
                setResult(r);
                if (historyId !== undefined) {
                  finishHistoryPlaceholder(tab, historyId, { status: "success", result: r });
                }
                setHistoryRefreshKey((k) => k + 1);
              }}
              onError={(message, historyId) => {
                if (historyId !== undefined) {
                  finishHistoryPlaceholder(tab, historyId, { status: "failed", errorMessage: message });
                }
                setHistoryRefreshKey((k) => k + 1);
              }}
              onSubmitted={
                tab === "eb"
                  ? (files, customerName, taxId) => setLastEbFiles({ files, customerName, taxId })
                  : undefined
              }
            />
            <HistoryPanel agentType={tab} onSelect={setResult} refreshKey={historyRefreshKey} />
            {result && tab === "crosssell" && <CrossSellPanel result={result} />}
            {result && tab === "eb" && <EbResultPanel result={result} onRerunWithPeriod={handleRerunWithPeriod} />}
          </>
        )}
```

`RbPortal` is loaded with `next/dynamic({ ssr: false })` because `next build`
in this repo runs `output: "export"` static generation — `RbPortal`'s data
fetching all happens client-side against `/api/rb-portal/...`, exactly like
every other tab's components, so this matches the existing pattern (no
other component in this codebase pre-fetches at build time either); it's
written explicitly here only because `RbPortal` is a `"use client"`
component reached via a fresh dynamic import rather than a static one,
where Next's export step is pickier about verifying there is no
server-only code path.

- [ ] **Step 2: Typecheck**

Run: `cd web && npx tsc --noEmit -p .`
Expected: clean

- [ ] **Step 3: Build**

Run: `cd web && npm run build`
Expected: succeeds

- [ ] **Step 4: Commit**

```bash
git add web/app/page.tsx
git commit -m "feat(rb-portal): wire RB Portal into the RB tab, retire the one-shot RB flow"
```

---

## Task 21: Full verification, deploy, live check

**Files:** none (verification only)

- [ ] **Step 1: Full backend suite**

Run: `/usr/local/bin/python -m pytest -q`
Expected: all pass (baseline 503 + ~55 new tests across Tasks 1–10 ≈ 558)

- [ ] **Step 2: Frontend typecheck + build**

Run: `cd web && npx tsc --noEmit -p . && npm run build`
Expected: both clean

- [ ] **Step 3: Local end-to-end smoke test**

Start a local server serving both the built frontend and the API (same
pattern used for prior local verification in this repo's history):

```bash
DB_PATH=/tmp/rb_portal_verify.db CASE_FILES_DIR=/tmp/rb_portal_verify_files \
  /usr/local/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8899 &
```

Using Playwright against `http://127.0.0.1:8899`, exercise the full flow in
one script and assert no console errors, no unhandled exceptions, and no
horizontal page overflow at both 1440px and 390px viewports (same
`document.documentElement.scrollWidth <= clientWidth` check this repo's
prior EB verification work used):
1. Click RB tab → Overview tab renders, create a case with a customer name
   and tax ID → redirected into the Customer tab.
2. Fill and save Customer, Legal, Income (source_type = "business", tick
   tax_declaration_present), Loan, Collateral (add one item), Other (add
   one credit relationship) tabs — confirm each "Đã lưu." confirmation
   appears.
3. Documents tab: upload one small `.csv` file under category LEGAL —
   confirm it appears in the list with a status badge.
4. Assessment tab: click "Chạy thẩm định sơ bộ" — confirm a
   `credit_readiness` value renders.
5. Summary tab: confirm all cards render (customer, loan, 6 metric cards,
   readiness, risk flags, timeline, missing-docs, uploaded-docs, AI
   Insight) and that clicking "Xuất MB01A QT.RR.038 (lần 3)" downloads a
   non-empty `.docx` file.
6. History tab: confirm the one saved PRELIMINARY version is listed.
7. Click the "Zalo Chat Bot" button in the sidebar — confirm the modal
   opens and shows the "Chưa kết nối" placeholder message (not a blank/
   broken state).
8. Switch to the EB tab and the Cross-sell tab — confirm both still work
   exactly as before (regression check: this plan must not have broken
   them).

- [ ] **Step 4: Report the LibreOffice/checkbox-rendering limitation honestly**

The exported `.docx` from Step 3.5 has not been visually confirmed to show
checked boxes as checked (Task 8/9's documented container limitation) —
open it with `python-docx` and confirm `w:default/@w:val="1"` on the
expected checkboxes (gender, marital status if set, "Đã/đang có khoản tín
dụng" if a credit relationship was added) as the available substitute
verification, and say so plainly in the final report rather than claiming
full visual confirmation.

- [ ] **Step 5: Push and deploy**

```bash
git push -u origin claude/pensive-hamilton-tu2cdx
```

Wait for the "Deploy to GreenNode AgentBase" GitHub Actions workflow to go
green on this branch before Step 6.

- [ ] **Step 6: Live verification on production**

Repeat the Step 3 flow (steps 1–8) against the production URL via
Playwright, exactly as this repo's prior EB/history-redesign work did —
retry navigation/actions on transient proxy failures (`net::ERR_TOO_MANY_RETRIES`)
rather than treating a single flaky attempt as a real bug; only escalate a
finding once it reproduces on a clean run.

- [ ] **Step 7: Report to the user**

Summarize: what was built (all 21 tasks), the explicit scope exclusions
already agreed (no login/SSO, Zalo QR placeholder, credit-card/hạn mức
khung/vợ-chồng/người-bảo-lãnh sections of MB01A left blank), and the
LibreOffice visual-verification gap from Step 4 — in Vietnamese, matching
this session's established reporting convention.

