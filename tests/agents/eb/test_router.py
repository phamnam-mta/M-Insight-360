import io

from fastapi.testclient import TestClient

from app.agents.eb import narrative as eb_narrative
from app.main import app


def test_assess_endpoint_computes_rf01_and_rf02(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(eb_narrative, "generate_narrative", lambda computed: {"why": [], "credit_memo": ""})

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
    monkeypatch.setattr(eb_narrative, "generate_narrative", lambda computed: {"why": [], "credit_memo": ""})

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
    monkeypatch.setattr(eb_narrative, "generate_narrative", lambda computed: {"why": [], "credit_memo": ""})

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
    from app.agents.eb import router as eb_router

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
    from app.agents.eb import router as eb_router

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
