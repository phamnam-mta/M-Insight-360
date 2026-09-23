import io
from dataclasses import asdict

import docx

from app.agents.eb.mb02_export import build_mb02_docx
from app.engine.core.types import RuleResult

from .fixtures.alpha_group_demo import ALPHA_GROUP_2025


def _computed_for_alpha_group(**overrides):
    computed = {
        "customer_profile": {"customer_name": "CÔNG TY CỔ PHẦN ĐẦU TƯ ALPHA GROUP", "tax_id": "0000000000"},
        "financial_inputs": {k: v for k, v in asdict(ALPHA_GROUP_2025).items() if v is not None},
        "credit_engine": {}, "risk_flags": [],
        "ho_so_period": {"selected": "2025"},
        "export_gate": {"verdict": "XUAT_KEM_CANH_BAO", "block_type": None, "signal_count": 0, "signals": [], "data_warnings": [], "reasons": []},
    }
    computed.update(overrides)
    return computed


def test_t11_and_t12_alpha_group_export_matches_trieu_dong_values():
    docx_bytes, _ = build_mb02_docx(_computed_for_alpha_group())
    doc = docx.Document(io.BytesIO(docx_bytes))
    table31 = next(t for t in doc.tables if t.rows[0].cells[0].text.strip() == "Chỉ tiêu" and len(t.rows) == 14)
    nwc_row = next(r for r in table31.rows if "Tổng doanh thu" in r.cells[0].text)
    assert nwc_row.cells[3].text.strip() == "90.106"  # net_revenue_vnd / 1e6, rounded


def test_t13_missing_field_is_placeholder():
    computed = _computed_for_alpha_group()
    computed["financial_inputs"].pop("pat_vnd", None)
    docx_bytes, _ = build_mb02_docx(computed)
    doc = docx.Document(io.BytesIO(docx_bytes))
    table31 = next(t for t in doc.tables if t.rows[0].cells[0].text.strip() == "Chỉ tiêu" and len(t.rows) == 14)
    row = next(r for r in table31.rows if "Lợi nhuận sau thuế" in r.cells[0].text)
    assert row.cells[3].text.strip() == "[Chưa xác định từ hồ sơ tải lên]"


def test_t14_legal_checkboxes_never_ticked():
    docx_bytes, _ = build_mb02_docx(_computed_for_alpha_group())
    doc = docx.Document(io.BytesIO(docx_bytes))
    row = next(r for r in doc.tables[2].rows if r.cells[0].text.strip() == "Tình trạng khách hàng")
    assert row.cells[1].text.strip() == "KH mới       KH hiện hữu"


def test_t15_prior_period_columns_never_borrow_selected_period():
    docx_bytes, _ = build_mb02_docx(_computed_for_alpha_group())
    doc = docx.Document(io.BytesIO(docx_bytes))
    table31 = next(t for t in doc.tables if t.rows[0].cells[0].text.strip() == "Chỉ tiêu" and len(t.rows) == 14)
    row = next(r for r in table31.rows if "Tổng doanh thu" in r.cells[0].text)
    assert row.cells[1].text.strip() == "[Chưa xác định từ hồ sơ tải lên]"
    assert row.cells[2].text.strip() == "[Chưa xác định từ hồ sơ tải lên]"


def test_t17_no_technical_values_leak_into_docx():
    docx_bytes, _ = build_mb02_docx(_computed_for_alpha_group())
    doc = docx.Document(io.BytesIO(docx_bytes))
    full_text = "\n".join(p.text for p in doc.paragraphs) + "\n".join(
        c.text for t in doc.tables for r in t.rows for c in r.cells
    )
    for banned in ("NaN", "Infinity", "None", "undefined", "#DIV/0!"):
        assert banned not in full_text


def test_t18_alpha_group_unknown_dscr_icr_does_not_block():
    from app.agents.eb.export_gate import evaluate_export_gate
    from app.engine.core.types import Metric
    dscr = Metric.need_more_data("dscr", "x")
    icr = Metric(metric="icr", value=1.00, formula="x", input_values={}, input_sources={})
    result = evaluate_export_gate([], equity_vnd=ALPHA_GROUP_2025.equity_vnd, dscr=dscr, icr=icr)
    assert result.verdict in ("XUAT", "XUAT_KEM_CANH_BAO")


def test_t19_five_signals_blocks_and_names_them():
    from app.agents.eb.export_gate import evaluate_export_gate
    from app.engine.core.types import Metric
    flags = [
        RuleResult(rule_id="RF05", rule_name="DSCR yếu", status="KÍCH HOẠT", observed_value=0.62),
        RuleResult(rule_id="RF09", rule_name="ICR yếu", status="KÍCH HOẠT", observed_value=0.75),
        RuleResult(rule_id="RF01", rule_name="Mất cân đối vốn", status="KÍCH HOẠT"),
        RuleResult(rule_id="RF08", rule_name="Đòn bẩy", status="KÍCH HOẠT", observed_value=3.0),
        RuleResult(rule_id="RF06", rule_name="Phải thu/tồn kho", status="KÍCH HOẠT", observed_value=0.85),
    ]
    result = evaluate_export_gate(
        flags, equity_vnd=1000,
        dscr=Metric(metric="dscr", value=0.62, formula="x", input_values={}, input_sources={}),
        icr=Metric(metric="icr", value=0.75, formula="x", input_values={}, input_sources={}),
    )
    assert result.verdict == "KHONG_XUAT_TU_DONG"
    assert result.signal_count == 5
    assert len(result.signals) == 5


def test_t20_force_still_exports_with_banner_and_log():
    computed = _computed_for_alpha_group(export_gate={
        "verdict": "KHONG_XUAT_TU_DONG", "block_type": "SOFT", "signal_count": 5,
        "signals": [{"rule_id": "RF05", "rule_name": "DSCR yếu", "status": "KÍCH HOẠT", "observed_value": 0.62}],
        "data_warnings": [], "reasons": [],
    })
    docx_bytes, fill_log = build_mb02_docx(computed, force=True, actor="rm.test")
    doc = docx.Document(io.BytesIO(docx_bytes))
    assert "BẢN NHÁP XUẤT THEO YÊU CẦU CỦA CÁN BỘ" in doc.paragraphs[0].text
    assert fill_log["xuat_theo_force"] is True


def test_t21_s8_field_keeps_template_ellipsis():
    docx_bytes, _ = build_mb02_docx(_computed_for_alpha_group())
    doc = docx.Document(io.BytesIO(docx_bytes))
    row = next(r for r in doc.tables[2].rows if r.cells[0].text.strip() == "Đăng ký kinh doanh")
    assert "……" in row.cells[1].text
