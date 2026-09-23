"""T29-T33 — the v2.4 regression suite named directly in
AGENT_ThamDinh_INSTRUCTION_FINAL.md, keyed to the Alpha Group 2026-09-23
incident. Each test's docstring quotes the instruction's own expectation."""
import io

import openpyxl
from fastapi.testclient import TestClient

from app.agents.eb import router as eb_router
from app.main import app


def _alpha_group_workbook(*, sheet_order_reversed: bool = False, with_stt: bool = False) -> io.BytesIO:
    wb = openpyxl.Workbook()
    bctc = wb.active
    bctc.title = "10_BCTC_TOM_TAT"
    if with_stt:
        bctc.append(["STT", "Chi tieu", "Ma so", "So tien"])
        bctc.append(["10", "Doanh thu thuan", "10", "90105893754"])
        bctc.append(["11", "Cac khoan giam tru doanh thu", "11", "0"])
        bctc.append(["Von chu so huu", "", "", "580965107518"])
    elif sheet_order_reversed:
        bctc.append(["Chi tieu", "31/12/2024", "31/12/2025"])
        bctc.append(["Von chu so huu", "500000000000", "580965107518"])
        bctc.append(["Doanh thu thuan", "80000000000", "90105893754"])
    else:
        bctc.append(["Chi tieu", "So cuoi nam", "So dau nam"])
        bctc.append(["Von chu so huu", "580965107518", "500000000000"])
        bctc.append(["Doanh thu thuan", "90105893754", "80000000000"])
        bctc.append(["Bao cao lap ngay 31/12/2025"])
    saoke = wb.create_sheet("SAO KE")
    saoke.append(["Ngay GD", "Dien giai", "So tien"])
    for d in range(1, 15):
        saoke.append([f"{d:02d}/01/2026", f"Giao dich {d}", 1_000_000 * d])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def _assess(monkeypatch, tmp_path, db_name, buf, **extra_data):
    monkeypatch.setenv("DB_PATH", str(tmp_path / db_name))
    monkeypatch.setenv("CASE_FILES_DIR", str(tmp_path / f"{db_name}_files"))
    from app.config import get_settings
    get_settings.cache_clear()
    monkeypatch.setattr(eb_router, "generate_narrative", lambda computed: {"why": [], "credit_memo": ""})
    client = TestClient(app)
    return client.post(
        "/api/eb/assess",
        data={"customer_name": "ALPHA GROUP", "tax_id": "0100000001", **extra_data},
        files={"files": ("ho_so.xlsx", buf, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )


def test_t29_report_year_never_taken_from_bank_statement_dates(monkeypatch, tmp_path):
    """T29: Workbook có sao kê 924 giao dịch ngày 2026, BCTC năm 2025 ->
    nam_bao_cao = 2025. Không được lấy 2026 từ ngày giao dịch trên sao kê."""
    resp = _assess(monkeypatch, tmp_path, "t29", _alpha_group_workbook())
    assert resp.json()["ho_so_period"]["selected"] == "2025"


def test_t30_column_order_reversed_still_picks_correct_year(monkeypatch, tmp_path):
    """T30: Sheet BCTC xếp cột 2024 trước 2025, người dùng chọn 2025 ->
    Doanh thu = 90.105.893.754 (cột 2025), không phải số cột 2024."""
    resp = _assess(
        monkeypatch, tmp_path, "t30", _alpha_group_workbook(sheet_order_reversed=True),
        report_period="2025",
    )
    assert resp.json()["financial_inputs"]["net_revenue_vnd"] == 90_105_893_754.0


def test_t31_stt_column_never_captured_as_field_value(monkeypatch, tmp_path):
    """T31: Sheet có cột STT 1-20; STT 10/11 trùng mã KQKD 10/11 -> Doanh
    thu không bị gán bằng số dòng STT 10. Không trường nào mang giá trị
    là số năm."""
    resp = _assess(monkeypatch, tmp_path, "t31", _alpha_group_workbook(with_stt=True))
    body = resp.json()
    assert body["financial_inputs"]["net_revenue_vnd"] == 90_105_893_754.0
    for value in body["financial_inputs"].values():
        assert value not in (10.0, 11.0)


def test_t32_equity_matches_across_bctc_and_condition_blocks(monkeypatch, tmp_path):
    """T32: Cùng một file, đọc VCSH ở khối BCTC và khối điều kiện -> Hai
    khối ra cùng một số, cùng một năm."""
    resp = _assess(monkeypatch, tmp_path, "t32", _alpha_group_workbook())
    body = resp.json()
    vcsh_bctc = body["financial_inputs"]["equity_vnd"]
    vcsh_overview = next(r for r in body["overview"] if r["condition_name"] == "Vốn chủ sở hữu")["observed"]["value"]
    assert vcsh_bctc == vcsh_overview == 580_965_107_518.0


def test_t33_force_cannot_bypass_data_mismatch_block(monkeypatch, tmp_path):
    """T33: consistency.khop = false, gọi xuất tờ trình với force=true ->
    Vẫn chặn. loai_chan = LECH_DU_LIEU, cho_phep_ghi_de = false, không sinh file."""
    monkeypatch.setenv("DB_PATH", str(tmp_path / "t33.db"))
    monkeypatch.setenv("CASE_FILES_DIR", str(tmp_path / "t33_files"))
    from app.config import get_settings
    get_settings.cache_clear()
    monkeypatch.setattr(eb_router, "generate_narrative", lambda computed: {"why": [], "credit_memo": ""})

    client = TestClient(app)
    computed = {
        "customer_profile": {"customer_name": "ALPHA GROUP"},
        "financial_inputs": {"equity_vnd": 580965107518.0},
        "credit_engine": {"dscr": {"value": None, "status": "NEED_MORE_DATA"}, "icr": {"value": None, "status": "NEED_MORE_DATA"}},
        "risk_flags": [], "ho_so_period": {"selected": "2025"},
        "consistency": {"khop": False, "danh_sach_lech": [{"chi_tieu": "Vốn chủ sở hữu", "gia_tri": [580965107518.0, 999999999999.0]}]},
    }
    resp = client.post("/api/eb/export", json={"computed": computed, "force": True})
    assert resp.status_code == 409
    body = resp.json()
    assert body["loai_chan"] == "LECH_DU_LIEU"
    assert body["block_type"] == "HARD"
