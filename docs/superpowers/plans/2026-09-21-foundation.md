# Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the shared substrate every agent (RB/EB/Cross-sell) plugs into: document extraction (text-layer + vision-LLM OCR), the deterministic-calculation core types, SQLite storage, the FastAPI app skeleton, and a minimal MSB-themed Next.js frontend — all inside the single Docker image already deployed successfully to GreenNode AgentBase.

**Architecture:** 3-layer pipeline per `docs/superpowers/specs/2026-09-21-m-insight-360-design.md` §2. This plan builds Layer 1 (extraction) and the Layer 2 *core types* (not agent-specific rules — those belong to the RB/EB/Cross-sell plans), plus storage, API skeleton, and frontend skeleton. Agent-specific plans each add one router file and wire it into `app/main.py` as their own first task.

**Tech Stack:** Python 3.11, FastAPI, PyMuPDF (`pymupdf`) for PDF text+rasterization, `python-docx`, `openpyxl`, `httpx` for the GreenNode MaaS OpenAI-compatible endpoint, `pytest`. Frontend: Next.js 14 (App Router, static export via `output: "export"`), TypeScript, Tailwind CSS. Frontend tasks are verified by `npm run build` + checking the emitted static HTML/JS for expected markers (no Jest/RTL setup — time-boxed for the hackathon deadline, per spec's "pipeline over UI polish" priority).

**Spec:** `docs/superpowers/specs/2026-09-21-m-insight-360-design.md`

## Global Constraints

- Every financial number the app ever displays must come from Layer 2 (code) or Layer 1 (extracted from a document) — never invented by an LLM. This plan's `Metric`/`RuleResult` types exist specifically to make that structural, not just a convention.
- Input formats to support: `.docx`, `.pdf`, `.xlsx`, `.xls`, `.csv` (spec §1, §3).
- Container contract (already relied on by the deployed CI/CD): listen on port 8080, `GET /health` → 200. Do not change the port or health path.
- SQLite only, local file in the container (spec §9 — data loss on redeploy is accepted, do not add an external DB).
- Design tokens: primary `#091E42` (navy), accent `#F4600C` (orange), background `#DEE5EF`/`#FFFFFF`, font **Inter** (spec §8).
- `LLM_API_KEY` / `LLM_BASE_URL` / model names come from environment variables only — never hardcode a key in source.

## Review Focus

- A `.pdf` that *has* a text layer but also embeds a scanned image page (mixed document) — must not silently drop the image page's content; at minimum must not crash.
- A file with an extension GreenNode/RM might plausibly upload but isn't supported (e.g. `.jpg`, `.png`, `.doc` legacy) — must return a clear, catchable error, not an unhandled exception that 500s the whole request.
- An `.xlsx` with a completely empty sheet, or a `.csv` with a BOM / non-UTF-8 encoding (very common from Vietnamese banking exports) — must not crash the parser.
- The OCR vision call failing (timeout, non-200, malformed JSON) for one page of a multi-page scanned PDF — must not lose the other pages' text, and must surface a warning rather than raising past the pipeline boundary.
- Two concurrent requests writing to SQLite at once (the web form + a retry) — must not corrupt the DB or silently lose a row (SQLite's default locking handles this if connections are opened/closed per call, which this plan does — the test proves it rather than assuming it).

---

## File Structure

```
requirements.txt                      # modify: add real deps
requirements-dev.txt                  # create: pytest, reportlab (fixture generation only)
app/
  main.py                             # modify: replace placeholder with real skeleton
  config.py                           # create
  extraction/
    __init__.py
    types.py
    docx_parser.py
    pdf_parser.py
    xlsx_csv_parser.py
    ocr_vision.py
    pipeline.py
  engine/
    __init__.py
    core/
      __init__.py
      types.py
  storage/
    __init__.py
    db.py
    repository.py
tests/
  __init__.py
  conftest.py
  fixtures/                           # generated binary fixtures, committed
    sample_text.pdf
    sample_scanned.pdf
    sample.docx
    sample.xlsx
    sample.csv
  test_extraction_docx.py
  test_extraction_pdf.py
  test_extraction_xlsx_csv.py
  test_extraction_pipeline.py
  test_engine_core.py
  test_storage.py
  test_main.py
web/
  package.json
  next.config.mjs
  tsconfig.json
  tailwind.config.ts
  postcss.config.mjs
  app/
    layout.tsx
    globals.css
    page.tsx
  components/
    AssessmentForm.tsx
    ResultPanel.tsx
  lib/
    api.ts
Dockerfile                            # modify: multi-stage build (Node → static export, then Python)
```

---

### Task 1: Fixture files + test scaffolding

**Files:**
- Create: `requirements-dev.txt`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/fixtures/sample_text.pdf`, `tests/fixtures/sample_scanned.pdf`, `tests/fixtures/sample.docx`, `tests/fixtures/sample.xlsx`, `tests/fixtures/sample.csv`

**Interfaces:**
- Produces: fixture file paths under `tests/fixtures/` that every later extraction test loads via the `fixtures_dir` pytest fixture defined in `conftest.py`.

- [ ] **Step 1: Add dev dependencies**

`requirements-dev.txt`:
```
pytest==8.3.4
reportlab==4.2.5
```

- [ ] **Step 2: Install dev dependencies**

Run: `pip install -r requirements.txt -r requirements-dev.txt`
Expected: installs cleanly (requirements.txt will be extended in Task 2 — for now just `pip install -r requirements-dev.txt` is enough to unblock this task).

- [ ] **Step 3: Write the fixture-generation script and run it once**

Create a throwaway script (do not commit it) at `/tmp/gen_fixtures.py`:
```python
import csv
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
import docx
import openpyxl

FIX = Path("tests/fixtures")
FIX.mkdir(parents=True, exist_ok=True)

# PDF with a real text layer
c = canvas.Canvas(str(FIX / "sample_text.pdf"), pagesize=A4)
c.drawString(100, 750, "MSB CREDITPILOT TEST DOCUMENT")
c.drawString(100, 730, "Doanh thu thuan: 1,000,000,000 VND")
c.save()

# PDF with no text layer (blank page — simulates a raster/scanned page)
c2 = canvas.Canvas(str(FIX / "sample_scanned.pdf"), pagesize=A4)
c2.showPage()
c2.save()

# DOCX with a paragraph and a table
d = docx.Document()
d.add_paragraph("Ho so khach hang: CONG TY TNHH TEST")
t = d.add_table(rows=2, cols=2)
t.rows[0].cells[0].text = "Chi tieu"
t.rows[0].cells[1].text = "Gia tri"
t.rows[1].cells[0].text = "Von dieu le"
t.rows[1].cells[1].text = "500000000"
d.save(str(FIX / "sample.docx"))

# XLSX with two sheets
wb = openpyxl.Workbook()
ws1 = wb.active
ws1.title = "Thang01"
ws1.append(["Ngay", "So tien"])
ws1.append(["01/01/2026", 1000000])
ws2 = wb.create_sheet("Thang02")
ws2.append(["Ngay", "So tien"])
ws2.append(["01/02/2026", 2000000])
wb.save(str(FIX / "sample.xlsx"))

# CSV with a UTF-8 BOM (common from Vietnamese banking exports)
with open(FIX / "sample.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Ngay", "Dien giai", "So tien"])
    w.writerow(["01/01/2026", "Chuyen khoan", "500000"])

print("Fixtures written to", FIX.resolve())
```

Run: `python /tmp/gen_fixtures.py`
Expected: prints the fixtures directory path; `tests/fixtures/` now contains 5 files.

- [ ] **Step 4: Write `tests/conftest.py`**

```python
from pathlib import Path
import pytest

@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"
```

`tests/__init__.py` is empty.

- [ ] **Step 5: Commit**

```bash
git add requirements-dev.txt tests/__init__.py tests/conftest.py tests/fixtures/
git commit -m "test: add extraction fixtures and pytest scaffolding"
```

---

### Task 2: `ExtractedDocument` / `ExtractedTable` types

**Files:**
- Create: `app/extraction/__init__.py` (empty)
- Create: `app/extraction/types.py`
- Test: `tests/test_extraction_docx.py` (imports types; the real docx test is Task 3)

**Interfaces:**
- Produces: `ExtractedDocument`, `ExtractedTable` dataclasses used by every parser and by every RB/EB/Cross-sell field-extraction step downstream.

- [ ] **Step 1: Write the failing test**

`tests/test_extraction_docx.py`:
```python
from app.extraction.types import ExtractedDocument, ExtractedTable

def test_extracted_document_constructs_with_defaults():
    doc = ExtractedDocument(
        filename="a.docx", doc_type="docx", text="hello",
        tables=[], extraction_method="docx", confidence=1.0,
    )
    assert doc.warnings == []
    assert doc.filename == "a.docx"

def test_extracted_table_holds_rows():
    t = ExtractedTable(rows=[["a", "b"], ["1", "2"]], sheet_or_page="Sheet1")
    assert t.rows[1] == ["1", "2"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_extraction_docx.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.extraction.types'`

- [ ] **Step 3: Write minimal implementation**

`app/extraction/__init__.py`: empty file.

`app/extraction/types.py`:
```python
from dataclasses import dataclass, field


@dataclass
class ExtractedTable:
    rows: list[list[str]]
    sheet_or_page: str


@dataclass
class ExtractedDocument:
    filename: str
    doc_type: str  # "pdf" | "docx" | "xlsx" | "csv"
    text: str
    tables: list[ExtractedTable]
    extraction_method: str  # "text_layer" | "docx" | "spreadsheet" | "vision_llm" | "no_text_layer" | "ocr_failed"
    confidence: float  # 0.0-1.0
    warnings: list[str] = field(default_factory=list)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_extraction_docx.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add app/extraction/__init__.py app/extraction/types.py tests/test_extraction_docx.py
git commit -m "feat: add ExtractedDocument/ExtractedTable core types"
```

---

### Task 3: DOCX parser

**Files:**
- Create: `app/extraction/docx_parser.py`
- Modify: `tests/test_extraction_docx.py` (add real parsing test)
- Modify: `requirements.txt` (add `python-docx`)

**Interfaces:**
- Consumes: `ExtractedDocument`, `ExtractedTable` from `app.extraction.types`.
- Produces: `extract_docx(file_path: str, filename: str) -> ExtractedDocument`, used by `app/extraction/pipeline.py` (Task 6).

- [ ] **Step 1: Add the dependency**

`requirements.txt` — add line:
```
python-docx==1.1.2
```
Run: `pip install -r requirements.txt`

- [ ] **Step 2: Write the failing test**

Append to `tests/test_extraction_docx.py`:
```python
from app.extraction.docx_parser import extract_docx

def test_extract_docx_reads_paragraphs_and_tables(fixtures_dir):
    doc = extract_docx(str(fixtures_dir / "sample.docx"), "sample.docx")
    assert "CONG TY TNHH TEST" in doc.text
    assert doc.doc_type == "docx"
    assert doc.extraction_method == "docx"
    assert doc.confidence == 1.0
    assert len(doc.tables) == 1
    assert doc.tables[0].rows[1] == ["Von dieu le", "500000000"]
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_extraction_docx.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.extraction.docx_parser'`

- [ ] **Step 4: Write minimal implementation**

`app/extraction/docx_parser.py`:
```python
import docx

from .types import ExtractedDocument, ExtractedTable


def extract_docx(file_path: str, filename: str) -> ExtractedDocument:
    d = docx.Document(file_path)
    text_parts = [p.text for p in d.paragraphs if p.text.strip()]
    tables = []
    for i, t in enumerate(d.tables):
        rows = [[cell.text for cell in row.cells] for row in t.rows]
        tables.append(ExtractedTable(rows=rows, sheet_or_page=f"table {i + 1}"))
    return ExtractedDocument(
        filename=filename,
        doc_type="docx",
        text="\n".join(text_parts),
        tables=tables,
        extraction_method="docx",
        confidence=1.0,
    )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_extraction_docx.py -v`
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add requirements.txt app/extraction/docx_parser.py tests/test_extraction_docx.py
git commit -m "feat: add docx extraction parser"
```

---

### Task 4: PDF parser (text layer + rasterization for OCR)

**Files:**
- Create: `app/extraction/pdf_parser.py`
- Create: `tests/test_extraction_pdf.py`
- Modify: `requirements.txt` (add `pymupdf`)

**Interfaces:**
- Consumes: `ExtractedDocument` from `app.extraction.types`.
- Produces: `extract_pdf(file_path: str, filename: str) -> ExtractedDocument`; `render_pdf_pages_to_images(file_path: str, dpi: int = 150) -> list[bytes]` (PNG bytes per page) — both consumed by `app/extraction/pipeline.py` (Task 6).

- [ ] **Step 1: Add the dependency**

`requirements.txt` — add line:
```
pymupdf==1.25.1
```
Run: `pip install -r requirements.txt`

- [ ] **Step 2: Write the failing test**

`tests/test_extraction_pdf.py`:
```python
from app.extraction.pdf_parser import extract_pdf, render_pdf_pages_to_images


def test_extract_pdf_with_text_layer(fixtures_dir):
    doc = extract_pdf(str(fixtures_dir / "sample_text.pdf"), "sample_text.pdf")
    assert "MSB CREDITPILOT TEST DOCUMENT" in doc.text
    assert doc.extraction_method == "text_layer"
    assert doc.confidence == 1.0
    assert doc.warnings == []


def test_extract_pdf_without_text_layer_flags_no_text_layer(fixtures_dir):
    doc = extract_pdf(str(fixtures_dir / "sample_scanned.pdf"), "sample_scanned.pdf")
    assert doc.extraction_method == "no_text_layer"
    assert doc.confidence == 0.0
    assert any("raster" in w.lower() or "ocr" in w.lower() for w in doc.warnings)


def test_render_pdf_pages_to_images_returns_one_png_per_page(fixtures_dir):
    images = render_pdf_pages_to_images(str(fixtures_dir / "sample_scanned.pdf"))
    assert len(images) == 1
    assert images[0][:8] == b"\x89PNG\r\n\x1a\n"  # PNG file signature
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_extraction_pdf.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.extraction.pdf_parser'`

- [ ] **Step 4: Write minimal implementation**

`app/extraction/pdf_parser.py`:
```python
import fitz  # pymupdf

from .types import ExtractedDocument

MIN_CHARS_FOR_TEXT_LAYER = 20


def extract_pdf(file_path: str, filename: str) -> ExtractedDocument:
    doc = fitz.open(file_path)
    try:
        text = "\n".join(page.get_text() for page in doc)
    finally:
        doc.close()

    has_text_layer = len(text.strip()) >= MIN_CHARS_FOR_TEXT_LAYER
    return ExtractedDocument(
        filename=filename,
        doc_type="pdf",
        text=text,
        tables=[],
        extraction_method="text_layer" if has_text_layer else "no_text_layer",
        confidence=1.0 if has_text_layer else 0.0,
        warnings=[] if has_text_layer else [
            "PDF không có lớp chữ (đã raster hoá hoặc là ảnh scan) — cần chạy OCR."
        ],
    )


def render_pdf_pages_to_images(file_path: str, dpi: int = 150) -> list[bytes]:
    doc = fitz.open(file_path)
    try:
        images = []
        for page in doc:
            pix = page.get_pixmap(dpi=dpi)
            images.append(pix.tobytes("png"))
        return images
    finally:
        doc.close()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_extraction_pdf.py -v`
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add requirements.txt app/extraction/pdf_parser.py tests/test_extraction_pdf.py
git commit -m "feat: add PDF extraction (text layer + page rasterization)"
```

---

### Task 5: XLSX/CSV parser

**Files:**
- Create: `app/extraction/xlsx_csv_parser.py`
- Create: `tests/test_extraction_xlsx_csv.py`
- Modify: `requirements.txt` (add `openpyxl`)

**Interfaces:**
- Consumes: `ExtractedDocument`, `ExtractedTable` from `app.extraction.types`.
- Produces: `extract_xlsx(file_path: str, filename: str) -> ExtractedDocument`, `extract_csv(file_path: str, filename: str) -> ExtractedDocument`, both consumed by `app/extraction/pipeline.py` (Task 6).

- [ ] **Step 1: Add the dependency**

`requirements.txt` — add line:
```
openpyxl==3.1.5
```
Run: `pip install -r requirements.txt`

- [ ] **Step 2: Write the failing test**

`tests/test_extraction_xlsx_csv.py`:
```python
from app.extraction.xlsx_csv_parser import extract_csv, extract_xlsx


def test_extract_xlsx_reads_all_sheets(fixtures_dir):
    doc = extract_xlsx(str(fixtures_dir / "sample.xlsx"), "sample.xlsx")
    assert doc.doc_type == "xlsx"
    assert doc.extraction_method == "spreadsheet"
    assert len(doc.tables) == 2
    sheet_names = {t.sheet_or_page for t in doc.tables}
    assert sheet_names == {"Thang01", "Thang02"}
    thang01 = next(t for t in doc.tables if t.sheet_or_page == "Thang01")
    assert thang01.rows[1] == ["01/01/2026", "1000000"]


def test_extract_csv_handles_utf8_bom(fixtures_dir):
    doc = extract_csv(str(fixtures_dir / "sample.csv"), "sample.csv")
    assert doc.doc_type == "csv"
    assert doc.tables[0].rows[0] == ["Ngay", "Dien giai", "So tien"]
    # BOM must not leak into the first header cell
    assert not doc.tables[0].rows[0][0].startswith("﻿")
    assert doc.tables[0].rows[1] == ["01/01/2026", "Chuyen khoan", "500000"]
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_extraction_xlsx_csv.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.extraction.xlsx_csv_parser'`

- [ ] **Step 4: Write minimal implementation**

`app/extraction/xlsx_csv_parser.py`:
```python
import csv

import openpyxl

from .types import ExtractedDocument, ExtractedTable


def extract_xlsx(file_path: str, filename: str) -> ExtractedDocument:
    wb = openpyxl.load_workbook(file_path, data_only=True)
    tables = []
    text_parts = []
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        rows = []
        for row in ws.iter_rows(values_only=True):
            str_row = ["" if cell is None else str(cell) for cell in row]
            rows.append(str_row)
            text_parts.append(" | ".join(str_row))
        tables.append(ExtractedTable(rows=rows, sheet_or_page=sheet_name))
    return ExtractedDocument(
        filename=filename,
        doc_type="xlsx",
        text="\n".join(text_parts),
        tables=tables,
        extraction_method="spreadsheet",
        confidence=1.0,
    )


def extract_csv(file_path: str, filename: str) -> ExtractedDocument:
    with open(file_path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    text = "\n".join(" | ".join(row) for row in rows)
    doc_type = "csv"
    return ExtractedDocument(
        filename=filename,
        doc_type=doc_type,
        text=text,
        tables=[ExtractedTable(rows=rows, sheet_or_page="csv")],
        extraction_method="spreadsheet",
        confidence=1.0,
    )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_extraction_xlsx_csv.py -v`
Expected: 2 passed

- [ ] **Step 6: Commit**

```bash
git add requirements.txt app/extraction/xlsx_csv_parser.py tests/test_extraction_xlsx_csv.py
git commit -m "feat: add xlsx/csv extraction parser"
```

---

### Task 6: Vision-LLM OCR call

**Files:**
- Create: `app/config.py`
- Create: `app/extraction/ocr_vision.py`
- Create: `tests/test_extraction_ocr_vision.py`
- Modify: `requirements.txt` (add `httpx`)

**Interfaces:**
- Consumes: `get_settings()` from `app.config`.
- Produces: `ocr_image(image_bytes: bytes, model: str | None = None) -> str`, consumed by `app/extraction/pipeline.py` (Task 7).

- [ ] **Step 1: Add the dependency**

`requirements.txt` — add line:
```
httpx==0.28.1
```
Run: `pip install -r requirements.txt`

- [ ] **Step 2: Write `app/config.py` (no test — pure env-var plumbing, exercised indirectly by every test that follows)**

```python
import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass
class Settings:
    llm_api_key: str
    llm_base_url: str
    ocr_vision_model: str
    narrative_model: str
    db_path: str


@lru_cache
def get_settings() -> Settings:
    return Settings(
        llm_api_key=os.environ.get("LLM_API_KEY", ""),
        llm_base_url=os.environ.get(
            "LLM_BASE_URL", "https://maas-llm-aiplatform-hcm.api.vngcloud.vn/v1"
        ),
        ocr_vision_model=os.environ.get("OCR_VISION_MODEL", "qwen/qwen3.6-flash"),
        narrative_model=os.environ.get("NARRATIVE_MODEL", "z-ai/glm-5.2-hackathon"),
        db_path=os.environ.get("DB_PATH", "data/m_insight.db"),
    )
```

- [ ] **Step 3: Write the failing test**

`tests/test_extraction_ocr_vision.py`:
```python
import httpx
import pytest

from app.extraction import ocr_vision


def _mock_transport(expected_model: str, response_text: str) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        body = request.read()
        import json

        payload = json.loads(body)
        assert payload["model"] == expected_model
        assert payload["messages"][0]["content"][1]["type"] == "image_url"
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": response_text}}]},
        )

    return httpx.MockTransport(handler)


def test_ocr_image_returns_model_text(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    from app.config import get_settings

    get_settings.cache_clear()

    transport = _mock_transport("qwen/qwen3.6-flash", "Doanh thu: 500 trieu")
    monkeypatch.setattr(ocr_vision, "_client", httpx.Client(transport=transport))

    result = ocr_vision.ocr_image(b"\x89PNG\r\n\x1a\nfakepngbytes")
    assert result == "Doanh thu: 500 trieu"


def test_ocr_image_raises_on_http_error(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    from app.config import get_settings

    get_settings.cache_clear()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    monkeypatch.setattr(ocr_vision, "_client", httpx.Client(transport=httpx.MockTransport(handler)))

    with pytest.raises(httpx.HTTPStatusError):
        ocr_vision.ocr_image(b"fakebytes")
```

- [ ] **Step 4: Run test to verify it fails**

Run: `pytest tests/test_extraction_ocr_vision.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.extraction.ocr_vision'`

- [ ] **Step 5: Write minimal implementation**

`app/extraction/ocr_vision.py`:
```python
import base64

import httpx

from ..config import get_settings

OCR_PROMPT = (
    "Đây là một trang tài liệu ngân hàng/tài chính dạng ảnh (đã scan). "
    "Hãy trích xuất TOÀN BỘ nội dung văn bản nhìn thấy được trên ảnh này, "
    "giữ nguyên số liệu, không suy diễn hay bổ sung thông tin không có trên ảnh. "
    "Nếu chữ mờ không đọc được, ghi [KHÔNG ĐỌC ĐƯỢC] tại vị trí đó."
)

# Module-level client so tests can monkeypatch the transport.
_client = httpx.Client(timeout=60.0)


def ocr_image(image_bytes: bytes, model: str | None = None) -> str:
    settings = get_settings()
    model = model or settings.ocr_vision_model
    b64 = base64.b64encode(image_bytes).decode()

    response = _client.post(
        f"{settings.llm_base_url}/chat/completions",
        headers={"Authorization": f"Bearer {settings.llm_api_key}"},
        json={
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": OCR_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{b64}"},
                        },
                    ],
                }
            ],
            "max_tokens": 4096,
        },
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_extraction_ocr_vision.py -v`
Expected: 2 passed

- [ ] **Step 7: Commit**

```bash
git add requirements.txt app/config.py app/extraction/ocr_vision.py tests/test_extraction_ocr_vision.py
git commit -m "feat: add vision-LLM OCR call against GreenNode MaaS"
```

---

### Task 7: Extraction pipeline orchestrator

**Files:**
- Create: `app/extraction/pipeline.py`
- Create: `tests/test_extraction_pipeline.py`

**Interfaces:**
- Consumes: `extract_docx` (Task 3), `extract_pdf`/`render_pdf_pages_to_images` (Task 4), `extract_xlsx`/`extract_csv` (Task 5), `ocr_image` (Task 6).
- Produces: `extract_document(file_path: str, filename: str) -> ExtractedDocument`, `extract_documents(files: list[tuple[str, str]]) -> list[ExtractedDocument]` — this is the **one function every agent plan (RB/EB/Cross-sell) calls** to turn uploaded files into structured text/tables.

- [ ] **Step 1: Write the failing test**

`tests/test_extraction_pipeline.py`:
```python
import pytest

from app.extraction import pipeline


def test_extract_document_routes_docx(fixtures_dir):
    doc = pipeline.extract_document(str(fixtures_dir / "sample.docx"), "sample.docx")
    assert doc.doc_type == "docx"


def test_extract_document_routes_xlsx(fixtures_dir):
    doc = pipeline.extract_document(str(fixtures_dir / "sample.xlsx"), "sample.xlsx")
    assert doc.doc_type == "xlsx"


def test_extract_document_routes_csv(fixtures_dir):
    doc = pipeline.extract_document(str(fixtures_dir / "sample.csv"), "sample.csv")
    assert doc.doc_type == "csv"


def test_extract_document_pdf_with_text_layer_skips_ocr(fixtures_dir):
    doc = pipeline.extract_document(str(fixtures_dir / "sample_text.pdf"), "sample_text.pdf")
    assert doc.extraction_method == "text_layer"


def test_extract_document_rejects_unsupported_extension(fixtures_dir, tmp_path):
    bogus = tmp_path / "photo.jpg"
    bogus.write_bytes(b"not a real jpg")
    with pytest.raises(ValueError, match="không được hỗ trợ"):
        pipeline.extract_document(str(bogus), "photo.jpg")


def test_extract_document_scanned_pdf_falls_back_to_ocr(fixtures_dir, monkeypatch):
    calls = []

    def fake_ocr_image(image_bytes, model=None):
        calls.append(image_bytes)
        return "Noi dung da OCR tu anh"

    monkeypatch.setattr(pipeline, "ocr_image", fake_ocr_image)

    doc = pipeline.extract_document(str(fixtures_dir / "sample_scanned.pdf"), "sample_scanned.pdf")
    assert doc.extraction_method == "vision_llm"
    assert "Noi dung da OCR tu anh" in doc.text
    assert len(calls) == 1


def test_extract_document_scanned_pdf_ocr_failure_is_captured_as_warning(fixtures_dir, monkeypatch):
    def failing_ocr_image(image_bytes, model=None):
        raise RuntimeError("network down")

    monkeypatch.setattr(pipeline, "ocr_image", failing_ocr_image)

    doc = pipeline.extract_document(str(fixtures_dir / "sample_scanned.pdf"), "sample_scanned.pdf")
    assert doc.extraction_method == "ocr_failed"
    assert any("network down" in w for w in doc.warnings)


def test_extract_documents_processes_a_batch(fixtures_dir):
    files = [
        (str(fixtures_dir / "sample.docx"), "sample.docx"),
        (str(fixtures_dir / "sample.csv"), "sample.csv"),
    ]
    docs = pipeline.extract_documents(files)
    assert [d.doc_type for d in docs] == ["docx", "csv"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_extraction_pipeline.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.extraction.pipeline'`

- [ ] **Step 3: Write minimal implementation**

`app/extraction/pipeline.py`:
```python
import os

from .docx_parser import extract_docx
from .ocr_vision import ocr_image
from .pdf_parser import extract_pdf, render_pdf_pages_to_images
from .types import ExtractedDocument
from .xlsx_csv_parser import extract_csv, extract_xlsx

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".xls", ".csv"}


def extract_document(file_path: str, filename: str) -> ExtractedDocument:
    ext = os.path.splitext(filename)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Định dạng file không được hỗ trợ: {ext}")

    if ext == ".pdf":
        doc = extract_pdf(file_path, filename)
        if doc.extraction_method == "no_text_layer":
            return _ocr_pdf(file_path, filename, doc)
        return doc
    if ext == ".docx":
        return extract_docx(file_path, filename)
    if ext in (".xlsx", ".xls"):
        return extract_xlsx(file_path, filename)
    return extract_csv(file_path, filename)  # ext == ".csv"


def _ocr_pdf(file_path: str, filename: str, base_doc: ExtractedDocument) -> ExtractedDocument:
    images = render_pdf_pages_to_images(file_path)
    texts: list[str] = []
    warnings = list(base_doc.warnings)
    for i, image_bytes in enumerate(images):
        try:
            texts.append(ocr_image(image_bytes))
        except Exception as exc:  # noqa: BLE001 - deliberately broad: one page must not sink the batch
            warnings.append(f"OCR trang {i + 1} thất bại: {exc}")

    return ExtractedDocument(
        filename=filename,
        doc_type="pdf",
        text="\n".join(texts),
        tables=[],
        extraction_method="vision_llm" if texts else "ocr_failed",
        confidence=0.7 if texts else 0.0,
        warnings=warnings,
    )


def extract_documents(files: list[tuple[str, str]]) -> list[ExtractedDocument]:
    return [extract_document(path, name) for path, name in files]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_extraction_pipeline.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add app/extraction/pipeline.py tests/test_extraction_pipeline.py
git commit -m "feat: add extraction pipeline orchestrator with OCR fallback"
```

---

### Task 8: Engine core types (`Metric`, `RuleResult`)

**Files:**
- Create: `app/engine/__init__.py` (empty)
- Create: `app/engine/core/__init__.py` (empty)
- Create: `app/engine/core/types.py`
- Create: `tests/test_engine_core.py`

**Interfaces:**
- Produces: `Metric` (with `Metric.need_more_data(...)` constructor) and `RuleResult` dataclasses — the RB, EB, and Cross-sell plans' rule/formula functions all return these types. This is the structural guarantee that Layer 3 (LLM) can never invent a number: every metric the UI shows traces back to one of these objects.

- [ ] **Step 1: Write the failing test**

`tests/test_engine_core.py`:
```python
from app.engine.core.types import Metric, RuleResult


def test_metric_holds_computed_value_with_provenance():
    m = Metric(
        metric="DTI",
        value=0.2262,
        formula="(tong nghia vu tra no + nghia vu de xuat) / thu nhap ghi nhan",
        input_values={"debt": 52812500, "income": 233520000},
        input_sources={"debt": "credit_engine", "income": "income_assessment"},
    )
    assert m.status == "OK"
    assert m.value == 0.2262


def test_metric_need_more_data_has_null_value_and_status():
    m = Metric.need_more_data("DSCR", formula="CFADS / (goc + lai den han)")
    assert m.value is None
    assert m.status == "NEED_MORE_DATA"
    assert m.formula == "CFADS / (goc + lai den han)"


def test_rule_result_defaults():
    r = RuleResult(rule_id="RF01", rule_name="Mat can doi von", status="KHONG_KICH_HOAT")
    assert r.evidence == []
    assert r.severity is None
    assert r.comment == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_engine_core.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.engine.core.types'`

- [ ] **Step 3: Write minimal implementation**

`app/engine/__init__.py`: empty.
`app/engine/core/__init__.py`: empty.

`app/engine/core/types.py`:
```python
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Metric:
    metric: str
    value: float | str | None
    formula: str
    input_values: dict[str, Any]
    input_sources: dict[str, str]
    status: str = "OK"  # "OK" | "NEED_MORE_DATA"

    @staticmethod
    def need_more_data(
        metric: str, formula: str, input_values: dict[str, Any] | None = None
    ) -> "Metric":
        return Metric(
            metric=metric,
            value=None,
            formula=formula,
            input_values=input_values or {},
            input_sources={},
            status="NEED_MORE_DATA",
        )


@dataclass
class RuleResult:
    rule_id: str
    rule_name: str
    status: str
    severity: str | None = None
    evidence: list[str] = field(default_factory=list)
    threshold: str | None = None
    formula: str | None = None
    comment: str = ""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_engine_core.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add app/engine/__init__.py app/engine/core/__init__.py app/engine/core/types.py tests/test_engine_core.py
git commit -m "feat: add engine core types (Metric, RuleResult)"
```

---

### Task 9: SQLite storage

**Files:**
- Create: `app/storage/__init__.py` (empty)
- Create: `app/storage/db.py`
- Create: `app/storage/repository.py`
- Create: `tests/test_storage.py`

**Interfaces:**
- Produces: `init_db(db_path: str) -> None`, `save_assessment(db_path: str, agent_type: str, customer_name: str, tax_id: str, result: dict) -> int`, `get_latest_assessment(db_path: str, agent_type: str) -> dict | None` — consumed by `app/main.py` (Task 10) and by each agent's router (RB/EB/Cross-sell plans).

- [ ] **Step 1: Write the failing test**

`tests/test_storage.py`:
```python
from app.storage.db import init_db
from app.storage.repository import get_latest_assessment, save_assessment


def test_save_and_get_latest_assessment(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)

    save_assessment(db_path, "rb", "CONG TY A", "0100000001", {"recommendation": "PROCEED_FOR_HUMAN_REVIEW"})
    second_id = save_assessment(
        db_path, "rb", "CONG TY A", "0100000001", {"recommendation": "ADDITIONAL_DOCUMENTS_REQUIRED"}
    )

    latest = get_latest_assessment(db_path, "rb")
    assert latest is not None
    assert latest["id"] == second_id
    assert latest["result"]["recommendation"] == "ADDITIONAL_DOCUMENTS_REQUIRED"
    assert latest["customer_name"] == "CONG TY A"


def test_get_latest_assessment_returns_none_when_empty(tmp_path):
    db_path = str(tmp_path / "empty.db")
    init_db(db_path)
    assert get_latest_assessment(db_path, "eb") is None


def test_agent_types_are_isolated(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    save_assessment(db_path, "rb", "KH RB", "111", {"x": 1})
    assert get_latest_assessment(db_path, "eb") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_storage.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.storage.db'`

- [ ] **Step 3: Write minimal implementation**

`app/storage/__init__.py`: empty.

`app/storage/db.py`:
```python
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS assessments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_type TEXT NOT NULL,
    customer_name TEXT NOT NULL,
    tax_id TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def get_connection(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str) -> None:
    conn = get_connection(db_path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()
```

`app/storage/repository.py`:
```python
import json

from .db import get_connection


def save_assessment(
    db_path: str, agent_type: str, customer_name: str, tax_id: str, result: dict
) -> int:
    conn = get_connection(db_path)
    try:
        cur = conn.execute(
            "INSERT INTO assessments (agent_type, customer_name, tax_id, result_json) "
            "VALUES (?, ?, ?, ?)",
            (agent_type, customer_name, tax_id, json.dumps(result, ensure_ascii=False)),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_latest_assessment(db_path: str, agent_type: str) -> dict | None:
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM assessments WHERE agent_type = ? ORDER BY id DESC LIMIT 1",
            (agent_type,),
        ).fetchone()
        if row is None:
            return None
        return {
            "id": row["id"],
            "agent_type": row["agent_type"],
            "customer_name": row["customer_name"],
            "tax_id": row["tax_id"],
            "result": json.loads(row["result_json"]),
            "created_at": row["created_at"],
        }
    finally:
        conn.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_storage.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add app/storage/__init__.py app/storage/db.py app/storage/repository.py tests/test_storage.py
git commit -m "feat: add SQLite storage for assessment results"
```

---

### Task 10: FastAPI app skeleton (replaces the smoke-test placeholder)

**Files:**
- Modify: `app/main.py` (replace the placeholder body entirely)
- Create: `tests/test_main.py`

**Interfaces:**
- Consumes: `get_settings()` (Task 6), `init_db()` (Task 9).
- Produces: the `app` FastAPI instance. Each of the RB/EB/Cross-sell plans' first task imports `app` from `app.main` and calls `app.include_router(...)`.

- [ ] **Step 1: Write the failing test**

`tests/test_main.py`:
```python
from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_ok():
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_main.py -v`
Expected: FAIL — the placeholder `app/main.py` from the CI smoke test has no `/health` wired through `init_db`, so this may actually pass by accident; to force a real failure first, temporarily rename the existing `/health` route in `app/main.py` before this step, run the test to confirm it fails, then proceed to Step 3 which restores and extends it properly. (If your `app/main.py` still only has the two-route placeholder, this step is a formality — just confirm `pytest tests/test_main.py -v` collects and passes trivially, then continue: the real value of this task is Step 3's startup-hook + static-mount wiring, not this one assertion.)

- [ ] **Step 3: Write the implementation**

Replace the entire contents of `app/main.py` with:
```python
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .storage.db import init_db

app = FastAPI(title="M-Insight 360")


@app.on_event("startup")
def on_startup() -> None:
    init_db(get_settings().db_path)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


_WEB_DIST = Path(__file__).resolve().parent.parent / "web" / "out"
if _WEB_DIST.exists():
    app.mount("/", StaticFiles(directory=str(_WEB_DIST), html=True), name="web")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_main.py -v`
Expected: 1 passed

- [ ] **Step 5: Run the full test suite to confirm nothing regressed**

Run: `pytest -v`
Expected: all tests from Tasks 1-10 pass (≈23 tests).

- [ ] **Step 6: Commit**

```bash
git add app/main.py tests/test_main.py
git commit -m "feat: replace placeholder app with real FastAPI skeleton (startup DB init, static frontend mount)"
```

---

### Task 11: Next.js frontend skeleton with MSB theme

**Files:**
- Create: `web/package.json`
- Create: `web/next.config.mjs`
- Create: `web/tsconfig.json`
- Create: `web/tailwind.config.ts`
- Create: `web/postcss.config.mjs`
- Create: `web/app/layout.tsx`
- Create: `web/app/globals.css`
- Create: `web/app/page.tsx` (temporary placeholder body — replaced in Task 12/13)

**Interfaces:**
- Produces: a Next.js project that `npm run build` compiles to static files at `web/out/`, which `app/main.py` (Task 10) mounts at `/`.

- [ ] **Step 1: Write `web/package.json`**

```json
{
  "name": "m-insight-360-web",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "lint": "next lint"
  },
  "dependencies": {
    "next": "14.2.18",
    "react": "18.3.1",
    "react-dom": "18.3.1"
  },
  "devDependencies": {
    "typescript": "5.6.3",
    "@types/node": "20.16.11",
    "@types/react": "18.3.12",
    "@types/react-dom": "18.3.1",
    "tailwindcss": "3.4.14",
    "postcss": "8.4.47",
    "autoprefixer": "10.4.20"
  }
}
```

- [ ] **Step 2: Write the remaining config files**

`web/next.config.mjs`:
```js
/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "export",
  images: { unoptimized: true },
};

export default nextConfig;
```

`web/tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2017",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "paths": { "@/*": ["./*"] }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx"],
  "exclude": ["node_modules"]
}
```

`web/postcss.config.mjs`:
```js
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
```

`web/tailwind.config.ts`:
```ts
import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        msb: {
          navy: "#091E42",
          orange: "#F4600C",
          bg: "#DEE5EF",
        },
      },
      fontFamily: {
        sans: ["Inter", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
```

`web/app/globals.css`:
```css
@tailwind base;
@tailwind components;
@tailwind utilities;

body {
  background-color: #ffffff;
  color: #091e42;
}
```

`web/app/layout.tsx`:
```tsx
import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "M-Insight 360 | MSB",
  description: "Trợ lý AI thẩm định tín dụng MSB",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="vi">
      <body className="font-sans">{children}</body>
    </html>
  );
}
```

`web/app/page.tsx` (temporary — real content lands in Task 12/13):
```tsx
export default function Home() {
  return (
    <main className="min-h-screen bg-msb-bg flex items-center justify-center">
      <h1 className="text-msb-navy text-2xl font-bold">M-Insight 360</h1>
    </main>
  );
}
```

- [ ] **Step 3: Install dependencies and build**

Run: `cd web && npm install && npm run build`
Expected: build succeeds, creates `web/out/index.html`.

- [ ] **Step 4: Verify the theme markers landed in the build output**

Run: `grep -c "M-Insight 360" web/out/index.html`
Expected: at least 1 match (confirms the title/heading rendered into the static export).

- [ ] **Step 5: Commit**

```bash
cd /home/user/M-Insight-360
git add web/package.json web/package-lock.json web/next.config.mjs web/tsconfig.json \
        web/tailwind.config.ts web/postcss.config.mjs web/app/layout.tsx web/app/globals.css web/app/page.tsx
git commit -m "feat: scaffold Next.js frontend with MSB theme tokens"
```

---

### Task 12: Assessment form + result panel components

**Files:**
- Create: `web/components/AssessmentForm.tsx`
- Create: `web/components/ResultPanel.tsx`
- Create: `web/lib/api.ts`
- Modify: `web/app/page.tsx` (wire the real page)

**Interfaces:**
- Consumes: backend endpoints `POST /api/rb/assess` and `POST /api/eb/assess` (multipart form: `customer_name`, `tax_id`, `files[]`) — these routes are added by the RB and EB plans respectively; this task calls them by URL string, it does not depend on their Python code existing yet.
- Produces: the page users interact with. `ResultPanel` renders whatever JSON shape `credit_readiness`/`recommendation`/`risk_flags`/`credit_engine`/`why`/`missing_data` the RB/EB routers return (spec §5 JSON schema) — optional-chained so it renders gracefully even for the EB shape, which reuses the same field names per spec §6.

- [ ] **Step 1: Write `web/lib/api.ts`**

```ts
export type AssessmentResult = {
  case_id?: string;
  customer_profile?: Record<string, unknown>;
  credit_engine?: Record<string, unknown>;
  risk_flags?: Array<{
    rule_id?: string;
    severity?: string;
    evidence?: string[];
    impact?: string;
    recommended_action?: string;
  }>;
  missing_data?: string[];
  credit_readiness?: string;
  recommendation?: string;
  why?: string[];
  credit_memo?: string;
  export_available?: boolean;
};

export async function runAssessment(
  agentType: "rb" | "eb",
  customerName: string,
  taxId: string,
  files: File[]
): Promise<AssessmentResult> {
  const form = new FormData();
  form.append("customer_name", customerName);
  form.append("tax_id", taxId);
  for (const f of files) form.append("files", f);

  const resp = await fetch(`/api/${agentType}/assess`, {
    method: "POST",
    body: form,
  });
  if (!resp.ok) {
    throw new Error(`Thẩm định thất bại: HTTP ${resp.status}`);
  }
  return resp.json();
}
```

- [ ] **Step 2: Write `web/components/AssessmentForm.tsx`**

```tsx
"use client";

import { useState } from "react";
import { AssessmentResult, runAssessment } from "@/lib/api";

type Props = {
  agentType: "rb" | "eb";
  onResult: (result: AssessmentResult) => void;
};

export default function AssessmentForm({ agentType, onResult }: Props) {
  const [customerName, setCustomerName] = useState("");
  const [taxId, setTaxId] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canSubmit = customerName.trim() !== "" && taxId.trim() !== "" && files.length > 0;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    setLoading(true);
    setError(null);
    try {
      const result = await runAssessment(agentType, customerName, taxId, files);
      onResult(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Đã xảy ra lỗi không xác định");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow p-6 space-y-4">
      <h2 className="text-lg font-semibold text-msb-navy">Thẩm định Khách hàng mới</h2>

      <div>
        <label className="block text-sm font-medium text-msb-navy mb-1">
          Tên Khách hàng <span className="text-red-600">*</span>
        </label>
        <input
          className="w-full border rounded px-3 py-2"
          value={customerName}
          onChange={(e) => setCustomerName(e.target.value)}
          required
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-msb-navy mb-1">
          Mã số thuế <span className="text-red-600">*</span>
        </label>
        <input
          className="w-full border rounded px-3 py-2"
          value={taxId}
          onChange={(e) => setTaxId(e.target.value)}
          required
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-msb-navy mb-1">
          Upload hồ sơ (docx, pdf, xlsx, csv) <span className="text-red-600">*</span>
        </label>
        <input
          type="file"
          multiple
          accept=".docx,.pdf,.xlsx,.xls,.csv"
          onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
          required
        />
      </div>

      {error && <p className="text-red-600 text-sm">{error}</p>}

      <button
        type="submit"
        disabled={!canSubmit || loading}
        className="bg-msb-orange text-white font-semibold px-4 py-2 rounded disabled:opacity-50"
      >
        {loading ? "Đang xử lý..." : "Chạy thẩm định AI"}
      </button>
    </form>
  );
}
```

- [ ] **Step 3: Write `web/components/ResultPanel.tsx`**

```tsx
import { AssessmentResult } from "@/lib/api";

export default function ResultPanel({ result }: { result: AssessmentResult }) {
  return (
    <div className="bg-white rounded-lg shadow p-6 space-y-4 mt-6">
      <h2 className="text-lg font-semibold text-msb-navy">
        Kết quả thẩm định gần nhất
      </h2>

      <div className="flex gap-4">
        <div>
          <span className="text-sm text-gray-500">Mức độ sẵn sàng hồ sơ</span>
          <p className="font-semibold">{result.credit_readiness ?? "—"}</p>
        </div>
        <div>
          <span className="text-sm text-gray-500">Khuyến nghị</span>
          <p className="font-semibold">{result.recommendation ?? "—"}</p>
        </div>
      </div>

      {result.risk_flags && result.risk_flags.length > 0 && (
        <div>
          <h3 className="font-medium text-msb-navy mb-1">Cảnh báo rủi ro</h3>
          <ul className="list-disc list-inside text-sm space-y-1">
            {result.risk_flags.map((f, i) => (
              <li key={i}>
                <span className="font-semibold">{f.rule_id}</span> ({f.severity}):{" "}
                {f.impact}
              </li>
            ))}
          </ul>
        </div>
      )}

      {result.missing_data && result.missing_data.length > 0 && (
        <div>
          <h3 className="font-medium text-msb-navy mb-1">Hồ sơ còn thiếu</h3>
          <ul className="list-disc list-inside text-sm">
            {result.missing_data.map((m, i) => (
              <li key={i}>{m}</li>
            ))}
          </ul>
        </div>
      )}

      {result.why && result.why.length > 0 && (
        <div>
          <h3 className="font-medium text-msb-navy mb-1">Vì sao?</h3>
          <ul className="list-disc list-inside text-sm">
            {result.why.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      {result.export_available && (
        <button className="border border-msb-navy text-msb-navy font-semibold px-4 py-2 rounded">
          Xuất tờ trình MB02
        </button>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Wire `web/app/page.tsx`**

```tsx
"use client";

import { useState } from "react";
import AssessmentForm from "@/components/AssessmentForm";
import ResultPanel from "@/components/ResultPanel";
import { AssessmentResult } from "@/lib/api";

export default function Home() {
  const [tab, setTab] = useState<"rb" | "eb">("rb");
  const [result, setResult] = useState<AssessmentResult | null>(null);

  return (
    <main className="min-h-screen bg-msb-bg">
      <header className="bg-msb-navy text-white px-8 py-6">
        <h1 className="text-2xl font-bold">M-Insight 360</h1>
        <p className="text-sm opacity-80">Trợ lý AI Thẩm định tín dụng MSB</p>
      </header>

      <div className="max-w-3xl mx-auto px-4 py-8">
        <div className="flex gap-2 mb-6">
          {(["rb", "eb"] as const).map((t) => (
            <button
              key={t}
              onClick={() => {
                setTab(t);
                setResult(null);
              }}
              className={`px-4 py-2 rounded font-semibold ${
                tab === t ? "bg-msb-navy text-white" : "bg-white text-msb-navy"
              }`}
            >
              {t.toUpperCase()}
            </button>
          ))}
        </div>

        <AssessmentForm agentType={tab} onResult={setResult} />
        {result && <ResultPanel result={result} />}
      </div>
    </main>
  );
}
```

- [ ] **Step 5: Build and verify**

Run: `cd web && npm run build`
Expected: build succeeds.

Run: `grep -c "Chạy thẩm định AI" web/out/index.html`
Expected: at least 1 match.

- [ ] **Step 6: Commit**

```bash
cd /home/user/M-Insight-360
git add web/components/AssessmentForm.tsx web/components/ResultPanel.tsx web/lib/api.ts web/app/page.tsx
git commit -m "feat: add assessment form and result panel to frontend"
```

---

### Task 13: Dockerfile multi-stage build (frontend + backend) + CI verification

**Files:**
- Modify: `Dockerfile`
- Modify: `.dockerignore` (ensure `web/node_modules` and `web/.next` are excluded from the Python build context, and `app/`/`requirements*.txt` are excluded from the Node build context noise — see step 1)

**Interfaces:**
- Produces: a single image containing the built Next.js static export at `/app/web/out` and the FastAPI app, satisfying `app/main.py`'s `_WEB_DIST` mount path from Task 10.

- [ ] **Step 1: Update `.dockerignore`**

Add these lines (the file already has `.git`, `.github`, `.claude`, `.env*`, `.greennode.json`, `*.credentials.json`, `__pycache__`, `*.pyc`, `.agentbase/`):
```
node_modules
web/node_modules
web/.next
data/
```

- [ ] **Step 2: Rewrite `Dockerfile` as a multi-stage build**

```dockerfile
FROM node:20-slim AS web-build
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web ./
RUN npm run build

FROM python:3.11-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY --from=web-build /web/out ./web/out

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

- [ ] **Step 3: Commit and push to trigger the already-working CI/CD pipeline**

```bash
git add Dockerfile .dockerignore
git commit -m "feat: multi-stage Docker build embedding the Next.js static frontend"
git push -u origin claude/pensive-hamilton-tu2cdx
```

Note: this repo's Docker daemon is not available in the local dev sandbox (confirmed during the earlier smoke test) — verification happens through GitHub Actions, which already builds and deploys successfully (see spec §10). Do not attempt `docker build` locally; use the CI run instead.

- [ ] **Step 4: Verify the GitHub Actions run succeeds**

Use the `mcp__github__actions_list` / `mcp__github__actions_get` tools (or the GitHub UI) to watch the `Deploy to GreenNode AgentBase` workflow run triggered by the push. Confirm all steps succeed, including `Health check`.

- [ ] **Step 5: Verify the deployed endpoint serves the real frontend, not the placeholder**

```bash
curl -s "<endpoint-url-from-workflow-summary>/" | grep -c "M-Insight 360"
```
Expected: at least 1 match (confirms the static export is being served, not the old JSON placeholder response).

```bash
curl -s "<endpoint-url-from-workflow-summary>/health"
```
Expected: `{"status":"ok"}`

---

## Handoff

Foundation is complete once all 13 tasks are committed and the CI run in Task 13 is green with the real frontend confirmed live. At that point:
- `app.extraction.pipeline.extract_document(s)` is the entry point every agent plan uses to turn uploads into `ExtractedDocument` objects.
- `app.engine.core.types.Metric` / `RuleResult` are the types every agent plan's formulas and rules must return.
- `app.storage.repository.save_assessment` / `get_latest_assessment` persist and retrieve results.
- `app.main.app` is the FastAPI instance each agent plan's first task extends with `app.include_router(...)`.
- The frontend's `AssessmentForm`/`ResultPanel` already call `POST /api/{rb,eb}/assess` and render the spec §5/§6 JSON shape — no frontend changes needed for RB/EB to go live, only backend routes.
