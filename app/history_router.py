from fastapi import APIRouter

from .config import get_settings
from .storage.db import init_db
from .storage.repository import list_recent_assessments

router = APIRouter(prefix="/api", tags=["history"])

ALLOWED_AGENT_TYPES = {"rb", "eb", "crosssell"}


@router.get("/history")
async def get_history(agent_type: str, limit: int = 5) -> dict:
    if agent_type not in ALLOWED_AGENT_TYPES:
        return {"items": []}
    settings = get_settings()
    init_db(settings.db_path)
    limit = max(1, min(limit, 20))
    return {"items": list_recent_assessments(settings.db_path, agent_type, limit)}
