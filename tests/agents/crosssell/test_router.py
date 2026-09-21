import io

from fastapi.testclient import TestClient

from app.agents.crosssell import router as crosssell_router
from app.agents.crosssell.rule5_receivables import LEAK_WARNING
from app.main import app

# NOTE: the narrative function must be patched on the *router* module, not on
# app.agents.crosssell.narrative — router.py binds its own reference with
# "from .narrative import generate_narrative" at import time, so patching the
# source module left the router calling the real LLM over the network.


def test_assess_endpoint_runs_precheck_and_rules(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(crosssell_router, "generate_narrative", lambda computed: {"why": [], "credit_memo": ""})

    header = "Ngay,So but toan,Ghi No,Ghi Co,Dien giai,Doi tac,Tai khoan doi tac,Ngan hang doi tac,Loai tien,Nguon\n"
    rows = "".join(
        f"0{i}/06/2025,BT{i},0,200000000,Thanh toan hop dong,CONG TY A,,MB,VND,sao_ke\n" for i in range(1, 4)
    )
    csv_content = (header + rows).encode("utf-8")

    files = {"files": ("sao_ke.csv", io.BytesIO(csv_content), "text/csv")}
    # TestClient must be used as a context manager so FastAPI's startup event
    # (which creates the SQLite `assessments` table via init_db) actually runs
    # before the request — without `with`, lifespan startup never fires and
    # save_assessment() 500s with "no such table: assessments".
    with TestClient(app) as client:
        resp = client.post(
            "/api/crosssell/assess",
            data={"customer_name": "CONG TY TNHH TEST", "tax_id": "0100000001"},
            files=files,
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["precheck"]["verdict"] == "WARN"  # no balance columns in this schema
    rule_ids = {r["rule_id"] for r in body["opportunities"]}
    assert "RULE2_SCF" in rule_ids
    assert body["dashboard"]


def test_assess_endpoint_wires_rule5d_leak_ratio_end_to_end(monkeypatch, tmp_path):
    # Regression test for a real gap found in review: the router computed
    # flow_classification but never actually passed leak_ratio into
    # evaluate_rule5(), so the mandatory LEAK_WARNING sentence (spec §7 Rule
    # 5D) was unreachable through the real HTTP pipeline even though it was
    # unit-tested inside rule5_receivables.py.
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test2.db"))
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(crosssell_router, "generate_narrative", lambda computed: {"why": [], "credit_memo": ""})

    header = "Ngay,So but toan,Ghi No,Ghi Co,Dien giai,Doi tac,Tai khoan doi tac,Ngan hang doi tac,Loai tien,Nguon\n"
    rows = "".join(
        f"0{i}/06/2025,BT{i},0,200000000,Thanh toan hop dong,CONG TY A,,MB,VND,sao_ke\n" for i in range(1, 4)
    )
    csv_content = (header + rows).encode("utf-8")
    files = {"files": ("sao_ke.csv", io.BytesIO(csv_content), "text/csv")}

    with TestClient(app) as client:
        resp = client.post(
            "/api/crosssell/assess",
            data={
                "customer_name": "CONG TY TNHH TEST",
                "tax_id": "0100000001",
                # operating_in = 600,000,000 VND (3 x 200M direct inflow); with a total 131
                # credit turnover of 2,000,000,000 VND the leak ratio is 0.3 (< 50%).
                "receivables_131_current_vnd": "1000000000",
                "total_receivable_credit_131_vnd": "2000000000",
            },
            files=files,
        )
    assert resp.status_code == 200
    body = resp.json()
    rule5 = next(r for r in body["opportunities"] if r["rule_id"] == "RULE5_RECEIVABLES")
    assert rule5["status"] == "KÍCH HOẠT"
    assert LEAK_WARNING in " ".join(rule5["evidence"])


def test_assess_endpoint_does_not_500_on_one_unsupported_file(monkeypatch, tmp_path):
    # Mirrors RB: extract_documents() raised ValueError for a single
    # unsupported/corrupt file and took the whole request down with a 500.
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test3.db"))
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(
        crosssell_router, "generate_narrative", lambda computed: {"why": [], "credit_memo": ""}
    )

    header = "Ngay,So but toan,Ghi No,Ghi Co,Dien giai,Doi tac,Tai khoan doi tac,Ngan hang doi tac,Loai tien,Nguon\n"
    rows = "".join(
        f"0{i}/06/2025,BT{i},0,200000000,Thanh toan hop dong,CONG TY A,,MB,VND,sao_ke\n" for i in range(1, 4)
    )
    files = [
        ("files", ("anh_chup.jpg", io.BytesIO(b"\xff\xd8\xff not a supported format"), "image/jpeg")),
        ("files", ("sao_ke.csv", io.BytesIO((header + rows).encode("utf-8")), "text/csv")),
    ]
    with TestClient(app) as client:
        resp = client.post(
            "/api/crosssell/assess",
            data={"customer_name": "CONG TY TNHH TEST", "tax_id": "0100000001"},
            files=files,
        )
    assert resp.status_code == 200
    body = resp.json()
    # the good file was still parsed
    assert body["dashboard"]
    assert body["precheck"]["total_credit"] == 600_000_000
    # and the bad one is reported rather than silently dropped
    assert any("anh_chup.jpg" in w for w in body["extraction_warnings"])


def test_assess_endpoint_opportunities_include_frontend_contract_fields(monkeypatch, tmp_path):
    # Mirrors RB's contract test: the shared ResultPanel renders f.impact, and
    # Cross-sell emitted a bare asdict() with no "impact" key.
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test4.db"))
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(
        crosssell_router, "generate_narrative", lambda computed: {"why": [], "credit_memo": ""}
    )

    header = "Ngay,So but toan,Ghi No,Ghi Co,Dien giai,Doi tac,Tai khoan doi tac,Ngan hang doi tac,Loai tien,Nguon\n"
    rows = "".join(
        f"0{i}/06/2025,BT{i},0,200000000,Thanh toan hop dong,CONG TY A,,MB,VND,sao_ke\n" for i in range(1, 4)
    )
    files = {"files": ("sao_ke.csv", io.BytesIO((header + rows).encode("utf-8")), "text/csv")}
    with TestClient(app) as client:
        resp = client.post(
            "/api/crosssell/assess",
            data={"customer_name": "CONG TY TNHH TEST", "tax_id": "0100000001"},
            files=files,
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["opportunities"]
    for opportunity in body["opportunities"]:
        assert "rule_id" in opportunity
        assert "status" in opportunity
        assert "impact" in opportunity
    rule2 = next(r for r in body["opportunities"] if r["rule_id"] == "RULE2_SCF")
    assert rule2["impact"] == rule2["comment"]
