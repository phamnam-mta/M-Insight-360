import io

from fastapi.testclient import TestClient

from app.main import app

_HEADER = "Ngay,So but toan,Ghi No,Ghi Co,Dien giai,Doi tac,Tai khoan doi tac,Ngan hang doi tac,Loai tien,Nguon\n"


def _csv_rows(n: int) -> str:
    return "".join(
        f"0{i}/06/2025,BT{i},0,200000000,Thanh toan hop dong,CONG TY DOI TAC A,,MB,VND,sao_ke\n"
        for i in range(1, n + 1)
    )


def test_assess_endpoint_returns_schema_c_shape(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    from app.config import get_settings

    get_settings.cache_clear()

    csv_content = (_HEADER + _csv_rows(3)).encode("utf-8")
    files = {"files": ("sao_ke.csv", io.BytesIO(csv_content), "text/csv")}
    with TestClient(app) as client:
        resp = client.post(
            "/api/crosssell/assess",
            data={"customer_name": "CONG TY TNHH TEST", "tax_id": "0100000001"},
            files=files,
        )
    assert resp.status_code == 200
    body = resp.json()
    for key in ("status", "request_id", "ma_lo", "ho_so", "badges", "kpi", "co_hoi", "doi_tac", "evidence", "ban_giao", "warnings", "error_code"):
        assert key in body
    assert body["ho_so"]["ten_kh"] == "CONG TY TNHH TEST"
    assert body["ho_so"]["mst"] == "0100000001"
    assert len(body["kpi"]) == 4


def test_assess_endpoint_partner_qualifies_for_rule2_and_partner_list(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test2.db"))
    from app.config import get_settings

    get_settings.cache_clear()

    csv_content = (_HEADER + _csv_rows(5)).encode("utf-8")
    files = {"files": ("sao_ke.csv", io.BytesIO(csv_content), "text/csv")}
    with TestClient(app) as client:
        resp = client.post(
            "/api/crosssell/assess",
            data={"customer_name": "CONG TY TNHH TEST", "tax_id": "0100000001"},
            files=files,
        )
    assert resp.status_code == 200
    body = resp.json()
    rule_ids = {c["rule_id"] for c in body["co_hoi"]}
    assert "RULE2_SCF" in rule_ids
    assert body["doi_tac"]["danh_sach"]
    assert body["doi_tac"]["danh_sach"][0]["trang_thai"] == "Chua kiem tra CIF"


def test_assess_endpoint_does_not_500_on_one_unsupported_file(monkeypatch, tmp_path):
    # Mirrors RB: extract_documents() raised ValueError for a single
    # unsupported/corrupt file and took the whole request down with a 500.
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test3.db"))
    from app.config import get_settings

    get_settings.cache_clear()

    files = [
        ("files", ("anh_chup.jpg", io.BytesIO(b"\xff\xd8\xff not a supported format"), "image/jpeg")),
        ("files", ("sao_ke.csv", io.BytesIO((_HEADER + _csv_rows(3)).encode("utf-8")), "text/csv")),
    ]
    with TestClient(app) as client:
        resp = client.post(
            "/api/crosssell/assess",
            data={"customer_name": "CONG TY TNHH TEST", "tax_id": "0100000001"},
            files=files,
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ho_so"]["so_gd"] == 3
    assert any("anh_chup.jpg" in w for w in body["extraction_warnings"])


def test_assess_endpoint_wires_receivables_and_payables_into_rule5(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test4.db"))
    from app.config import get_settings

    get_settings.cache_clear()

    files = {"files": ("sao_ke.csv", io.BytesIO((_HEADER + _csv_rows(3)).encode("utf-8")), "text/csv")}
    with TestClient(app) as client:
        resp = client.post(
            "/api/crosssell/assess",
            data={
                "customer_name": "CONG TY TNHH TEST",
                "tax_id": "0100000001",
                "receivables_131_current_vnd": "1000000000",
                "payables_331_vnd": "800000000",
                "total_receivable_credit_131_vnd": "2000000000",
            },
            files=files,
        )
    assert resp.status_code == 200
    body = resp.json()
    rule5a = next(c for c in body["co_hoi"] if c["rule_id"] == "RULE5A_AR")
    rule5b = next(c for c in body["co_hoi"] if c["rule_id"] == "RULE5B_AP")
    assert rule5a["deal_size"] == 800_000_000  # 80% x 1,000,000,000
    assert rule5b["deal_size"] == 800_000_000
    assert body["evidence"]["dongtien"]["noi_dung"]["leak_ratio_131"]["status"] == "tinh_duoc"


def test_assess_endpoint_block_precheck_returns_single_kpi_and_no_opportunities(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test5.db"))
    from app.config import get_settings

    get_settings.cache_clear()

    files = {"files": ("sao_ke.csv", io.BytesIO((_HEADER + _csv_rows(3)).encode("utf-8")), "text/csv")}
    with TestClient(app) as client:
        resp = client.post(
            "/api/crosssell/assess",
            data={
                "customer_name": "CONG TY TNHH TEST",
                "tax_id": "0100000001",
                "opening_balance": "0",
                "closing_balance": "999999999999",
            },
            files=files,
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "blocked"
    assert len(body["kpi"]) == 1
    assert body["co_hoi"] == []
