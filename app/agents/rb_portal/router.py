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
