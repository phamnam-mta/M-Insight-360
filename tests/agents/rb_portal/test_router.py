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


def _make_ready_case(client, monkeypatch) -> str:
    case_id = client.post("/api/rb-portal/cases", json={"customer_name": "A", "tax_id": "111"}).json()["case_id"]
    client.patch(f"/api/rb-portal/cases/{case_id}/customer", json={"full_name": "A"})
    client.patch(f"/api/rb-portal/cases/{case_id}/legal", json={"id_type": "CCCD"})
    client.patch(f"/api/rb-portal/cases/{case_id}/income", json={"source_type": "salary", "income_salary_vnd": 25_000_000})
    client.patch(f"/api/rb-portal/cases/{case_id}/loan", json={
        "product": "vay_von", "purpose": "tieu dung", "amount_vnd": 100_000_000,
        "tenor_months": 12, "annual_rate": 0.1, "existing_monthly_obligation_vnd": 1_000_000,
    })
    return case_id


def test_preliminary_assessment_runs_and_saves_a_version(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    from app.config import get_settings
    get_settings.cache_clear()
    import app.agents.rb_portal.router as rb_portal_router
    monkeypatch.setattr(rb_portal_router, "generate_narrative", lambda computed: {"why": [], "credit_memo": ""})
    client = TestClient(app)
    case_id = _make_ready_case(client, monkeypatch)

    resp = client.post(f"/api/rb-portal/cases/{case_id}/preliminary-assessment")
    assert resp.status_code == 200
    body = resp.json()
    # Same reused (unmodified) credit_engine.py behavior as Task 4: dti is
    # only computable from avg_monthly_revenue_vnd (business income), which
    # a salary-source case never populates; dsr uses gross_monthly_income_vnd
    # directly and IS computable here — assert on that instead (see Task 4's
    # ledgered ruling for the full explanation).
    assert body["credit_engine"]["dsr"]["status"] == "OK"

    history = client.get(f"/api/rb-portal/cases/{case_id}/history").json()["versions"]
    assert len(history) == 1
    assert history[0]["kind"] == "PRELIMINARY"


def test_full_assessment_blocked_when_mandatory_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    from app.config import get_settings
    get_settings.cache_clear()
    import app.agents.rb_portal.router as rb_portal_router
    monkeypatch.setattr(rb_portal_router, "generate_narrative", lambda computed: {"why": [], "credit_memo": ""})
    client = TestClient(app)
    case_id = client.post("/api/rb-portal/cases", json={"customer_name": "A", "tax_id": "111"}).json()["case_id"]

    resp = client.post(f"/api/rb-portal/cases/{case_id}/full-assessment")
    assert resp.status_code == 409
    # FastAPI wraps a dict `detail=` under the top-level "detail" key —
    # web/lib/rb-portal-api.ts's runFullAssessment() reads body.detail?.missing,
    # so this must stay in sync with that shape.
    assert resp.json()["detail"]["missing"]


def test_full_assessment_runs_when_mandatory_satisfied(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    from app.config import get_settings
    get_settings.cache_clear()
    import app.agents.rb_portal.router as rb_portal_router
    monkeypatch.setattr(rb_portal_router, "generate_narrative", lambda computed: {"why": [], "credit_memo": ""})
    client = TestClient(app)
    case_id = _make_ready_case(client, monkeypatch)

    resp = client.post(f"/api/rb-portal/cases/{case_id}/full-assessment")
    assert resp.status_code == 200
    assert client.get(f"/api/rb-portal/cases/{case_id}").json()["status"] == "FULL_DONE"


def test_two_preliminary_runs_create_two_history_versions(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    from app.config import get_settings
    get_settings.cache_clear()
    import app.agents.rb_portal.router as rb_portal_router
    monkeypatch.setattr(rb_portal_router, "generate_narrative", lambda computed: {"why": [], "credit_memo": ""})
    client = TestClient(app)
    case_id = _make_ready_case(client, monkeypatch)

    client.post(f"/api/rb-portal/cases/{case_id}/preliminary-assessment")
    client.post(f"/api/rb-portal/cases/{case_id}/preliminary-assessment")
    versions = client.get(f"/api/rb-portal/cases/{case_id}/history").json()["versions"]
    assert [v["version"] for v in versions] == [2, 1]


def test_summary_available_before_any_assessment_run(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    from app.config import get_settings
    get_settings.cache_clear()
    client = TestClient(app)
    case_id = client.post("/api/rb-portal/cases", json={"customer_name": "A", "tax_id": "111"}).json()["case_id"]

    resp = client.get(f"/api/rb-portal/cases/{case_id}/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["missing_data"]
    assert body["ai_status"] == "UNAVAILABLE"
    assert body["why"] == []


def test_summary_reflects_latest_saved_narrative(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    from app.config import get_settings
    get_settings.cache_clear()
    import app.agents.rb_portal.router as rb_portal_router
    monkeypatch.setattr(
        rb_portal_router, "generate_narrative",
        lambda computed: {"why": ["DTI trong ngưỡng an toàn"], "credit_memo": "Đủ điều kiện sơ bộ."},
    )
    client = TestClient(app)
    case_id = _make_ready_case(client, monkeypatch)
    client.post(f"/api/rb-portal/cases/{case_id}/preliminary-assessment")

    body = client.get(f"/api/rb-portal/cases/{case_id}/summary").json()
    assert body["why"] == ["DTI trong ngưỡng an toàn"]
    assert body["ai_status"] == "AVAILABLE"


def test_export_mb01a_returns_docx_bytes(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    from app.config import get_settings
    get_settings.cache_clear()
    client = TestClient(app)
    case_id = client.post("/api/rb-portal/cases", json={"customer_name": "NGUYEN VAN A", "tax_id": "111"}).json()["case_id"]
    client.patch(f"/api/rb-portal/cases/{case_id}/customer", json={"full_name": "NGUYEN VAN A"})

    resp = client.post(f"/api/rb-portal/cases/{case_id}/export/mb01a")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert len(resp.content) > 0


def test_export_mb01a_404_for_unknown_case(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    from app.config import get_settings
    get_settings.cache_clear()
    client = TestClient(app)
    resp = client.post("/api/rb-portal/cases/RB-NOPE/export/mb01a")
    assert resp.status_code == 404


def test_zalo_qr_endpoint_returns_placeholder(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    from app.config import get_settings
    get_settings.cache_clear()
    client = TestClient(app)
    resp = client.get("/api/rb-portal/zalo-bot/qr")
    assert resp.status_code == 200
    assert resp.json()["status"] == "NOT_CONNECTED"
