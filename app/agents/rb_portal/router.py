import os
import tempfile
import uuid

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.agents.rb.document_classifier import classify_document
from app.config import get_settings
from app.extraction.pipeline import extract_document
from app.storage.db import init_db
from app.storage.files import save_case_file
from app.storage.rb_case_repository import (
    add_document, create_case, get_case, list_cases, list_documents,
    update_case_section, update_case_status, update_document_status,
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
