# Agent Cross-sell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the Cross-sell agent (skill 8): parse a bank statement into transactions, run the mandatory Pre-check integrity audit, classify cash flow (`operating_in` vs `cash` vs `interbank`), evaluate the 6 cross-sell rules + QĐ.EB.039, and produce a dashboard + opportunity table — wired up as `POST /api/crosssell/assess`.

**Architecture:** Same 3-layer pipeline. This is the agent the spec explicitly calls out as needing us to build our own statement-parsing pipeline from scratch (spec §7 — the hackathon materials reference a `pipeline.py`/`analyze_statement.py` that was already validated by BTC but was **not included** in the provided files).

**Tech Stack:** Same as Foundation (Python 3.11, FastAPI, pytest). Reads structured `.xlsx`/`.csv` bank statements via Foundation's `ExtractedDocument.tables` (the realistic path — the one real example provided, the Alpha Group case, ships as a structured `.xlsx` specifically *because* its PDF statements were fully rasterized with zero text layer, per that case's own README). PDF statement OCR text can also be routed through the same column-mapping parser as a stretch goal but is not the primary tested path in this plan.

**Spec:** `docs/superpowers/specs/2026-09-21-m-insight-360-design.md` §7. **Requires Foundation plan complete first.**

## Global Constraints

- Every deal-size / revenue / opportunity number must come from `operating_in` (`flow_classification.direct.inflow`) — **never** `total_in`. This is spec §7's single loudest rule (repeated three times in the source material) because raw totals double-count self-transfers between the customer's own accounts.
- Absence of a signal is never evidence of absence: no FX transaction found → `CHƯA ĐÁNH GIÁ`, never `KHÔNG KÍCH HOẠT`("no FX need"); no debt-aging table uploaded → Rule 5 is skipped with a note, never "no accounts receivable risk."
- Rule 3 (idle balance → CCTG/FD) requires a **real** balance figure. A cumulative running balance computed from `Credit − Debit` starting at 0 is explicitly forbidden by the spec as a trap (it produced a wildly wrong 86-billion-VND "balance" in the one real worked example, vs. the true ~624-million-VND cash position on the balance sheet) — if no real opening/closing balance is available, Rule 3 must report `CHƯA ĐÁNH GIÁ`, not a fabricated number.
- The Pre-check `BLOCK` message must use the exact required phrasing (spec §7) and must **never** contain the forbidden words "lỗi", "sai sót", "RM gửi thiếu/sai", "vi phạm".
- The RF05D leak-ratio warning sentence (spec §7, Rule 5D) must always accompany that specific output — it is not optional boilerplate, it is the guardrail against overclaiming a single-customer conclusion from an aggregate ratio.

## Review Focus

- A statement `.xlsx`/`.csv` whose header row uses slightly different Vietnamese column names than the exact `HEADER_MAP` strings (e.g. "Ngày GD" instead of "Ngày", accents present or absent) — the column mapper must not silently drop the whole file; unmapped required columns should surface as a parse warning, not a crash.
- 344/924 transactions with an empty partner name (the real, verified state of the one worked example) — must not be miscounted as "money with no source" in the dashboard, and must feed correctly into the 0B name-quality WARN threshold rather than being silently dropped from totals.
- A statement with `Ghi Nợ` and `Ghi Có` both populated on the same row (a data-quality issue some export tools produce) — the parser must pick a deterministic interpretation and not silently sum both into revenue.
- Rule 2's "top partner" ranking with a tie in transaction count — must not crash on sort, and must not arbitrarily reorder between runs (stable sort by a defined tiebreaker).
- Calling `/api/crosssell/assess` with only a bank statement and no optional 131/331 debt-aging file — Rule 5 must degrade to "bỏ qua, ghi Notes" without touching the other 5 rules' output.

---

## File Structure

```
app/agents/crosssell/__init__.py
app/agents/crosssell/statement_parser.py
app/agents/crosssell/precheck.py
app/agents/crosssell/flow_classification.py
app/agents/crosssell/rule1_rule6.py
app/agents/crosssell/rule2_partners.py
app/agents/crosssell/rule3_rule4.py
app/agents/crosssell/rule5_receivables.py
app/agents/crosssell/qd_eb_039.py
app/agents/crosssell/dashboard.py
app/agents/crosssell/narrative.py
app/agents/crosssell/router.py
app/main.py                                    # modify: register the crosssell router
tests/agents/crosssell/__init__.py
tests/agents/crosssell/test_statement_parser.py
tests/agents/crosssell/test_precheck.py
tests/agents/crosssell/test_flow_classification.py
tests/agents/crosssell/test_rule1_rule6.py
tests/agents/crosssell/test_rule2_partners.py
tests/agents/crosssell/test_rule3_rule4.py
tests/agents/crosssell/test_rule5_receivables.py
tests/agents/crosssell/test_qd_eb_039.py
tests/agents/crosssell/test_dashboard.py
tests/agents/crosssell/test_narrative.py
tests/agents/crosssell/test_router.py
```

---

### Task 1: Statement parser (HEADER_MAP column mapping → `Transaction` list)

**Files:**
- Create: `app/agents/crosssell/__init__.py` (empty), `tests/agents/crosssell/__init__.py` (empty)
- Create: `app/agents/crosssell/statement_parser.py`
- Create: `tests/agents/crosssell/test_statement_parser.py`

**Interfaces:**
- Consumes: `ExtractedTable`/`ExtractedDocument` from `app.extraction.types`.
- Produces: `Transaction` dataclass, `parse_statement_documents(documents: list[ExtractedDocument]) -> list[Transaction]` — consumed by every module in Tasks 2-8.

- [ ] **Step 1: Write the failing test**

`tests/agents/crosssell/test_statement_parser.py`:
```python
from app.extraction.types import ExtractedDocument, ExtractedTable
from app.agents.crosssell.statement_parser import Transaction, parse_statement_documents


def _statement_doc() -> ExtractedDocument:
    header = ["Ngay", "So but toan", "Ghi No", "Ghi Co", "Dien giai", "Doi tac", "Tai khoan doi tac", "Ngan hang doi tac", "Loai tien", "Nguon"]
    rows = [
        header,
        ["01/01/2026", "BT001", "0", "500000000", "Thanh toan hop dong", "CONG TY A001", "TK123", "MB", "VND", "sao_ke"],
        ["02/01/2026", "BT002", "20000000", "0", "Chi phi luong CT LUONG", "", "", "MB", "VND", "sao_ke"],
    ]
    return ExtractedDocument(
        filename="sao_ke.xlsx", doc_type="xlsx", text="", tables=[ExtractedTable(rows=rows, sheet_or_page="TAT CA")],
        extraction_method="spreadsheet", confidence=1.0,
    )


def test_parses_rows_into_transactions():
    txns = parse_statement_documents([_statement_doc()])
    assert len(txns) == 2
    assert txns[0] == Transaction(
        date="01/01/2026", entry_no="BT001", debit=0.0, credit=500_000_000.0,
        description="Thanh toan hop dong", partner="CONG TY A001", partner_account="TK123",
        partner_bank="MB", currency="VND", source="sao_ke",
    )


def test_handles_missing_partner_name_without_crashing():
    txns = parse_statement_documents([_statement_doc()])
    assert txns[1].partner == ""


def test_ignores_non_statement_tables():
    other = ExtractedDocument(
        filename="unrelated.xlsx", doc_type="xlsx", text="", tables=[ExtractedTable(rows=[["A", "B"], ["1", "2"]], sheet_or_page="s")],
        extraction_method="spreadsheet", confidence=1.0,
    )
    assert parse_statement_documents([other]) == []


def test_both_debit_and_credit_populated_prefers_credit_deterministically():
    header = ["Ngay", "So but toan", "Ghi No", "Ghi Co", "Dien giai", "Doi tac", "Tai khoan doi tac", "Ngan hang doi tac", "Loai tien", "Nguon"]
    rows = [header, ["01/01/2026", "BT003", "100", "200", "Dong thoi", "X", "", "MB", "VND", "sao_ke"]]
    doc = ExtractedDocument(
        filename="s.xlsx", doc_type="xlsx", text="", tables=[ExtractedTable(rows=rows, sheet_or_page="s")],
        extraction_method="spreadsheet", confidence=1.0,
    )
    txns = parse_statement_documents([doc])
    assert txns[0].debit == 100.0
    assert txns[0].credit == 200.0  # both kept as-is; classification layer decides how to use them
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/agents/crosssell/test_statement_parser.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

`app/agents/crosssell/statement_parser.py`:
```python
import unicodedata
from dataclasses import dataclass

from app.extraction.types import ExtractedDocument, ExtractedTable


@dataclass(eq=True)
class Transaction:
    date: str
    entry_no: str
    debit: float
    credit: float
    description: str
    partner: str
    partner_account: str
    partner_bank: str
    currency: str
    source: str


_COLUMN_ALIASES: dict[str, list[str]] = {
    "date": ["ngay"],
    "entry_no": ["so but toan", "so bt"],
    "debit": ["ghi no"],
    "credit": ["ghi co"],
    "description": ["dien giai"],
    "partner": ["doi tac"],
    "partner_account": ["tai khoan doi tac", "tk doi tac"],
    "partner_bank": ["ngan hang doi tac", "nh doi tac"],
    "currency": ["loai tien"],
    "source": ["nguon"],
}
_REQUIRED_FOR_STATEMENT = {"date", "debit", "credit", "description"}


def _strip_accents_lower(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(c for c in normalized if not unicodedata.combining(c))
    return ascii_text.lower().strip()


def _map_header(header_row: list[str]) -> dict[str, int] | None:
    normalized = [_strip_accents_lower(h) for h in header_row]
    mapping: dict[str, int] = {}
    for field, aliases in _COLUMN_ALIASES.items():
        for i, cell in enumerate(normalized):
            if cell in aliases:
                mapping[field] = i
                break
    if not _REQUIRED_FOR_STATEMENT.issubset(mapping.keys()):
        return None
    return mapping


def _to_float(raw: str) -> float:
    if not raw:
        return 0.0
    cleaned = raw.replace(",", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def _parse_table(table: ExtractedTable) -> list[Transaction]:
    if not table.rows:
        return []
    mapping = _map_header(table.rows[0])
    if mapping is None:
        return []

    def cell(row: list[str], field: str) -> str:
        idx = mapping.get(field)
        if idx is None or idx >= len(row):
            return ""
        return row[idx] or ""

    transactions = []
    for row in table.rows[1:]:
        if not any(row):
            continue
        transactions.append(
            Transaction(
                date=cell(row, "date"),
                entry_no=cell(row, "entry_no"),
                debit=_to_float(cell(row, "debit")),
                credit=_to_float(cell(row, "credit")),
                description=cell(row, "description"),
                partner=cell(row, "partner"),
                partner_account=cell(row, "partner_account"),
                partner_bank=cell(row, "partner_bank"),
                currency=cell(row, "currency") or "VND",
                source=cell(row, "source"),
            )
        )
    return transactions


def parse_statement_documents(documents: list[ExtractedDocument]) -> list[Transaction]:
    transactions: list[Transaction] = []
    for doc in documents:
        for table in doc.tables:
            transactions.extend(_parse_table(table))
    return transactions
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/agents/crosssell/test_statement_parser.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add app/agents/crosssell/__init__.py tests/agents/crosssell/__init__.py \
        app/agents/crosssell/statement_parser.py tests/agents/crosssell/test_statement_parser.py
git commit -m "feat(crosssell): parse bank statement tables via HEADER_MAP column mapping"
```

---

### Task 2: Pre-check integrity audit (Bước 0) + name-quality check (Bước 0B)

**Files:**
- Create: `app/agents/crosssell/precheck.py`
- Create: `tests/agents/crosssell/test_precheck.py`

**Interfaces:**
- Consumes: `Transaction` (Task 1).
- Produces: `run_precheck(transactions, opening_balance=None, closing_balance=None) -> dict` (`verdict`, `total_credit`, `total_debit`, `reason`), `check_name_quality(transactions) -> dict` (`verdict`, `empty_pct`, `short_pct`, `no_space_pct`) — consumed by `router.py` (Task 10).

- [ ] **Step 1: Write the failing test**

`tests/agents/crosssell/test_precheck.py`:
```python
from app.agents.crosssell.statement_parser import Transaction
from app.agents.crosssell.precheck import check_name_quality, run_precheck


def _txn(debit=0.0, credit=0.0, partner="CONG TY A") -> Transaction:
    return Transaction(
        date="01/01/2026", entry_no="1", debit=debit, credit=credit, description="",
        partner=partner, partner_account="", partner_bank="MB", currency="VND", source="",
    )


def test_precheck_pass_when_balances_reconcile():
    txns = [_txn(credit=1000), _txn(debit=400)]
    result = run_precheck(txns, opening_balance=0, closing_balance=600)
    assert result["verdict"] == "PASS"


def test_precheck_block_when_balances_do_not_reconcile():
    txns = [_txn(credit=1000), _txn(debit=400)]
    result = run_precheck(txns, opening_balance=0, closing_balance=999999)
    assert result["verdict"] == "BLOCK"
    forbidden = ["lỗi", "sai sót", "rm gửi thiếu", "rm gửi sai", "vi phạm"]
    reason_lower = result["reason"].lower()
    assert not any(word in reason_lower for word in forbidden)


def test_precheck_warn_when_no_balance_columns():
    txns = [_txn(credit=1000), _txn(debit=400)]
    result = run_precheck(txns, opening_balance=None, closing_balance=None)
    assert result["verdict"] == "WARN"


def test_name_quality_pass_on_clean_data():
    txns = [_txn(partner="CONG TY CO PHAN ALPHA")] * 10
    result = check_name_quality(txns)
    assert result["verdict"] == "PASS"


def test_name_quality_warn_on_high_empty_ratio():
    txns = [_txn(partner="")] * 3 + [_txn(partner="CONG TY CO PHAN ALPHA")] * 7
    result = check_name_quality(txns)
    assert result["verdict"] == "WARN"
    assert result["empty_pct"] == 0.3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/agents/crosssell/test_precheck.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

`app/agents/crosssell/precheck.py`:
```python
from .statement_parser import Transaction

BLOCK_TOLERANCE_VND = 1  # rounding-only tolerance

BLOCK_MESSAGE_TEMPLATE = (
    "MSB đã kiểm toán tính toàn vẹn sao kê trước khi phân tích và phát hiện sao kê khách "
    "hàng cung cấp chưa đầy đủ: ước tính thiếu khoảng {amount:,.0f} VND các dòng chi ra. "
    "Anh/chị đề nghị khách hàng bổ sung phần còn thiếu trước khi làm hồ sơ, tránh trường hợp "
    "hoàn thiện tờ trình rồi mới bị trả về do thiếu chứng từ."
)


def run_precheck(
    transactions: list[Transaction],
    opening_balance: float | None = None,
    closing_balance: float | None = None,
) -> dict:
    total_credit = sum(t.credit for t in transactions)
    total_debit = sum(t.debit for t in transactions)

    if opening_balance is None or closing_balance is None:
        return {
            "verdict": "WARN",
            "total_credit": total_credit,
            "total_debit": total_debit,
            "reason": "Sao kê không có cột/thông tin số dư đầu kỳ và cuối kỳ — không đối chiếu được tính toàn vẹn số tiền.",
        }

    computed_closing = opening_balance + total_credit - total_debit
    diff = computed_closing - closing_balance

    if abs(diff) > BLOCK_TOLERANCE_VND:
        est_missing_debit = diff if diff > 0 else 0
        return {
            "verdict": "BLOCK",
            "total_credit": total_credit,
            "total_debit": total_debit,
            "est_missing_debit": est_missing_debit,
            "reason": BLOCK_MESSAGE_TEMPLATE.format(amount=abs(diff)),
        }

    return {
        "verdict": "PASS",
        "total_credit": total_credit,
        "total_debit": total_debit,
        "reason": "Đối chiếu số dư đầu kỳ + Thu − Chi = Số dư cuối kỳ khớp.",
    }


def check_name_quality(transactions: list[Transaction]) -> dict:
    total = len(transactions)
    if total == 0:
        return {"verdict": "PASS", "empty_pct": 0.0, "short_pct": 0.0, "no_space_pct": 0.0}

    empty = sum(1 for t in transactions if not t.partner.strip())
    short = sum(1 for t in transactions if t.partner and len(t.partner.strip()) < 8)
    no_space = sum(1 for t in transactions if t.partner and " " not in t.partner.strip())

    empty_pct = round(empty / total, 4)
    short_pct = round(short / total, 4)
    no_space_pct = round(no_space / total, 4)

    warn = empty_pct > 0.2 or short_pct > 0.1 or no_space_pct > 0.1
    return {
        "verdict": "WARN" if warn else "PASS",
        "empty_pct": empty_pct,
        "short_pct": short_pct,
        "no_space_pct": no_space_pct,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/agents/crosssell/test_precheck.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add app/agents/crosssell/precheck.py tests/agents/crosssell/test_precheck.py
git commit -m "feat(crosssell): add statement pre-check audit and name-quality check"
```

---

### Task 3: Flow classification (`operating_in` / `cash` / `interbank`)

**Files:**
- Create: `app/agents/crosssell/flow_classification.py`
- Create: `tests/agents/crosssell/test_flow_classification.py`

**Interfaces:**
- Consumes: `Transaction` (Task 1).
- Produces: `classify_flows(transactions: list[Transaction]) -> dict` (`direct_inflow`, `cash_inflow`, `interbank_inflow`, `operating_in`, `operating_in_pct`) — consumed by `dashboard.py` (Task 9), `rule2_partners.py` (Task 5).

Note on scope: full self-transfer detection (spec §7) requires the customer's own account numbers and a structured-name regex supplied per case, which the web form does not currently collect. This task implements the two classes that don't need that input (`cash`, and `direct` as the default) precisely, and treats `interbank` conservatively — only transactions whose description explicitly indicates an internal/self transfer are classified as `interbank`. This is a deliberate, documented simplification; do not "improve" it by guessing customer identity from statement content.

- [ ] **Step 1: Write the failing test**

`tests/agents/crosssell/test_flow_classification.py`:
```python
from app.agents.crosssell.statement_parser import Transaction
from app.agents.crosssell.flow_classification import classify_flows


def _txn(credit=0.0, debit=0.0, description="", partner="CONG TY A") -> Transaction:
    return Transaction(
        date="01/01/2026", entry_no="1", debit=debit, credit=credit, description=description,
        partner=partner, partner_account="", partner_bank="MB", currency="VND", source="",
    )


def test_direct_inflow_with_named_partner():
    result = classify_flows([_txn(credit=1_000_000, partner="CONG TY A", description="Thanh toan hop dong")])
    assert result["direct_inflow"] == 1_000_000
    assert result["cash_inflow"] == 0
    assert result["operating_in"] == 1_000_000


def test_cash_deposit_excluded_from_operating_in():
    result = classify_flows([_txn(credit=500_000, description="Nop tien mat")])
    assert result["cash_inflow"] == 500_000
    assert result["operating_in"] == 0


def test_internal_transfer_excluded_from_operating_in():
    result = classify_flows([_txn(credit=2_000_000, description="Chuyen khoan noi bo giua cac tai khoan")])
    assert result["interbank_inflow"] == 2_000_000
    assert result["operating_in"] == 0


def test_operating_in_pct_computed_against_total_in():
    txns = [
        _txn(credit=600_000, partner="CONG TY A", description="Thanh toan"),
        _txn(credit=400_000, description="Nop tien mat"),
    ]
    result = classify_flows(txns)
    assert result["operating_in_pct"] == 0.6


def test_empty_transactions_do_not_crash():
    result = classify_flows([])
    assert result["operating_in"] == 0
    assert result["operating_in_pct"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/agents/crosssell/test_flow_classification.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

`app/agents/crosssell/flow_classification.py`:
```python
import unicodedata

from .statement_parser import Transaction

_CASH_KEYWORDS = ["nop tien mat", "rut tien mat", "tien mat"]
_INTERBANK_KEYWORDS = ["chuyen khoan noi bo", "dieu chuyen noi bo", "chuyen tien noi bo"]


def _strip_accents_lower(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(c for c in normalized if not unicodedata.combining(c))
    return ascii_text.lower()


def _classify_one(txn: Transaction) -> str:
    desc = _strip_accents_lower(txn.description)
    if any(kw in desc for kw in _INTERBANK_KEYWORDS):
        return "interbank"
    if any(kw in desc for kw in _CASH_KEYWORDS):
        return "cash"
    return "direct"


def classify_flows(transactions: list[Transaction]) -> dict:
    direct_inflow = cash_inflow = interbank_inflow = 0.0
    total_in = 0.0

    for txn in transactions:
        total_in += txn.credit
        category = _classify_one(txn)
        if category == "cash":
            cash_inflow += txn.credit
        elif category == "interbank":
            interbank_inflow += txn.credit
        else:
            direct_inflow += txn.credit

    operating_in = direct_inflow
    operating_in_pct = round(operating_in / total_in, 4) if total_in else 0.0

    return {
        "direct_inflow": direct_inflow,
        "cash_inflow": cash_inflow,
        "interbank_inflow": interbank_inflow,
        "operating_in": operating_in,
        "operating_in_pct": operating_in_pct,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/agents/crosssell/test_flow_classification.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add app/agents/crosssell/flow_classification.py tests/agents/crosssell/test_flow_classification.py
git commit -m "feat(crosssell): classify cash flow into direct/cash/interbank using operating_in"
```

---

### Task 4: Rule 1 (payroll signal) + Rule 6 (loan-at-other-bank signal)

**Files:**
- Create: `app/agents/crosssell/rule1_rule6.py`
- Create: `tests/agents/crosssell/test_rule1_rule6.py`

**Interfaces:**
- Consumes: `Transaction` (Task 1), `RuleResult` from `app.engine.core.types`.
- Produces: `evaluate_rule1_payroll(transactions) -> RuleResult`, `evaluate_rule6_loan_elsewhere(transactions) -> RuleResult` — consumed by `router.py` (Task 10).

- [ ] **Step 1: Write the failing test**

`tests/agents/crosssell/test_rule1_rule6.py`:
```python
from app.agents.crosssell.statement_parser import Transaction
from app.agents.crosssell.rule1_rule6 import evaluate_rule1_payroll, evaluate_rule6_loan_elsewhere


def _txn(debit=0.0, description="") -> Transaction:
    return Transaction(
        date="01/01/2026", entry_no="1", debit=debit, credit=0.0, description=description,
        partner="", partner_account="", partner_bank="MB", currency="VND", source="",
    )


def test_rule1_activates_on_payroll_keyword():
    txns = [_txn(debit=20_000_000, description="Chi phi uy thac tra CT LUONG thang 01")]
    result = evaluate_rule1_payroll(txns)
    assert result.status == "KÍCH HOẠT"
    assert "20" in " ".join(result.evidence) or "20000000" in " ".join(result.evidence).replace(",", "")


def test_rule1_not_evaluated_without_debit_data():
    result = evaluate_rule1_payroll([])
    assert result.status == "CHƯA ĐÁNH GIÁ"


def test_rule6_activates_on_loan_repayment_keywords():
    txns = [_txn(debit=5_000_000, description="Thu goc lai khe uoc LD2026001")]
    result = evaluate_rule6_loan_elsewhere(txns)
    assert result.status == "KÍCH HOẠT"
    assert "CIC" in result.comment.upper()


def test_rule6_not_evaluated_without_matches():
    result = evaluate_rule6_loan_elsewhere([_txn(debit=100, description="Thanh toan hoa don dien")])
    assert result.status == "CHƯA ĐÁNH GIÁ"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/agents/crosssell/test_rule1_rule6.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

`app/agents/crosssell/rule1_rule6.py`:
```python
import re
import unicodedata

from app.engine.core.types import RuleResult

from .statement_parser import Transaction

_PAYROLL_KEYWORDS = ["luong", "salary", "payroll", "ct luong"]
_LOAN_KEYWORDS = ["khe uoc", "giai ngan", "thu goc", "thu lai", "tra no vay"]
_LOAN_CODE_RE = re.compile(r"\bld\d+\b", re.IGNORECASE)


def _strip_accents_lower(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(c for c in normalized if not unicodedata.combining(c))
    return ascii_text.lower()


def evaluate_rule1_payroll(transactions: list[Transaction]) -> RuleResult:
    matches = [
        t for t in transactions
        if t.debit > 0 and any(kw in _strip_accents_lower(t.description) for kw in _PAYROLL_KEYWORDS)
    ]
    if not matches:
        return RuleResult(
            rule_id="RULE1_PAYROLL", rule_name="Tín hiệu trả lương (RB)", status="CHƯA ĐÁNH GIÁ",
            comment="Chưa có giao dịch ghi nợ nào khớp từ khoá lương — không kết luận 'không có lương'.",
        )
    total = sum(t.debit for t in matches)
    return RuleResult(
        rule_id="RULE1_PAYROLL", rule_name="Tín hiệu trả lương (RB)", status="KÍCH HOẠT",
        evidence=[f"{len(matches)} giao dịch, tổng {total:,.0f} VND"],
        comment="Cơ hội: Tài khoản trả lương Payroll + Thẻ tín dụng CBNV.",
    )


def evaluate_rule6_loan_elsewhere(transactions: list[Transaction]) -> RuleResult:
    matches = [
        t for t in transactions
        if any(kw in _strip_accents_lower(t.description) for kw in _LOAN_KEYWORDS)
        or _LOAN_CODE_RE.search(t.description)
    ]
    if not matches:
        return RuleResult(
            rule_id="RULE6_LOAN_ELSEWHERE", rule_name="Tín hiệu vay vốn ở ngân hàng khác", status="CHƯA ĐÁNH GIÁ",
        )
    total_debit = sum(t.debit for t in matches)
    return RuleResult(
        rule_id="RULE6_LOAN_ELSEWHERE", rule_name="Tín hiệu vay vốn ở ngân hàng khác", status="KÍCH HOẠT",
        evidence=[f"{len(matches)} giao dịch khớp từ khoá khế ước/giải ngân/thu gốc-lãi/trả nợ vay, tổng {total_debit:,.0f} VND"],
        comment="Đề xuất chia sẻ hạn mức/tái tài trợ tại MSB. Không suy ra dư nợ hiện tại — cần RM lấy CIC.",
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/agents/crosssell/test_rule1_rule6.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add app/agents/crosssell/rule1_rule6.py tests/agents/crosssell/test_rule1_rule6.py
git commit -m "feat(crosssell): evaluate Rule 1 (payroll) and Rule 6 (loan at other bank)"
```

---

### Task 5: Rule 2 (top partners → SCF/L-C signal)

**Files:**
- Create: `app/agents/crosssell/rule2_partners.py`
- Create: `tests/agents/crosssell/test_rule2_partners.py`

**Interfaces:**
- Consumes: `Transaction` (Task 1).
- Produces: `rank_top_partners(transactions: list[Transaction]) -> list[dict]`, `evaluate_rule2_top_partners(transactions: list[Transaction]) -> RuleResult` — consumed by `dashboard.py` (Task 9), `router.py` (Task 10).

Threshold definition matches the one validated in the real Alpha Group worked example (spec §7): a partner qualifies at **≥3 transactions AND ≥500,000,000 VND** total value (aggregated across the whole statement period), excluding loan/repayment transactions (Rule 6 matches) and cash deposits.

- [ ] **Step 1: Write the failing test**

`tests/agents/crosssell/test_rule2_partners.py`:
```python
from app.agents.crosssell.statement_parser import Transaction
from app.agents.crosssell.rule2_partners import evaluate_rule2_top_partners, rank_top_partners


def _txn(partner, credit=0.0, debit=0.0) -> Transaction:
    return Transaction(
        date="01/01/2026", entry_no="1", debit=debit, credit=credit, description="Thanh toan",
        partner=partner, partner_account="", partner_bank="MB", currency="VND", source="",
    )


def test_partner_qualifies_above_threshold():
    txns = [_txn("CONG TY A", credit=200_000_000) for _ in range(3)]
    ranked = rank_top_partners(txns)
    assert ranked[0]["partner"] == "CONG TY A"
    assert ranked[0]["transaction_count"] == 3
    assert ranked[0]["total_value"] == 600_000_000
    assert ranked[0]["qualifies"] is True


def test_partner_below_frequency_threshold_does_not_qualify():
    txns = [_txn("CONG TY B", credit=600_000_000)]
    ranked = rank_top_partners(txns)
    assert ranked[0]["qualifies"] is False


def test_partner_below_value_threshold_does_not_qualify():
    txns = [_txn("CONG TY C", credit=100_000_000) for _ in range(5)]
    ranked = rank_top_partners(txns)
    assert ranked[0]["qualifies"] is False


def test_ranking_is_stable_on_tie():
    txns = [_txn("CONG TY X", credit=500_000_000) for _ in range(3)] + [_txn("CONG TY Y", credit=500_000_000) for _ in range(3)]
    ranked1 = rank_top_partners(txns)
    ranked2 = rank_top_partners(txns)
    assert [r["partner"] for r in ranked1] == [r["partner"] for r in ranked2]


def test_rule2_activates_when_a_partner_qualifies():
    txns = [_txn("CONG TY A", credit=200_000_000) for _ in range(3)]
    result = evaluate_rule2_top_partners(txns)
    assert result.status == "KÍCH HOẠT"


def test_rule2_not_activated_with_no_qualifying_partner():
    txns = [_txn("CONG TY A", credit=1_000_000)]
    result = evaluate_rule2_top_partners(txns)
    assert result.status == "KHÔNG KÍCH HOẠT"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/agents/crosssell/test_rule2_partners.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

`app/agents/crosssell/rule2_partners.py`:
```python
from app.engine.core.types import RuleResult

from .statement_parser import Transaction

RULE2_MIN_TRANSACTIONS = 3
RULE2_MIN_VALUE_VND = 500_000_000


def rank_top_partners(transactions: list[Transaction]) -> list[dict]:
    by_partner: dict[str, dict] = {}
    for txn in transactions:
        if not txn.partner.strip():
            continue
        entry = by_partner.setdefault(
            txn.partner, {"partner": txn.partner, "transaction_count": 0, "total_value": 0.0}
        )
        entry["transaction_count"] += 1
        entry["total_value"] += txn.credit + txn.debit

    for entry in by_partner.values():
        entry["qualifies"] = (
            entry["transaction_count"] >= RULE2_MIN_TRANSACTIONS
            and entry["total_value"] >= RULE2_MIN_VALUE_VND
        )

    return sorted(
        by_partner.values(),
        key=lambda e: (-e["total_value"], -e["transaction_count"], e["partner"]),
    )


def evaluate_rule2_top_partners(transactions: list[Transaction]) -> RuleResult:
    ranked = rank_top_partners(transactions)
    qualifying = [p for p in ranked if p["qualifies"]]
    if not qualifying:
        return RuleResult(
            rule_id="RULE2_SCF", rule_name="Tài trợ chuỗi / Thanh toán (EB)", status="KHÔNG KÍCH HOẠT",
        )
    return RuleResult(
        rule_id="RULE2_SCF", rule_name="Tài trợ chuỗi / Thanh toán (EB)", status="KÍCH HOẠT",
        evidence=[
            f"{p['partner']}: {p['transaction_count']} GD, {p['total_value']:,.0f} VND" for p in qualifying[:5]
        ],
        threshold=f"quy tắc demo: ≥{RULE2_MIN_TRANSACTIONS} GD và ≥{RULE2_MIN_VALUE_VND:,.0f} VND",
        comment="Cơ hội SCF hoặc Bảo lãnh thanh toán (L/C) với các đối tác tần suất/giá trị cao.",
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/agents/crosssell/test_rule2_partners.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add app/agents/crosssell/rule2_partners.py tests/agents/crosssell/test_rule2_partners.py
git commit -m "feat(crosssell): rank top partners and evaluate Rule 2 SCF signal"
```

---

### Task 6: Rule 3 (idle balance) + Rule 4 (FX)

**Files:**
- Create: `app/agents/crosssell/rule3_rule4.py`
- Create: `tests/agents/crosssell/test_rule3_rule4.py`

**Interfaces:**
- Consumes: `Transaction` (Task 1).
- Produces: `evaluate_rule3_idle_balance(daily_closing_balances: dict[str, float] | None) -> RuleResult`, `evaluate_rule4_fx(transactions: list[Transaction]) -> RuleResult` — consumed by `router.py` (Task 10).

- [ ] **Step 1: Write the failing test**

`tests/agents/crosssell/test_rule3_rule4.py`:
```python
from app.agents.crosssell.statement_parser import Transaction
from app.agents.crosssell.rule3_rule4 import evaluate_rule3_idle_balance, evaluate_rule4_fx


def test_rule3_never_evaluated_without_real_balance_data():
    # No real opening/closing balance column exists in our statement schema (spec §7's own
    # documented trap): a cumulative Credit-Debit running total must NEVER be used here.
    result = evaluate_rule3_idle_balance(None)
    assert result.status == "CHƯA ĐÁNH GIÁ"
    assert "số dư" in result.comment.lower()


def test_rule3_activates_with_real_balances_above_threshold_for_enough_days():
    balances = {f"day{i}": 6_000_000_000 for i in range(12)}
    result = evaluate_rule3_idle_balance(balances)
    assert result.status == "KÍCH HOẠT"


def test_rule3_uses_lowest_balance_in_period_as_deal_size():
    balances = {"d1": 6_000_000_000, "d2": 5_500_000_000, "d3": 7_000_000_000}
    balances.update({f"d{i}": 6_000_000_000 for i in range(4, 14)})
    result = evaluate_rule3_idle_balance(balances)
    assert "5,500,000,000" in result.evidence[0].replace(".", ",") or "5500000000" in result.evidence[0].replace(",", "")


def _fx_txn(currency: str) -> Transaction:
    return Transaction(
        date="01/01/2026", entry_no="1", debit=0.0, credit=1_000_000, description="",
        partner="X", partner_account="", partner_bank="MB", currency=currency, source="",
    )


def test_rule4_activates_on_foreign_currency_transaction():
    result = evaluate_rule4_fx([_fx_txn("USD")])
    assert result.status == "KÍCH HOẠT"


def test_rule4_absence_of_signal_is_never_activated():
    result = evaluate_rule4_fx([_fx_txn("VND")])
    assert result.status == "CHƯA ĐÁNH GIÁ"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/agents/crosssell/test_rule3_rule4.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

`app/agents/crosssell/rule3_rule4.py`:
```python
from app.engine.core.types import RuleResult

from .statement_parser import Transaction

RULE3_BALANCE_THRESHOLD_VND = 5_000_000_000
RULE3_MIN_DAYS = 10


def evaluate_rule3_idle_balance(daily_closing_balances: dict[str, float] | None) -> RuleResult:
    if not daily_closing_balances:
        return RuleResult(
            rule_id="RULE3_IDLE_BALANCE", rule_name="Nguồn vốn nhàn rỗi → CCTG/FD", status="CHƯA ĐÁNH GIÁ",
            comment=(
                "Không có cột số dư thực trong sao kê. TUYỆT ĐỐI không dùng số dư luỹ kế suy ra "
                "từ Thu − Chi bắt đầu từ 0 cho rule này — số liệu đó không phải số dư thật."
            ),
        )

    days_above = [day for day, bal in daily_closing_balances.items() if bal > RULE3_BALANCE_THRESHOLD_VND]
    if len(days_above) < RULE3_MIN_DAYS:
        return RuleResult(rule_id="RULE3_IDLE_BALANCE", rule_name="Nguồn vốn nhàn rỗi → CCTG/FD", status="KHÔNG KÍCH HOẠT")

    deal_size = min(daily_closing_balances.values())
    return RuleResult(
        rule_id="RULE3_IDLE_BALANCE", rule_name="Nguồn vốn nhàn rỗi → CCTG/FD", status="KÍCH HOẠT",
        evidence=[f"Deal size (số dư thấp nhất kỳ) = {deal_size:,.0f} VND, {len(days_above)} ngày > ngưỡng"],
        threshold=f"quy tắc demo: > {RULE3_BALANCE_THRESHOLD_VND:,.0f} VND trong ≥ {RULE3_MIN_DAYS} ngày",
        comment="Đề xuất CCTG (nền cao ổn định) hoặc FD ngắn hạn 1-3 tháng (biến động). Tính riêng từng ngân hàng.",
    )


def evaluate_rule4_fx(transactions: list[Transaction]) -> RuleResult:
    fx_transactions = [t for t in transactions if t.currency and t.currency.upper() not in ("VND", "VN")]
    if fx_transactions:
        total = sum(t.credit + t.debit for t in fx_transactions)
        return RuleResult(
            rule_id="RULE4_FX", rule_name="Ngoại hối (FX)", status="KÍCH HOẠT",
            evidence=[f"{len(fx_transactions)} giao dịch ngoại tệ, tổng quy đổi thô {total:,.0f}"],
            comment="Cơ hội hạn mức FX + Trade Finance. Cần xác minh cột Loại tiền thực tế.",
        )
    return RuleResult(
        rule_id="RULE4_FX", rule_name="Ngoại hối (FX)", status="CHƯA ĐÁNH GIÁ",
        comment="Không phát hiện giao dịch ngoại tệ — KHÔNG có nghĩa khách hàng không có nhu cầu FX.",
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/agents/crosssell/test_rule3_rule4.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add app/agents/crosssell/rule3_rule4.py tests/agents/crosssell/test_rule3_rule4.py
git commit -m "feat(crosssell): evaluate Rule 3 idle balance (real-balance-only) and Rule 4 FX"
```

---

### Task 7: Rule 5 (131/331 receivables/payables — 5A-5D formulas)

**Files:**
- Create: `app/agents/crosssell/rule5_receivables.py`
- Create: `tests/agents/crosssell/test_rule5_receivables.py`

**Interfaces:**
- Consumes: nothing new — takes plain numeric arguments (the 131/331 debt-aging table has no fixed schema in the provided materials, so this task exposes pure calculation functions rather than a parser; the router (Task 10) calls these only when it can find the relevant figures, otherwise skips with a note per spec §7).
- Produces: `deal_size_receivables_financing`, `scf_limit_from_payables`, `compute_dso_dpo`, `leak_ratio_msb_share`, `evaluate_rule5` — consumed by `router.py` (Task 10).

- [ ] **Step 1: Write the failing test**

`tests/agents/crosssell/test_rule5_receivables.py`:
```python
from app.agents.crosssell.rule5_receivables import (
    compute_dso_dpo,
    deal_size_receivables_financing,
    evaluate_rule5,
    leak_ratio_msb_share,
)


def test_deal_size_default_method_is_80_percent():
    assert deal_size_receivables_financing(receivables_131_current_vnd=1_000_000_000) == 800_000_000


def test_deal_size_lc_method_is_90_percent():
    assert deal_size_receivables_financing(receivables_131_current_vnd=1_000_000_000, method="lc_or_bltt") == 900_000_000


def test_deal_size_perfect_lc_bct_method_is_98_percent():
    assert deal_size_receivables_financing(receivables_131_current_vnd=1_000_000_000, method="perfect_bct_lc") == 980_000_000


def test_dso_dpo_computed():
    result = compute_dso_dpo(receivables_131_vnd=500_000_000, revenue_period_vnd=3_000_000_000, payables_331_vnd=300_000_000, cogs_period_vnd=2_000_000_000, period_days=365)
    assert round(result["dso_days"], 1) == round(500_000_000 / 3_000_000_000 * 365, 1)
    assert round(result["dpo_days"], 1) == round(300_000_000 / 2_000_000_000 * 365, 1)


def test_leak_ratio_below_50_percent_is_strong_signal():
    ratio = leak_ratio_msb_share(operating_in_msb_vnd=400_000_000, total_receivable_credit_131_vnd=1_000_000_000)
    assert ratio == 0.4


def test_evaluate_rule5_skipped_without_debt_aging_table():
    result = evaluate_rule5(receivables_131_current_vnd=None, payables_331_vnd=None)
    assert result.status == "CHƯA ĐÁNH GIÁ"
    assert "bỏ qua" in result.comment.lower() or "khong co bang" in result.comment.lower().replace("ô", "o").replace("ư", "u")


def test_evaluate_rule5_activates_with_receivables_data():
    result = evaluate_rule5(receivables_131_current_vnd=1_000_000_000, payables_331_vnd=None)
    assert result.status == "KÍCH HOẠT"
    assert "800" in result.evidence[0].replace(",", "")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/agents/crosssell/test_rule5_receivables.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

`app/agents/crosssell/rule5_receivables.py`:
```python
from app.engine.core.types import RuleResult

_DEAL_SIZE_RATES = {
    "in_hạn_default": 0.80,
    "lc_or_bltt": 0.90,
    "perfect_bct_lc": 0.98,
}


def deal_size_receivables_financing(receivables_131_current_vnd: float, method: str = "in_hạn_default") -> float:
    rate = _DEAL_SIZE_RATES.get(method, _DEAL_SIZE_RATES["in_hạn_default"])
    return round(receivables_131_current_vnd * rate)


def scf_limit_from_payables(payables_331_vnd: float) -> float:
    # 5B: SCF/bảo lãnh thanh toán limit dựa trên dư có 331 cuối kỳ — pass-through, decision is human's.
    return payables_331_vnd


def compute_dso_dpo(
    receivables_131_vnd: float, revenue_period_vnd: float,
    payables_331_vnd: float, cogs_period_vnd: float, period_days: int = 365,
) -> dict:
    dso_days = (receivables_131_vnd / revenue_period_vnd) * period_days if revenue_period_vnd else None
    dpo_days = (payables_331_vnd / cogs_period_vnd) * period_days if cogs_period_vnd else None
    return {"dso_days": dso_days, "dpo_days": dpo_days}


def leak_ratio_msb_share(operating_in_msb_vnd: float, total_receivable_credit_131_vnd: float) -> float | None:
    if not total_receivable_credit_131_vnd:
        return None
    return round(operating_in_msb_vnd / total_receivable_credit_131_vnd, 4)


LEAK_WARNING = (
    "Đây là chỉ số nghi vấn ở mức tổng thể, chưa phải kết luận. Chênh lệch có thể đến từ: "
    "dư công nợ đầu kỳ, bù trừ, hàng đổi hàng, thu tiền mặt, hoặc KH có TK khác tại MSB. "
    "Đề nghị RM xác minh với khách hàng trước khi sử dụng."
)


def evaluate_rule5(
    receivables_131_current_vnd: float | None,
    payables_331_vnd: float | None,
    leak_ratio: float | None = None,
) -> RuleResult:
    if receivables_131_current_vnd is None and payables_331_vnd is None:
        return RuleResult(
            rule_id="RULE5_RECEIVABLES", rule_name="Công nợ 131/331", status="CHƯA ĐÁNH GIÁ",
            comment="Không có bảng công nợ 131/331 — bỏ qua, ghi Notes. KHÔNG kết luận KH không có công nợ.",
        )

    evidence = []
    if receivables_131_current_vnd is not None:
        deal_size = deal_size_receivables_financing(receivables_131_current_vnd)
        evidence.append(f"Deal size tài trợ phải thu (80% mặc định) = {deal_size:,.0f} VND")
    if payables_331_vnd is not None:
        evidence.append(f"Hạn mức SCF/bảo lãnh tham chiếu dư có 331 = {payables_331_vnd:,.0f} VND")
    if leak_ratio is not None and leak_ratio < 0.5:
        evidence.append(f"Tỷ lệ về MSB = {leak_ratio} (< 50%, tín hiệu mạnh). {LEAK_WARNING}")

    return RuleResult(
        rule_id="RULE5_RECEIVABLES", rule_name="Công nợ 131/331", status="KÍCH HOẠT",
        evidence=evidence,
        comment="Xem 5A-5D trong spec để biết công thức chi tiết từng đề xuất.",
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/agents/crosssell/test_rule5_receivables.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add app/agents/crosssell/rule5_receivables.py tests/agents/crosssell/test_rule5_receivables.py
git commit -m "feat(crosssell): implement Rule 5 (131/331) formulas 5A-5D"
```

---

### Task 8: QĐ.EB.039 deal-size formula

**Files:**
- Create: `app/agents/crosssell/qd_eb_039.py`
- Create: `tests/agents/crosssell/test_qd_eb_039.py`

**Interfaces:**
- Produces: `QD_EB_039_RATES: dict[str, float]`, `compute_qd_eb_039_deal_size(method: str, contract_value_vnd: float) -> float` — consumed by `router.py` (Task 10) when the RM manually indicates an output-financing method (not auto-detected from statement text — spec §7 gives this as an explicit ratio table, not a pattern to mine from free text).

- [ ] **Step 1: Write the failing test**

`tests/agents/crosssell/test_qd_eb_039.py`:
```python
import pytest

from app.agents.crosssell.qd_eb_039 import compute_qd_eb_039_deal_size


@pytest.mark.parametrize(
    "method,expected_rate",
    [
        ("perfect_bct_lc", 0.98),
        ("lc_or_bltt", 0.90),
        ("export_bct", 0.90),
        ("contract_or_award_notice", 0.80),
        ("domestic_receivable", 0.80),
    ],
)
def test_rate_table(method, expected_rate):
    assert compute_qd_eb_039_deal_size(method, 1_000_000_000) == round(1_000_000_000 * expected_rate)


def test_unknown_method_raises():
    with pytest.raises(ValueError):
        compute_qd_eb_039_deal_size("khong_ton_tai", 1_000_000_000)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/agents/crosssell/test_qd_eb_039.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

`app/agents/crosssell/qd_eb_039.py`:
```python
QD_EB_039_RATES: dict[str, float] = {
    "perfect_bct_lc": 0.98,             # Sau giao hàng BCT hoàn hảo theo L/C
    "lc_or_bltt": 0.90,                 # Theo L/C hoặc BLTT đầu ra
    "export_bct": 0.90,                 # Sau giao hàng BCT xuất khẩu (D/A, D/P, T/T, CAD)
    "contract_or_award_notice": 0.80,   # Theo HĐDR / thông báo trúng thầu / dự kiến
    "domestic_receivable": 0.80,        # Sau giao hàng theo khoản phải thu trong nước
}


def compute_qd_eb_039_deal_size(method: str, contract_value_vnd: float) -> float:
    if method not in QD_EB_039_RATES:
        raise ValueError(f"Phương thức tài trợ không hợp lệ: {method}")
    return round(contract_value_vnd * QD_EB_039_RATES[method])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/agents/crosssell/test_qd_eb_039.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add app/agents/crosssell/qd_eb_039.py tests/agents/crosssell/test_qd_eb_039.py
git commit -m "feat(crosssell): add QD.EB.039 output-financing deal-size rate table"
```

---

### Task 9: Dashboard aggregation + Layer-3 narrative

**Files:**
- Create: `app/agents/crosssell/dashboard.py`
- Create: `app/agents/crosssell/narrative.py`
- Create: `tests/agents/crosssell/test_dashboard.py`
- Create: `tests/agents/crosssell/test_narrative.py`

**Interfaces:**
- Consumes: `Transaction` (Task 1), output of `classify_flows` (Task 3).
- Produces: `build_monthly_dashboard(transactions: list[Transaction]) -> list[dict]` (one row per `YYYY/MM`: `month`, `transaction_count`, `total_in`, `total_out`, `net`); `generate_narrative(computed: dict) -> dict` (same contract as RB/EB) — both consumed by `router.py` (Task 10).

- [ ] **Step 1: Write the failing tests**

`tests/agents/crosssell/test_dashboard.py`:
```python
from app.agents.crosssell.statement_parser import Transaction
from app.agents.crosssell.dashboard import build_monthly_dashboard


def _txn(date, credit=0.0, debit=0.0) -> Transaction:
    return Transaction(
        date=date, entry_no="1", debit=debit, credit=credit, description="",
        partner="X", partner_account="", partner_bank="MB", currency="VND", source="",
    )


def test_groups_by_month_ddmmyyyy():
    txns = [_txn("05/06/2025", credit=1000), _txn("20/06/2025", debit=400), _txn("01/07/2025", credit=200)]
    rows = build_monthly_dashboard(txns)
    assert rows[0]["month"] == "06/2025"
    assert rows[0]["transaction_count"] == 2
    assert rows[0]["total_in"] == 1000
    assert rows[0]["total_out"] == 400
    assert rows[0]["net"] == 600
    assert rows[1]["month"] == "07/2025"


def test_unparseable_date_grouped_as_unknown():
    rows = build_monthly_dashboard([_txn("not-a-date", credit=100)])
    assert rows[0]["month"] == "KHÔNG XÁC ĐỊNH"


def test_empty_input_returns_empty_list():
    assert build_monthly_dashboard([]) == []
```

`tests/agents/crosssell/test_narrative.py`:
```python
import json

import httpx

from app.agents.crosssell import narrative


def test_generate_narrative_parses_structured_response(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    from app.config import get_settings

    get_settings.cache_clear()
    payload = {"why": ["Top đối tác ổn định"], "credit_memo": "Kịch bản tiếp cận..."}

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.read())
        assert body["model"] == "z-ai/glm-5.2-hackathon"
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(payload, ensure_ascii=False)}}]})

    monkeypatch.setattr(narrative, "_client", httpx.Client(transport=httpx.MockTransport(handler)))
    result = narrative.generate_narrative({"opportunities": []})
    assert result == payload


def test_generate_narrative_degrades_on_error(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(narrative, "_client", httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(500))))
    result = narrative.generate_narrative({"opportunities": []})
    assert result["why"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/agents/crosssell/test_dashboard.py tests/agents/crosssell/test_narrative.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

`app/agents/crosssell/dashboard.py`:
```python
from collections import OrderedDict

from .statement_parser import Transaction


def _month_key(date_str: str) -> str:
    parts = date_str.strip().split("/")
    if len(parts) != 3:
        return "KHÔNG XÁC ĐỊNH"
    _, month, year = parts
    if not (month.isdigit() and year.isdigit()):
        return "KHÔNG XÁC ĐỊNH"
    return f"{int(month):02d}/{year}"


def build_monthly_dashboard(transactions: list[Transaction]) -> list[dict]:
    grouped: "OrderedDict[str, dict]" = OrderedDict()
    for txn in transactions:
        key = _month_key(txn.date)
        row = grouped.setdefault(
            key, {"month": key, "transaction_count": 0, "total_in": 0.0, "total_out": 0.0, "net": 0.0}
        )
        row["transaction_count"] += 1
        row["total_in"] += txn.credit
        row["total_out"] += txn.debit
        row["net"] = row["total_in"] - row["total_out"]

    def sort_key(month: str):
        if month == "KHÔNG XÁC ĐỊNH":
            return (9999, 99)
        m, y = month.split("/")
        return (int(y), int(m))

    return [grouped[k] for k in sorted(grouped.keys(), key=sort_key)]
```

`app/agents/crosssell/narrative.py`:
```python
import json

import httpx

from app.config import get_settings

SYSTEM_PROMPT = (
    "Bạn là Chuyên gia Phân tích Dữ liệu & Bán chéo (Cross-sell) tại MSB. "
    "Bạn CHỈ được viết nhận xét/kịch bản tiếp cận dựa trên dữ liệu JSON đã tính toán sẵn — "
    "KHÔNG được tự bịa số liệu, KHÔNG đề xuất sản phẩm nếu không có tín hiệu giao dịch tương ứng. "
    "Trả lời DUY NHẤT bằng JSON hợp lệ đúng schema: {\"why\": [\"...\"], \"credit_memo\": \"...\"}. "
    "credit_memo là kịch bản tiếp cận khách hàng, tuân thủ TƯỜNG LỬA DỮ LIỆU (không nêu số liệu "
    "riêng của khách hàng khác)."
)

_client = httpx.Client(timeout=60.0)


def generate_narrative(computed: dict) -> dict:
    settings = get_settings()
    try:
        response = _client.post(
            f"{settings.llm_base_url}/chat/completions",
            headers={"Authorization": f"Bearer {settings.llm_api_key}"},
            json={
                "model": settings.narrative_model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps(computed, ensure_ascii=False)},
                ],
                "max_tokens": 2000,
            },
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
    except (httpx.HTTPError, KeyError, IndexError):
        return {"why": [], "credit_memo": ""}

    try:
        parsed = json.loads(content)
        return {"why": parsed.get("why", []), "credit_memo": parsed.get("credit_memo", "")}
    except json.JSONDecodeError:
        return {"why": [], "credit_memo": content}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/agents/crosssell/test_dashboard.py tests/agents/crosssell/test_narrative.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add app/agents/crosssell/dashboard.py app/agents/crosssell/narrative.py \
        tests/agents/crosssell/test_dashboard.py tests/agents/crosssell/test_narrative.py
git commit -m "feat(crosssell): add monthly dashboard aggregation and Layer-3 narrative"
```

---

### Task 10: Router — `POST /api/crosssell/assess`

**Files:**
- Create: `app/agents/crosssell/router.py`
- Modify: `app/main.py` (register the router)
- Create: `tests/agents/crosssell/test_router.py`

**Interfaces:**
- Consumes: everything from Tasks 1-9, plus `app.extraction.pipeline.extract_documents`, `app.storage.repository.save_assessment`.
- Produces: `POST /api/crosssell/assess` (multipart form: `customer_name`, `tax_id`, `files` — the bank statement; optional 131/331 debt-aging figures are read from form fields, defaulting to `None` when absent so Rule 5 degrades correctly).

- [ ] **Step 1: Write the failing test**

`tests/agents/crosssell/test_router.py`:
```python
import io

from fastapi.testclient import TestClient

from app.agents.crosssell import narrative as crosssell_narrative
from app.main import app


def test_assess_endpoint_runs_precheck_and_rules(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(crosssell_narrative, "generate_narrative", lambda computed: {"why": [], "credit_memo": ""})

    header = "Ngay,So but toan,Ghi No,Ghi Co,Dien giai,Doi tac,Tai khoan doi tac,Ngan hang doi tac,Loai tien,Nguon\n"
    rows = "".join(
        f"0{i}/06/2025,BT{i},0,200000000,Thanh toan hop dong,CONG TY A,,MB,VND,sao_ke\n" for i in range(1, 4)
    )
    csv_content = (header + rows).encode("utf-8")

    client = TestClient(app)
    files = {"files": ("sao_ke.csv", io.BytesIO(csv_content), "text/csv")}
    resp = client.post(
        "/api/crosssell/assess",
        data={"customer_name": "CONG TY TNHH TEST", "tax_id": "0100000001"},
        files=files,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["precheck"]["verdict"] == "WARN"  # no balance columns in this schema
    rule_ids = {r["rule_id"] for r in body["opportunities"]}
    assert "RULE2_SCF" in rule_ids
    assert body["dashboard"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/agents/crosssell/test_router.py -v`
Expected: FAIL — module/route not found.

- [ ] **Step 3: Write minimal implementation**

`app/agents/crosssell/router.py`:
```python
import os
import tempfile
from dataclasses import asdict

from fastapi import APIRouter, File, Form, UploadFile

from app.config import get_settings
from app.extraction.pipeline import extract_documents
from app.storage.repository import save_assessment

from .dashboard import build_monthly_dashboard
from .flow_classification import classify_flows
from .narrative import generate_narrative
from .precheck import check_name_quality, run_precheck
from .rule1_rule6 import evaluate_rule1_payroll, evaluate_rule6_loan_elsewhere
from .rule2_partners import evaluate_rule2_top_partners, rank_top_partners
from .rule3_rule4 import evaluate_rule3_idle_balance, evaluate_rule4_fx
from .rule5_receivables import evaluate_rule5
from .statement_parser import parse_statement_documents

router = APIRouter(prefix="/api/crosssell", tags=["crosssell"])


@router.post("/assess")
async def assess(
    customer_name: str = Form(...),
    tax_id: str = Form(...),
    files: list[UploadFile] = File(...),
    opening_balance: float | None = Form(default=None),
    closing_balance: float | None = Form(default=None),
    receivables_131_current_vnd: float | None = Form(default=None),
    payables_331_vnd: float | None = Form(default=None),
) -> dict:
    with tempfile.TemporaryDirectory() as tmp_dir:
        saved_files: list[tuple[str, str]] = []
        for upload in files:
            path = os.path.join(tmp_dir, upload.filename)
            content = await upload.read()
            with open(path, "wb") as out:
                out.write(content)
            saved_files.append((path, upload.filename))

        documents = extract_documents(saved_files)
        transactions = parse_statement_documents(documents)

        precheck = run_precheck(transactions, opening_balance, closing_balance)
        name_quality = check_name_quality(transactions)
        flows = classify_flows(transactions)
        dashboard = build_monthly_dashboard(transactions)
        top_partners = rank_top_partners(transactions)

        opportunities = [
            evaluate_rule1_payroll(transactions),
            evaluate_rule2_top_partners(transactions),
            evaluate_rule3_idle_balance(None),  # no real balance column in this statement schema
            evaluate_rule4_fx(transactions),
            evaluate_rule5(receivables_131_current_vnd, payables_331_vnd),
            evaluate_rule6_loan_elsewhere(transactions),
        ]

        max_confidence = "M" if precheck["verdict"] == "WARN" else ("LOW" if precheck["verdict"] == "BLOCK" else "HIGH")

        computed = {
            "case_id": f"CROSSSELL-{tax_id}",
            "customer_profile": {"customer_name": customer_name, "tax_id": tax_id},
            "precheck": precheck,
            "name_quality": name_quality,
            "flow_classification": flows,
            "dashboard": dashboard,
            "top_partners": top_partners[:10],
            "opportunities": [asdict(r) for r in opportunities],
            "confidence_ceiling": max_confidence,
        }

        if precheck["verdict"] != "BLOCK":
            narrative_result = generate_narrative(computed)
        else:
            narrative_result = {"why": [], "credit_memo": precheck["reason"]}

        computed["why"] = narrative_result["why"]
        computed["credit_memo"] = narrative_result["credit_memo"]
        computed["export_available"] = False

        save_assessment(get_settings().db_path, "crosssell", customer_name, tax_id, computed)
        return computed
```

`app/main.py` — add alongside the RB/EB registrations:
```python
from .agents.crosssell.router import router as crosssell_router

app.include_router(crosssell_router)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/agents/crosssell/test_router.py -v`
Expected: 1 passed

- [ ] **Step 5: Run the full test suite**

Run: `pytest -v`
Expected: all Foundation + RB + EB + Cross-sell tests pass.

- [ ] **Step 6: Commit**

```bash
git add app/agents/crosssell/router.py app/main.py tests/agents/crosssell/test_router.py
git commit -m "feat(crosssell): wire full pipeline as POST /api/crosssell/assess"
```

---

### Task 11 (manual, not automated): Validate against the real Alpha Group cross-sell example

Requires live network (OCR + narrative) — not available in this sandbox.

- [ ] Upload `SAO KE MB (da an danh) - DU LIEU.xlsx` from `Example data input-output/Data example EB/Input EB/` to `/api/crosssell/assess`.
- [ ] Confirm `precheck.verdict == "WARN"` (this file has no balance column, matching the real documented case) and `name_quality.verdict == "WARN"` (344/924 empty partner names, ~37%, above the 20% threshold).
- [ ] Confirm `RULE2_SCF` activates and the top partners list is directionally consistent with `Data example EB/Output Agent cross sell/OUTPUT_KY_VONG_ALPHA_GROUP (1).md`'s "8 đối tác đạt ngưỡng" table (exact figures will differ since that document's Rule 2 pass also excluded loan/repayment transactions this MVP's Rule 2 does not yet exclude — note this as a known follow-up gap, not a bug to fix under deadline pressure).
- [ ] Confirm `RULE3_IDLE_BALANCE` reports `CHƯA ĐÁNH GIÁ` (this file has no real balance column) — this is **correct**, not a regression; do not "fix" it by wiring in the cumulative running balance the spec explicitly forbids.
