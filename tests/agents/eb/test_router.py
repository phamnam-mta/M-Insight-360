import io

from fastapi.testclient import TestClient

from app.agents.eb import router as eb_router
from app.main import app

# NOTE: the narrative function must be patched on the *router* module, not on
# app.agents.eb.narrative — router.py binds its own reference with
# "from .narrative import generate_narrative" at import time, so patching the
# source module left the router calling the real LLM over the network.


def test_assess_endpoint_computes_rf01_and_rf02(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(eb_router, "generate_narrative", lambda computed: {"why": [], "credit_memo": ""})

    client = TestClient(app)
    bctc_text = (
        b"Von chu so huu: 500,000,000\n"
        b"Tai san ngan han: 1,000,000,000\n"
        b"No ngan han: 1,500,000,000\n"
        b"Luu chuyen tien thuan tu hoat dong kinh doanh: -200,000,000\n"
    )
    files = {"files": ("bctc.csv", io.BytesIO(bctc_text), "text/csv")}
    resp = client.post(
        "/api/eb/assess",
        data={"customer_name": "CONG TY TNHH TEST", "tax_id": "0100000001"},
        files=files,
    )
    assert resp.status_code == 200
    body = resp.json()
    flag_ids = {f["rule_id"] for f in body["risk_flags"]}
    assert "RF01" in flag_ids
    assert "RF02" in flag_ids
    assert body["export_available"] is True


def test_assess_endpoint_missing_documents_reports_not_ready(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test2.db"))
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(eb_router, "generate_narrative", lambda computed: {"why": [], "credit_memo": ""})

    client = TestClient(app)
    files = {"files": ("empty.csv", io.BytesIO(b"khong co gi lien quan"), "text/csv")}
    resp = client.post(
        "/api/eb/assess",
        data={"customer_name": "CONG TY TNHH TEST", "tax_id": "0100000001"},
        files=files,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["missing_data"], "expected at least one missing mandatory document type"
    assert body["credit_readiness"] == "NOT_READY"
    assert body["recommendation"] == "ADDITIONAL_DOCUMENTS_REQUIRED"


def test_assess_endpoint_rf04_never_defaults_to_pass_without_dsp(monkeypatch, tmp_path):
    # Regression guard for the RF04/DSP trap explicitly called out in spec §6.
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test3.db"))
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(eb_router, "generate_narrative", lambda computed: {"why": [], "credit_memo": ""})

    client = TestClient(app)
    bctc_text = b"Von chu so huu: 500,000,000\nDoanh thu thuan: 1,000,000,000\n"
    files = {"files": ("bctc.csv", io.BytesIO(bctc_text), "text/csv")}
    resp = client.post(
        "/api/eb/assess",
        data={"customer_name": "CONG TY TNHH TEST", "tax_id": "0100000001"},
        files=files,
    )
    assert resp.status_code == 200
    body = resp.json()
    rf04 = next(f for f in body["risk_flags"] if f["rule_id"] == "RF04")
    assert rf04["status"] == "CHƯA ĐÁNH GIÁ"


def test_export_endpoint_returns_docx():
    client = TestClient(app)
    computed = {
        "customer_profile": {"customer_name": "CONG TY TNHH TEST", "tax_id": "0100000001"},
        "credit_engine": {}, "risk_flags": [], "missing_data": [], "recommendation": "PROCEED_FOR_HUMAN_REVIEW",
        "why": [], "credit_memo": "",
    }
    resp = client.post("/api/eb/export", json=computed)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert len(resp.content) > 0


def test_assess_endpoint_recognises_a_real_bctc_bundle_as_complete(monkeypatch, tmp_path):
    # Regression: EB's own keyword classifier matched "ma so thue" (present in
    # the header of every VN business document) as LEGAL_IDENTITY first and
    # returned, so a real BCTC + loan-request bundle came back with
    # missing_data ["FINANCIAL_STATEMENT", "LOAN_REQUEST"] and
    # ADDITIONAL_DOCUMENTS_REQUIRED while EB was holding the BCTC.
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test4.db"))
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(eb_router, "generate_narrative", lambda computed: {"why": [], "credit_memo": ""})

    files = [
        ("files", ("dkkd.csv", io.BytesIO(
            "GIAY CHUNG NHAN DANG KY DOANH NGHIEP\nDang ky kinh doanh - Ma so thue: 0100000001\n".encode()
        ), "text/csv")),
        ("files", ("bctc.csv", io.BytesIO(
            "Ma so thue: 0100000001\nBAO CAO TAI CHINH 2024\nBANG CAN DOI KE TOAN\n"
            "Von chu so huu: 5.000.000.000\nTai san ngan han: 3.500.000.000\nNo ngan han: 2.000.000.000\n".encode()
        ), "text/csv")),
        ("files", ("de_nghi_vay.csv", io.BytesIO(
            "Ma so thue: 0100000001\nGIAY DE NGHI CAP TIN DUNG\nMuc dich vay: bo sung von luu dong\n".encode()
        ), "text/csv")),
    ]
    with TestClient(app) as client:
        resp = client.post(
            "/api/eb/assess",
            data={"customer_name": "CONG TY TNHH TEST", "tax_id": "0100000001"},
            files=files,
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["missing_data"] == []
    assert body["recommendation"] != "ADDITIONAL_DOCUMENTS_REQUIRED"


def test_assess_endpoint_does_not_500_on_one_unsupported_file(monkeypatch, tmp_path):
    # Mirrors RB: extract_documents() raised ValueError for a single
    # unsupported/corrupt file and took the whole request down with a 500.
    # One bad file must degrade into a warning flag, not sink the batch.
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test5.db"))
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(eb_router, "generate_narrative", lambda computed: {"why": [], "credit_memo": ""})

    files = [
        ("files", ("anh_chup.jpg", io.BytesIO(b"\xff\xd8\xff not a supported format"), "image/jpeg")),
        ("files", ("bctc.csv", io.BytesIO(
            # VN-locale dots, not commas: a .csv's commas are column separators,
            # so "1,000,000,000" would reach the parser as "1 | 000 | 000 | 000".
            "Von chu so huu: 500.000.000\nTai san ngan han: 1.000.000.000\nNo ngan han: 1.500.000.000\n".encode()
        ), "text/csv")),
    ]
    with TestClient(app) as client:
        resp = client.post(
            "/api/eb/assess",
            data={"customer_name": "CONG TY TNHH TEST", "tax_id": "0100000001"},
            files=files,
        )
    assert resp.status_code == 200
    body = resp.json()
    # the good file was still processed
    assert body["credit_engine"]["nwc"]["value"] == -500_000_000
    # and the bad one is reported rather than silently dropped
    warning_flags = [f for f in body["risk_flags"] if f["rule_id"] == "LOW_OCR_CONFIDENCE"]
    assert warning_flags, "expected a flag naming the skipped file"
    assert "anh_chup.jpg" in " ".join(warning_flags[0]["evidence"])


def test_assess_endpoint_skips_narrative_when_time_budget_already_exceeded(monkeypatch, tmp_path):
    # The narrative LLM call is the one non-essential step in the pipeline —
    # GreenNode's gateway has an unconfigurable ~60s hard timeout in front of
    # this container, so if OCR already used most of the budget, attempting
    # the narrative call risks a 502 that throws away already-correct,
    # already-computed numbers along with it. Must be skipped, not attempted.
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test7.db"))
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(eb_router, "narrative_budget_exceeded", lambda start: True)

    def must_not_be_called(computed):
        raise AssertionError("generate_narrative must not be called once the time budget is exceeded")

    monkeypatch.setattr(eb_router, "generate_narrative", must_not_be_called)

    files = {"files": ("bctc.csv", io.BytesIO(
        "Von chu so huu: 500.000.000\nTai san ngan han: 1.000.000.000\nNo ngan han: 1.500.000.000\n".encode()
    ), "text/csv")}
    with TestClient(app) as client:
        resp = client.post(
            "/api/eb/assess",
            data={"customer_name": "CONG TY TNHH TEST", "tax_id": "0100000001"},
            files=files,
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["credit_engine"]["nwc"]["value"] == -500_000_000
    assert body["why"] == []


def test_assess_endpoint_risk_flags_include_frontend_contract_fields(monkeypatch, tmp_path):
    # Mirrors RB's contract test: web/components/ResultPanel.tsx renders
    # f.rule_id, f.severity, f.impact and f.status for each risk flag, and EB
    # emitted a bare asdict() with no "impact" key — every EB flag rendered
    # with an empty description.
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test6.db"))
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(eb_router, "generate_narrative", lambda computed: {"why": [], "credit_memo": ""})

    files = {"files": ("bctc.csv", io.BytesIO(
        "Von chu so huu: 500.000.000\nTai san ngan han: 1.000.000.000\nNo ngan han: 1.500.000.000\n".encode()
    ), "text/csv")}
    with TestClient(app) as client:
        resp = client.post(
            "/api/eb/assess",
            data={"customer_name": "CONG TY TNHH TEST", "tax_id": "0100000001"},
            files=files,
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["risk_flags"]
    for flag in body["risk_flags"]:
        assert "rule_id" in flag
        assert "severity" in flag
        assert "status" in flag
        assert "impact" in flag
        assert "recommended_action" in flag
    rf01 = next(f for f in body["risk_flags"] if f["rule_id"] == "RF01")
    assert rf01["impact"] == rf01["comment"]
    assert rf01["impact"], "an activated flag must carry a non-empty description"
    for rule in body["policy_eligibility"]:
        assert "impact" in rule


def test_assess_endpoint_case_id_is_unique_per_run(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test8.db"))
    monkeypatch.setenv("CASE_FILES_DIR", str(tmp_path / "eb_files"))
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(eb_router, "generate_narrative", lambda computed: {"why": [], "credit_memo": ""})

    with TestClient(app) as client:
        files = {"files": ("bctc.csv", io.BytesIO(b"Von chu so huu: 500.000.000\n"), "text/csv")}
        resp1 = client.post("/api/eb/assess", data={"customer_name": "A", "tax_id": "0100000001"}, files=files)
        files2 = {"files": ("bctc.csv", io.BytesIO(b"Von chu so huu: 500.000.000\n"), "text/csv")}
        resp2 = client.post("/api/eb/assess", data={"customer_name": "A", "tax_id": "0100000001"}, files=files2)
    assert resp1.json()["case_id"] != resp2.json()["case_id"]
    assert resp1.json()["case_id"].startswith("EB-0100000001-")


def test_assess_endpoint_persists_uploaded_file_and_serves_it_back(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test9.db"))
    monkeypatch.setenv("CASE_FILES_DIR", str(tmp_path / "eb_files"))
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(eb_router, "generate_narrative", lambda computed: {"why": [], "credit_memo": ""})

    content = b"Tai san ngan han: 1.000.000.000\nNo ngan han: 1.500.000.000\n"
    files = {"files": ("bctc.csv", io.BytesIO(content), "text/csv")}
    with TestClient(app) as client:
        resp = client.post("/api/eb/assess", data={"customer_name": "A", "tax_id": "0100000001"}, files=files)
        body = resp.json()
        case_id = body["case_id"]
        nwc_evidence = body["credit_engine"]["nwc"]
        assert nwc_evidence.get("evidence"), "expected NWC metric to carry evidence citations"
        file_id = list(nwc_evidence["evidence"].values())[0][0]["file_id"]
        file_resp = client.get(f"/api/eb/files/{case_id}/{file_id}")
    assert file_resp.status_code == 200
    assert file_resp.content == content


def test_get_file_endpoint_404s_on_unknown_case(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test10.db"))
    monkeypatch.setenv("CASE_FILES_DIR", str(tmp_path / "eb_files"))
    from app.config import get_settings

    get_settings.cache_clear()
    with TestClient(app) as client:
        resp = client.get("/api/eb/files/NOPE/NOPE")
    assert resp.status_code == 404


def test_assess_endpoint_includes_overview_and_never_shows_ready_without_full_checklist(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test11.db"))
    monkeypatch.setenv("CASE_FILES_DIR", str(tmp_path / "eb_files"))
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(eb_router, "generate_narrative", lambda computed: {"why": [], "credit_memo": ""})

    files = {"files": ("bctc.csv", io.BytesIO(b"Von chu so huu: 500.000.000\n"), "text/csv")}
    with TestClient(app) as client:
        resp = client.post("/api/eb/assess", data={"customer_name": "A", "tax_id": "0100000001"}, files=files)
    body = resp.json()
    assert len(body["overview"]) == 11
    assert body["overview_summary"]["pending"] > 0
    assert body["overall_conclusion"] == "Chưa đủ căn cứ xác định điều kiện áp dụng"
    assert "credit_engine" in body and "output_contract_financing_ratio" in body["credit_engine"]


def test_assess_endpoint_opportunities_empty_without_statement(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test12.db"))
    monkeypatch.setenv("CASE_FILES_DIR", str(tmp_path / "eb_files"))
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(eb_router, "generate_narrative", lambda computed: {"why": [], "credit_memo": ""})

    files = {"files": ("bctc.csv", io.BytesIO(b"Von chu so huu: 500.000.000\n"), "text/csv")}
    with TestClient(app) as client:
        resp = client.post("/api/eb/assess", data={"customer_name": "A", "tax_id": "0100000001"}, files=files)
    assert resp.json()["opportunities"] == []


def test_stress_test_endpoint_recomputes_metrics():
    client = TestClient(app)
    resp = client.post("/api/eb/stress-test", json={
        "inputs": {"ebit_vnd": 800_000_000, "interest_expense_vnd": 200_000_000},
        "deltas": {"margin_pct": -50},
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["before"]["icr"]["value"] == 4.0
    assert body["after"]["icr"]["value"] == 2.0
