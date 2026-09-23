import os
import tempfile
import time
import uuid

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.agents.rb.document_classifier import classify_document
from app.agents.rb.narrative import generate_narrative
from app.config import get_settings
from app.engine.core.timing import narrative_budget_exceeded
from app.extraction.pipeline import extract_document
from app.storage.db import init_db
from app.storage.files import save_case_file
from app.storage.rb_case_repository import (
    add_document, create_case, get_case, list_assessment_versions, list_cases,
    list_documents, save_assessment_version, update_case_section,
    update_case_status, update_document_status,
)

from .assessment import run_case_assessment
from .mandatory_check import check_mandatory

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
