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
