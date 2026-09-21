from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
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


from .agents.rb.router import router as rb_router  # noqa: E402

app.include_router(rb_router)


# NOTE for RB/EB/Cross-sell: call app.include_router(...) for your agent's
# router (POST endpoints) any time before this module finishes importing —
# the frontend fallback below is a GET-only route, so it never shadows a
# POST/PUT/DELETE endpoint regardless of registration order. It would only
# shadow a future GET endpoint registered *after* this block, so keep any
# new GET routes above it.
_WEB_DIST = Path(__file__).resolve().parent.parent / "web" / "out"

if _WEB_DIST.exists():
    _next_assets = _WEB_DIST / "_next"
    if _next_assets.exists():
        app.mount("/_next", StaticFiles(directory=str(_next_assets)), name="web-next-assets")

    @app.get("/{full_path:path}")
    def serve_frontend(full_path: str) -> FileResponse:
        base = _WEB_DIST.resolve()
        candidate = (base / full_path).resolve()
        try:
            candidate.relative_to(base)
        except ValueError:
            candidate = base / "index.html"
        if not candidate.is_file():
            candidate = base / "index.html"
        return FileResponse(candidate)
