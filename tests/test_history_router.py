from fastapi.testclient import TestClient

from app.main import app
from app.storage.repository import save_assessment


def test_history_endpoint_returns_recent_items_for_agent_type(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    from app.config import get_settings

    get_settings.cache_clear()

    with TestClient(app) as client:
        save_assessment(get_settings().db_path, "eb", "Cong ty A", "0100000001", {"credit_readiness": "READY"})
        resp = client.get("/api/history", params={"agent_type": "eb"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["customer_name"] == "Cong ty A"


def test_history_endpoint_respects_limit_param(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test2.db"))
    from app.config import get_settings

    get_settings.cache_clear()

    with TestClient(app) as client:
        for i in range(4):
            save_assessment(get_settings().db_path, "eb", f"Cong ty {i}", "0100000001", {})
        resp = client.get("/api/history", params={"agent_type": "eb", "limit": 2})
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 2


def test_history_endpoint_rejects_unknown_agent_type(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test3.db"))
    from app.config import get_settings

    get_settings.cache_clear()

    with TestClient(app) as client:
        resp = client.get("/api/history", params={"agent_type": "nope"})
    assert resp.status_code == 200
    assert resp.json()["items"] == []


def test_history_endpoint_returns_empty_when_nothing_saved(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test4.db"))
    from app.config import get_settings

    get_settings.cache_clear()

    with TestClient(app) as client:
        resp = client.get("/api/history", params={"agent_type": "rb"})
    assert resp.status_code == 200
    assert resp.json()["items"] == []
