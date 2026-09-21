from fastapi import APIRouter
from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_ok():
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_frontend_mount_does_not_shadow_an_included_api_router():
    router = APIRouter()

    @router.post("/api/_test_dummy_assess")
    def dummy_assess() -> dict:
        return {"ok": True}

    app.include_router(router)

    client = TestClient(app)
    resp = client.post("/api/_test_dummy_assess")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
