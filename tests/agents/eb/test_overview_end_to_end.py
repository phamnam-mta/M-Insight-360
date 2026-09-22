import io

from fastapi.testclient import TestClient

from app.agents.eb import router as eb_router
from app.main import app

# Conditions C01 (Đối tượng áp dụng), C03 (Doanh thu 6 tháng qua TKTT), C04
# (Ngành nghề), C06 (03/05 đối tác), C11 (Lịch sử quan hệ tín dụng) are
# PENDING_INTERNAL_CHECK or INSUFFICIENT_DATA *by construction* — no CIF/CIC
# connection exists, no statement window can be verified, the prohibited-
# industries list is empty until a real policy document is loaded, and the
# "03/05" policy reading is unresolved. These never resolve PASS/FAIL, with
# or without supporting documents — that is the honest, intended behavior
# this test pins, not a gap in the fixture.
_ALWAYS_PENDING = {"C01", "C03", "C04", "C06", "C11"}


def _complete_evidence_files():
    dkkd = (
        "GIAY CHUNG NHAN DANG KY DOANH NGHIEP\n"
        "Ngay thanh lap: 01/01/2020\n"
        "Nganh nghe kinh doanh: Ban le hang tieu dung\n"
        "Tinh trang: dang hoat dong\n"
    ).encode()
    bctc = (
        "BAO CAO TAI CHINH 2025\n"
        "Doanh thu thuan: 50.000.000.000\n"
        "Von chu so huu: 500.000.000\n"
        "Loi nhuan gop: 1.000.000.000\n"
        "Chi phi lai vay: 300.000.000\n"
    ).encode()
    pakd = "PHUONG AN KINH DOANH\nLNST theo PAKD: 200.000.000\n".encode()
    return [
        ("files", ("dkkd.csv", io.BytesIO(dkkd), "text/csv")),
        ("files", ("bctc.csv", io.BytesIO(bctc), "text/csv")),
        ("files", ("pakd.csv", io.BytesIO(pakd), "text/csv")),
    ]


def _sparse_bundle_files():
    dkkd = "GIAY CHUNG NHAN DANG KY DOANH NGHIEP\nNgay thanh lap: 01/01/2020\n".encode()
    return [("files", ("dkkd.csv", io.BytesIO(dkkd), "text/csv"))]


def _post(client, files):
    return client.post(
        "/api/eb/assess",
        data={"customer_name": "CONG TY TNHH TEST", "tax_id": "0100000099"},
        files=files,
    )


def test_complete_evidence_bundle_resolves_every_computable_condition(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "e2e1.db"))
    monkeypatch.setenv("CASE_FILES_DIR", str(tmp_path / "eb_files1"))
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(eb_router, "generate_narrative", lambda computed: {"why": [], "credit_memo": ""})

    with TestClient(app) as client:
        resp = _post(client, _complete_evidence_files())
    body = resp.json()
    for row in body["overview"]:
        if row["condition_id"] in _ALWAYS_PENDING:
            assert row["result"] in ("INSUFFICIENT_DATA", "PENDING_INTERNAL_CHECK")
        else:
            assert row["result"] in ("PASS", "FAIL"), (row["condition_id"], row["result"])


def test_sparse_bundle_never_silently_reports_ready(monkeypatch, tmp_path):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "e2e2.db"))
    monkeypatch.setenv("CASE_FILES_DIR", str(tmp_path / "eb_files2"))
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(eb_router, "generate_narrative", lambda computed: {"why": [], "credit_memo": ""})

    with TestClient(app) as client:
        resp = _post(client, _sparse_bundle_files())
    body = resp.json()
    c11 = next(r for r in body["overview"] if r["condition_id"] == "C11")
    assert c11["result"] == "PENDING_INTERNAL_CHECK"
    assert body["overall_conclusion"] == "Chưa đủ căn cứ xác định điều kiện áp dụng"
    assert body["overview_summary"]["pending"] >= 4
