import io

from fastapi.testclient import TestClient

from app.agents.crosssell import narrative as crosssell_narrative
from app.main import app


def test_assess_endpoint_runs_precheck_and_rules(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(crosssell_narrative, "generate_narrative", lambda computed: {"why": [], "credit_memo": ""})

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
