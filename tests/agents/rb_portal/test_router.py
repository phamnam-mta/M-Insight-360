import io

from fastapi.testclient import TestClient

from app.main import app


def test_create_case_returns_case_id(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    from app.config import get_settings
    get_settings.cache_clear()
    client = TestClient(app)
    resp = client.post("/api/rb-portal/cases", json={"customer_name": "NGUYEN VAN A", "tax_id": "0100000001"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["case_id"].startswith("RB-0100000001-")


def test_get_case_after_create(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    from app.config import get_settings
    get_settings.cache_clear()
    client = TestClient(app)
    case_id = client.post("/api/rb-portal/cases", json={"customer_name": "A", "tax_id": "111"}).json()["case_id"]
    resp = client.get(f"/api/rb-portal/cases/{case_id}")
    assert resp.status_code == 200
    assert resp.json()["case_id"] == case_id
    assert resp.json()["customer"] is None


def test_get_case_404_for_unknown_id(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    from app.config import get_settings
    get_settings.cache_clear()
    client = TestClient(app)
    resp = client.get("/api/rb-portal/cases/RB-NOPE")
    assert resp.status_code == 404


def test_list_cases_returns_recent_first(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    from app.config import get_settings
    get_settings.cache_clear()
    client = TestClient(app)
    client.post("/api/rb-portal/cases", json={"customer_name": "A", "tax_id": "111"})
    client.post("/api/rb-portal/cases", json={"customer_name": "B", "tax_id": "222"})
    resp = client.get("/api/rb-portal/cases")
    assert resp.status_code == 200
    names = [c["customer_name"] for c in resp.json()["cases"]]
    assert names == ["B", "A"]


def test_patch_customer_section_persists(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    from app.config import get_settings
    get_settings.cache_clear()
    client = TestClient(app)
    case_id = client.post("/api/rb-portal/cases", json={"customer_name": "A", "tax_id": "111"}).json()["case_id"]
    resp = client.patch(f"/api/rb-portal/cases/{case_id}/customer", json={"full_name": "A", "gender": "male"})
    assert resp.status_code == 200
    case = client.get(f"/api/rb-portal/cases/{case_id}").json()
    assert case["customer"]["full_name"] == "A"


def test_patch_unknown_section_returns_404(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    from app.config import get_settings
    get_settings.cache_clear()
    client = TestClient(app)
    case_id = client.post("/api/rb-portal/cases", json={"customer_name": "A", "tax_id": "111"}).json()["case_id"]
    resp = client.patch(f"/api/rb-portal/cases/{case_id}/bogus", json={})
    assert resp.status_code == 404


def test_patch_on_unknown_case_returns_404(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    from app.config import get_settings
    get_settings.cache_clear()
    client = TestClient(app)
    resp = client.patch("/api/rb-portal/cases/RB-NOPE/customer", json={"full_name": "A"})
    assert resp.status_code == 404


def test_upload_document_requires_category(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("CASE_FILES_DIR", str(tmp_path / "files"))
    from app.config import get_settings
    get_settings.cache_clear()
    client = TestClient(app)
    case_id = client.post("/api/rb-portal/cases", json={"customer_name": "A", "tax_id": "111"}).json()["case_id"]
    resp = client.post(
        f"/api/rb-portal/cases/{case_id}/documents",
        files={"file": ("cccd.csv", io.BytesIO(b"CCCD SO 001234567890"), "text/csv")},
    )
    assert resp.status_code == 422  # category missing


def test_upload_document_and_list(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("CASE_FILES_DIR", str(tmp_path / "files"))
    from app.config import get_settings
    get_settings.cache_clear()
    client = TestClient(app)
    case_id = client.post("/api/rb-portal/cases", json={"customer_name": "A", "tax_id": "111"}).json()["case_id"]
    resp = client.post(
        f"/api/rb-portal/cases/{case_id}/documents",
        data={"category": "LEGAL"},
        files={"file": ("cccd.csv", io.BytesIO(b"CCCD SO 001234567890"), "text/csv")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "EXTRACTED"

    resp = client.get(f"/api/rb-portal/cases/{case_id}/documents")
    docs = resp.json()["documents"]
    assert len(docs) == 1
    assert docs[0]["filename"] == "cccd.csv"
    assert docs[0]["category"] == "LEGAL"


def test_upload_unreadable_file_marks_failed_not_500(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("CASE_FILES_DIR", str(tmp_path / "files"))
    from app.config import get_settings
    get_settings.cache_clear()
    client = TestClient(app)
    case_id = client.post("/api/rb-portal/cases", json={"customer_name": "A", "tax_id": "111"}).json()["case_id"]
    resp = client.post(
        f"/api/rb-portal/cases/{case_id}/documents",
        data={"category": "OTHER"},
        files={"file": ("photo.jpg", io.BytesIO(b"\xff\xd8\xff not a real image"), "image/jpeg")},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "FAILED"
