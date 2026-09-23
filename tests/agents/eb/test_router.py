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
    assert resp.json()["crosssell_opportunities"] == []


def test_assess_endpoint_includes_new_metrics_and_flags(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test_new_metrics.db"))
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(eb_router, "generate_narrative", lambda computed: {"why": [], "credit_memo": ""})

    client = TestClient(app)
    csv_text = (
        b"Chi tieu,31/12/2025\n"
        b"Von chu so huu,500000000\n"
        b"Tai san ngan han,300000000\n"
        b"No ngan han,100000000\n"
        b"Tai san dai han,400000000\n"
        b"No dai han,100000000\n"
        b"Phai thu khach hang,150000000\n"
        b"Hang ton kho,100000000\n"
        b"Loi nhuan truoc thue,200000000\n"
        b"Loi nhuan sau thue,160000000\n"
        b"Chi phi lai vay,50000000\n"
        b"Khau hao,20000000\n"
    )
    files = {"files": ("bctc.csv", io.BytesIO(csv_text), "text/csv")}
    resp = client.post(
        "/api/eb/assess",
        data={"customer_name": "CONG TY TNHH TEST", "tax_id": "0100000001"},
        files=files,
    )
    assert resp.status_code == 200
    body = resp.json()
    for key in ("ebitda", "liquidity_balance", "long_term_capital", "total_borrowings", "receivables_financing_limit_80", "receivables_financing_limit_85"):
        assert key in body["credit_engine"], f"{key} missing from credit_engine"
    assert "capital_balance_check" in body
    rule_ids = {f["rule_id"] for f in body["risk_flags"]}
    assert {"RF06", "RF07"}.issubset(rule_ids)


def test_assess_endpoint_reports_available_and_selected_period(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test_period.db"))
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(eb_router, "generate_narrative", lambda computed: {"why": [], "credit_memo": ""})

    client = TestClient(app)
    csv_text = (
        b"Chi tieu,31/12/2025,31/12/2024\n"
        b"Von chu so huu,500000000,400000000\n"
        b"Tai san ngan han,1000000000,900000000\n"
        b"No ngan han,600000000,550000000\n"
    )
    files = {"files": ("bctc.csv", io.BytesIO(csv_text), "text/csv")}
    resp = client.post(
        "/api/eb/assess",
        data={"customer_name": "CONG TY TNHH TEST", "tax_id": "0100000001"},
        files=files,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ho_so_period"]["selected"] == "2025"
    assert "2024" in body["ho_so_period"]["available"]


def test_assess_endpoint_honors_explicit_report_period(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test_period2.db"))
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(eb_router, "generate_narrative", lambda computed: {"why": [], "credit_memo": ""})

    client = TestClient(app)
    csv_text = (
        b"Chi tieu,31/12/2025,31/12/2024\n"
        b"Von chu so huu,500000000,400000000\n"
    )
    files = {"files": ("bctc.csv", io.BytesIO(csv_text), "text/csv")}
    resp = client.post(
        "/api/eb/assess",
        data={"customer_name": "CONG TY TNHH TEST", "tax_id": "0100000001", "report_period": "2024"},
        files=files,
    )
    body = resp.json()
    assert body["ho_so_period"]["selected"] == "2024"
    # NWC is NEED_MORE_DATA here (no current_assets/current_liabilities rows in
    # this fixture), so RF01 falls back to reporting equity_vnd directly —
    # proving the 2024 column (400M), not the 2025 column (500M), was selected.
    rf01 = next(f for f in body["risk_flags"] if f["rule_id"] == "RF01")
    assert rf01["observed_value"] == 400_000_000


def test_assess_endpoint_reports_visible_fallback_notice_for_unavailable_period(monkeypatch, tmp_path):
    # Important finding: when the requested report_period isn't among the
    # document's detected years, the router silently falls back to the most
    # recent one — the frontend must be able to tell the user this happened
    # rather than silently showing a different year than the one they picked.
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test_period_fallback.db"))
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(eb_router, "generate_narrative", lambda computed: {"why": [], "credit_memo": ""})

    client = TestClient(app)
    csv_text = (
        b"Chi tieu,31/12/2025,31/12/2024\n"
        b"Von chu so huu,500000000,400000000\n"
    )
    files = {"files": ("bctc.csv", io.BytesIO(csv_text), "text/csv")}
    resp = client.post(
        "/api/eb/assess",
        data={"customer_name": "CONG TY TNHH TEST", "tax_id": "0100000001", "report_period": "2099"},
        files=files,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ho_so_period"]["selected"] == "2025"  # fell back to most recent
    assert body["ho_so_period"]["requested"] == "2099"
    assert body["ho_so_period"]["fallback_notice"]


def test_assess_endpoint_no_fallback_notice_when_period_honored(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test_period_no_fallback.db"))
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(eb_router, "generate_narrative", lambda computed: {"why": [], "credit_memo": ""})

    client = TestClient(app)
    csv_text = (
        b"Chi tieu,31/12/2025,31/12/2024\n"
        b"Von chu so huu,500000000,400000000\n"
    )
    files = {"files": ("bctc.csv", io.BytesIO(csv_text), "text/csv")}
    resp = client.post(
        "/api/eb/assess",
        data={"customer_name": "CONG TY TNHH TEST", "tax_id": "0100000001", "report_period": "2024"},
        files=files,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ho_so_period"]["selected"] == "2024"
    assert "fallback_notice" not in body["ho_so_period"]


def test_stress_test_v2_endpoint_returns_new_contract():
    with TestClient(app) as client:
        resp = client.post(
            "/api/eb/stress-test",
            json={
                "inputs": {"net_revenue_vnd": 1_000_000_000, "pbt_vnd": 200_000_000, "pat_vnd": 160_000_000,
                           "interest_expense_vnd": 50_000_000, "interest_due_vnd": 50_000_000, "principal_due_vnd": 100_000_000,
                           "depreciation_vnd": 20_000_000},
                "deltas": {"revenue_pct": -10, "ebit_pct": -15, "interest_pct": 15},
            },
        )
    assert resp.status_code == 200
    body = resp.json()
    assert "conclusions" in body
    assert "buffers" in body
    assert body["disclaimer"]


def test_assess_endpoint_exposes_raw_financial_inputs_channel(monkeypatch, tmp_path):
    # Critical fix regression guard: the frontend (FinancialDataTable,
    # StressTestDrawer) needs a raw extracted-field map to read from —
    # scavenging Metric.input_values across credit_engine metrics silently
    # misses any field no metric happens to expose (inventory_vnd,
    # payables_vnd, cash_vnd, non_current_assets_vnd) and, for EBIT/DSCR,
    # exposes generic/mismatched keys. computed["financial_inputs"] must
    # carry the real EbFinancialInputs field names/values directly.
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test_financial_inputs.db"))
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(eb_router, "generate_narrative", lambda computed: {"why": [], "credit_memo": ""})

    client = TestClient(app)
    csv_text = (
        b"Chi tieu,31/12/2025\n"
        b"Von chu so huu,500000000\n"
        b"Tai san ngan han,300000000\n"
        b"No ngan han,100000000\n"
        b"Tai san dai han,400000000\n"
        b"Hang ton kho,100000000\n"
        b"Phai tra nguoi ban,50000000\n"
        b"Tien va tuong duong tien,30000000\n"
    )
    files = {"files": ("bctc.csv", io.BytesIO(csv_text), "text/csv")}
    resp = client.post(
        "/api/eb/assess",
        data={"customer_name": "CONG TY TNHH TEST", "tax_id": "0100000001"},
        files=files,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "financial_inputs" in body
    assert body["financial_inputs"]["equity_vnd"] == 500_000_000
    # These four fields are the ones no credit_engine metric ever exposes in
    # its input_values — they must still be readable from the raw channel.
    assert body["financial_inputs"]["non_current_assets_vnd"] == 400_000_000
    assert body["financial_inputs"]["inventory_vnd"] == 100_000_000
    assert body["financial_inputs"]["payables_vnd"] == 50_000_000
    assert body["financial_inputs"]["cash_vnd"] == 30_000_000


def test_stress_test_end_to_end_from_real_assess_response(monkeypatch, tmp_path):
    # Integration regression guard for the review's Critical #1/#2: build the
    # stress-test request exactly the way the frontend does (POST /assess,
    # then re-post computed["financial_inputs"] verbatim as stress-test
    # inputs) and assert the EBIT delta actually moves EBIT, and DSCR is
    # computable rather than perpetually NEED_MORE_DATA.
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test_stress_e2e.db"))
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(eb_router, "generate_narrative", lambda computed: {"why": [], "credit_memo": ""})

    client = TestClient(app)
    csv_text = (
        b"Chi tieu,31/12/2025\n"
        b"Loi nhuan truoc thue,300000000\n"
        b"Loi nhuan sau thue,240000000\n"
        b"Khau hao,50000000\n"
        b"Chi phi lai vay,40000000\n"
        b"Lai den han,40000000\n"
        b"Goc den han,100000000\n"
    )
    files = {"files": ("bctc.csv", io.BytesIO(csv_text), "text/csv")}
    assess_resp = client.post(
        "/api/eb/assess",
        data={"customer_name": "CONG TY TNHH TEST", "tax_id": "0100000001"},
        files=files,
    )
    assert assess_resp.status_code == 200
    financial_inputs = assess_resp.json()["financial_inputs"]
    assert "ebit_vnd" not in financial_inputs  # never directly extracted here — must fall through to pbt+interest

    stress_resp = client.post(
        "/api/eb/stress-test",
        json={"inputs": financial_inputs, "deltas": {"ebit_pct": -20}},
    )
    assert stress_resp.status_code == 200
    body = stress_resp.json()
    ebit_before = body["before"]["ebit"]
    ebit_after = body["after"]["ebit"]
    assert ebit_before == 300_000_000 + 40_000_000  # PBT + interest_expense
    assert ebit_after == round(ebit_before * 0.8, 2)
    assert ebit_after != ebit_before
    assert body["after"]["dscr"]["status"] == "OK"


def test_save_and_list_stress_scenario_endpoints(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "scenario_test.db"))
    from app.config import get_settings

    get_settings.cache_clear()
    with TestClient(app) as client:
        save_resp = client.post(
            "/api/eb/stress-test/scenarios",
            json={"case_id": "EB-123", "name": "Bất lợi", "created_by": "RM", "report_period": "2025",
                  "request": {"preset": "bat_loi"}, "response": {"after": {}}},
        )
        assert save_resp.status_code == 200
        list_resp = client.get("/api/eb/stress-test/scenarios", params={"case_id": "EB-123"})
    assert list_resp.status_code == 200
    assert list_resp.json()["scenarios"][0]["name"] == "Bất lợi"
