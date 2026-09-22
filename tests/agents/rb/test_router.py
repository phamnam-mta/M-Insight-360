import io

from fastapi.testclient import TestClient

from app.agents.rb import router as rb_router
from app.main import app

# NOTE: the narrative function must be patched on the *router* module, not on
# app.agents.rb.narrative: router.py does "from .narrative import
# generate_narrative" at import time, which binds its own reference — patching
# the source module leaves the router calling the real function, and every test
# below then made a real outbound HTTPS call to the LLM endpoint.


# NOTE: TestClient must be used as a context manager ("with TestClient(app) as
# client:") so FastAPI's startup event (which calls init_db()) actually runs.
# Instantiating it bare and calling .post() directly never triggers the
# lifespan/startup handler, which was leaving the "assessments" table missing
# and every one of these tests failing with sqlite3.OperationalError.


def test_assess_endpoint_rejects_missing_mandatory_docs(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    from app.config import get_settings

    get_settings.cache_clear()

    monkeypatch.setattr(
        rb_router, "generate_narrative", lambda computed: {"why": [], "credit_memo": ""}
    )

    with TestClient(app) as client:
        files = {"files": ("note.csv", io.BytesIO(b"col1,col2\nval1,val2\n"), "text/csv")}
        resp = client.post(
            "/api/rb/assess",
            data={"customer_name": "CONG TY TEST", "tax_id": "0319998887"},
            files=files,
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["credit_readiness"] == "NOT_READY"
    assert body["recommendation"] == "ADDITIONAL_DOCUMENTS_REQUIRED"
    assert body["missing_data"]  # non-empty


def test_assess_endpoint_flags_tax_id_mismatch(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    from app.config import get_settings

    get_settings.cache_clear()

    monkeypatch.setattr(
        rb_router, "generate_narrative", lambda computed: {"why": [], "credit_memo": ""}
    )

    with TestClient(app) as client:
        files = [
            ("files", ("cccd.pdf", io.BytesIO(b"CAN CUOC CONG DAN so CCCD 001"), "application/octet-stream")),
            ("files", ("statement.csv", io.BytesIO(b"sao ke,ghi no,ghi co\n1,2,3\n"), "text/csv")),
            ("files", ("loan.csv", io.BytesIO(b"de nghi vay,so tien vay\n1,450000000\n"), "text/csv")),
            ("files", ("etax.csv", io.BytesIO(b"ma so thue\n0319998897\n"), "text/csv")),
        ]
        resp = client.post(
            "/api/rb/assess",
            data={"customer_name": "CONG TY TEST", "tax_id": "0319998887"},
            files=files,
        )
    assert resp.status_code == 200
    body = resp.json()
    assert any(f["rule_id"] == "TAX_ID_MISMATCH" for f in body["risk_flags"])
    assert "FAKE" not in str(body).upper()


def test_assess_endpoint_does_not_500_on_unparseable_file(monkeypatch, tmp_path):
    # A fake/corrupt .pdf (the "cccd.pdf" above isn't a real PDF) must not crash
    # the whole assessment - the request must still return 200 with a computed result.
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    from app.config import get_settings

    get_settings.cache_clear()

    monkeypatch.setattr(
        rb_router, "generate_narrative", lambda computed: {"why": [], "credit_memo": ""}
    )

    with TestClient(app) as client:
        files = {"files": ("broken.pdf", io.BytesIO(b"not actually a pdf file"), "application/pdf")}
        resp = client.post(
            "/api/rb/assess",
            data={"customer_name": "CONG TY TEST", "tax_id": "0319998887"},
            files=files,
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["credit_readiness"] in ("NOT_READY", "MANUAL_REVIEW_REQUIRED", "READY_WITH_CONDITIONS", "READY")


def test_assess_endpoint_risk_flags_include_frontend_contract_fields(monkeypatch, tmp_path):
    # web/components/ResultPanel.tsx renders f.rule_id, f.severity, f.impact,
    # f.recommended_action for each risk flag - the router's JSON must carry them.
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    from app.config import get_settings

    get_settings.cache_clear()

    monkeypatch.setattr(
        rb_router, "generate_narrative", lambda computed: {"why": [], "credit_memo": ""}
    )

    with TestClient(app) as client:
        files = {"files": ("note.csv", io.BytesIO(b"col1,col2\nval1,val2\n"), "text/csv")}
        resp = client.post(
            "/api/rb/assess",
            data={"customer_name": "CONG TY TEST", "tax_id": "0319998887"},
            files=files,
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["risk_flags"], "expected at least one risk flag (missing mandatory docs)"
    flag = body["risk_flags"][0]
    assert "rule_id" in flag
    assert "severity" in flag
    assert "impact" in flag
    assert "recommended_action" in flag


def test_assess_endpoint_persists_assessment(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    from app.config import get_settings

    get_settings.cache_clear()

    monkeypatch.setattr(
        rb_router, "generate_narrative", lambda computed: {"why": [], "credit_memo": ""}
    )

    from app.storage.repository import get_latest_assessment

    with TestClient(app) as client:
        files = {"files": ("note.csv", io.BytesIO(b"col1,col2\nval1,val2\n"), "text/csv")}
        resp = client.post(
            "/api/rb/assess",
            data={"customer_name": "CONG TY TEST", "tax_id": "0319998887"},
            files=files,
        )
    assert resp.status_code == 200

    saved = get_latest_assessment(str(tmp_path / "test.db"), "rb")
    assert saved is not None
    assert saved["customer_name"] == "CONG TY TEST"
    assert saved["tax_id"] == "0319998887"


def test_assess_endpoint_flags_unclassified_document_for_manual_review(monkeypatch, tmp_path):
    # A complete mandatory bundle plus one document RB cannot classify must not
    # come back READY with that document silently dropped (RB plan Global
    # Constraint, spec §5).
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    from app.config import get_settings

    get_settings.cache_clear()

    monkeypatch.setattr(
        rb_router, "generate_narrative", lambda computed: {"why": [], "credit_memo": ""}
    )

    with TestClient(app) as client:
        files = [
            ("files", ("cccd.csv", io.BytesIO(b"CAN CUOC CONG DAN\nCCCD\n"), "text/csv")),
            ("files", ("statement.csv", io.BytesIO(b"sao ke\nghi no\nghi co\n"), "text/csv")),
            ("files", ("loan.csv", io.BytesIO(b"de nghi vay\nmuc dich vay\n"), "text/csv")),
            ("files", ("khong_ro.csv", io.BytesIO(b"noi dung khong xac dinh duoc\n"), "text/csv")),
        ]
        resp = client.post(
            "/api/rb/assess",
            data={"customer_name": "CONG TY TEST", "tax_id": "0319998887"},
            files=files,
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["missing_data"] == [], "mandatory bundle should be complete"
    flag = next(f for f in body["risk_flags"] if f["rule_id"] == "UNCLASSIFIED_DOCUMENT")
    assert any("khong_ro.csv" in e for e in flag["evidence"])
    assert body["credit_readiness"] == "MANUAL_REVIEW_REQUIRED"


def test_assess_endpoint_includes_crosssell_opportunities_key(monkeypatch, tmp_path):
    # The web/app/page.tsx home page now runs RB assessment and expects
    # cross-sell suggestions back in the same response (no statement data
    # here, so the list is simply empty, but the key must always be present).
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    from app.config import get_settings

    get_settings.cache_clear()

    monkeypatch.setattr(
        rb_router, "generate_narrative", lambda computed: {"why": [], "credit_memo": ""}
    )

    with TestClient(app) as client:
        files = {"files": ("note.csv", io.BytesIO(b"col1,col2\nval1,val2\n"), "text/csv")}
        resp = client.post(
            "/api/rb/assess",
            data={"customer_name": "CONG TY TEST", "tax_id": "0319998887"},
            files=files,
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["crosssell_opportunities"] == []
    assert body["assessed_at"]


def test_assess_endpoint_crosssell_opportunities_detects_signal(monkeypatch, tmp_path):
    # A bank statement showing repeated large payments to the same partner
    # should surface a cross-sell opportunity card alongside the RB result.
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    from app.config import get_settings

    get_settings.cache_clear()

    monkeypatch.setattr(
        rb_router, "generate_narrative", lambda computed: {"why": [], "credit_memo": ""}
    )

    statement_csv = (
        "Ngay,So but toan,Ghi No,Ghi Co,Dien giai,Doi tac,TK doi tac,NH doi tac,Loai tien,Nguon\n"
        "01/01/2026,1,0,600000000,thanh toan hang,Cong ty A,,,VND,\n"
        "02/01/2026,2,0,600000000,thanh toan hang,Cong ty A,,,VND,\n"
        "03/01/2026,3,0,600000000,thanh toan hang,Cong ty A,,,VND,\n"
    ).encode("utf-8")

    with TestClient(app) as client:
        files = {"files": ("sao_ke.csv", io.BytesIO(statement_csv), "text/csv")}
        resp = client.post(
            "/api/rb/assess",
            data={"customer_name": "CONG TY TEST", "tax_id": "0319998887"},
            files=files,
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["crosssell_opportunities"], "expected at least one cross-sell opportunity card"


def test_assess_endpoint_skips_narrative_when_time_budget_already_exceeded(monkeypatch, tmp_path):
    # GreenNode's gateway has an unconfigurable ~60s hard timeout in front of
    # this container; if OCR already used most of the budget, the narrative
    # call must be skipped rather than risk a 502 that discards already-
    # computed, already-correct numbers along with it.
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test_budget.db"))
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(rb_router, "narrative_budget_exceeded", lambda start: True)

    def must_not_be_called(computed):
        raise AssertionError("generate_narrative must not be called once the time budget is exceeded")

    monkeypatch.setattr(rb_router, "generate_narrative", must_not_be_called)

    with TestClient(app) as client:
        files = {"files": ("note.csv", io.BytesIO(b"col1,col2\nval1,val2\n"), "text/csv")}
        resp = client.post(
            "/api/rb/assess",
            data={"customer_name": "CONG TY TEST", "tax_id": "0319998887"},
            files=files,
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["why"] == []
    assert body["credit_memo"] == ""
