import zipfile

import docx

from app.agents.eb.mb02_export import (
    _MISSING_PLACEHOLDER, _format_number_vn, build_mb02_docx,
)


def test_format_number_vn_uses_vietnamese_separators():
    assert _format_number_vn(128_061_897.6, 0) == "128.061.898"
    assert _format_number_vn(0.14, 2) == "0,14"


def test_format_number_vn_none_is_missing_placeholder():
    assert _format_number_vn(None, 0) == _MISSING_PLACEHOLDER


def test_build_mb02_docx_returns_valid_docx_bytes_and_fill_log():
    computed = {
        "customer_profile": {"customer_name": "ACME", "tax_id": "0101234567"},
        "financial_inputs": {}, "credit_engine": {}, "risk_flags": [],
        "export_gate": {"verdict": "XUAT", "block_type": None, "signal_count": 0, "signals": [], "data_warnings": [], "reasons": []},
    }
    docx_bytes, fill_log = build_mb02_docx(computed)
    assert docx_bytes[:2] == b"PK"  # a .docx is a zip archive
    with zipfile.ZipFile(__import__("io").BytesIO(docx_bytes)) as zf:
        assert "word/document.xml" in zf.namelist()
    assert "verdict" in fill_log
    assert isinstance(fill_log["cells"], list)


def _make_computed(**financial_inputs_overrides):
    financial_inputs = {
        "net_revenue_vnd": 128_061_897_765.0, "pbt_vnd": 12_160_680_287.0,
        "pat_vnd": 9_000_000_000.0, "interest_expense_vnd": 12_131_595_580.0,
        "equity_vnd": 100_000_000_000.0, "current_assets_vnd": 200_000_000_000.0,
        "non_current_assets_vnd": 50_000_000_000.0, "short_term_debt_vnd": 78_810_636_239.0,
        "long_term_debt_vnd": 0.0, "charter_capital_vnd": 50_000_000_000.0,
        **financial_inputs_overrides,
    }
    return {
        "customer_profile": {"customer_name": "CÔNG TY ACME", "tax_id": "0101234567"},
        "financial_inputs": financial_inputs,
        "credit_engine": {
            "current_ratio": {"value": 2.5, "status": "OK"},
            "total_borrowings": {"value": 78_810_636_239.0, "status": "OK"},
        },
        "risk_flags": [],
        "export_gate": {"verdict": "XUAT", "block_type": None, "signal_count": 0, "signals": [], "data_warnings": [], "reasons": []},
    }


def _reload(docx_bytes):
    return docx.Document(__import__("io").BytesIO(docx_bytes))


def test_s2_1_fills_customer_name():
    docx_bytes, _ = build_mb02_docx(_make_computed())
    doc = _reload(docx_bytes)
    row = next(r for r in doc.tables[2].rows if "Tên Doanh nghiệp" in r.cells[0].text)
    assert "CÔNG TY ACME" in row.cells[1].text


def test_s2_2_fills_revenue_in_nam_n_column():
    docx_bytes, _ = build_mb02_docx(_make_computed())
    doc = _reload(docx_bytes)
    table31 = next(t for t in doc.tables if t.rows[0].cells[0].text.strip() == "Chỉ tiêu" and len(t.rows) == 14)
    row = next(r for r in table31.rows if "Tổng doanh thu" in r.cells[0].text)
    assert row.cells[3].text.strip() == "128.062"  # triệu đồng, rounded
    assert row.cells[1].text.strip() == "[Chưa xác định từ hồ sơ tải lên]"  # Năm N-2 never borrowed


def test_s2_2_leverage_ratio_two_decimals():
    docx_bytes, _ = build_mb02_docx(_make_computed())
    doc = _reload(docx_bytes)
    table31 = next(t for t in doc.tables if t.rows[0].cells[0].text.strip() == "Chỉ tiêu" and len(t.rows) == 14)
    row = next(r for r in table31.rows if "Hệ số đòn bẩy" in r.cells[0].text)
    assert row.cells[3].text.strip() == "0,79"  # 78.8bn / 100bn


def test_s2_2_missing_field_is_placeholder_not_zero():
    computed = _make_computed(pat_vnd=None)
    docx_bytes, _ = build_mb02_docx(computed)
    doc = _reload(docx_bytes)
    table31 = next(t for t in doc.tables if t.rows[0].cells[0].text.strip() == "Chỉ tiêu" and len(t.rows) == 14)
    row = next(r for r in table31.rows if "Lợi nhuận sau thuế" in r.cells[0].text)
    assert row.cells[3].text.strip() == "[Chưa xác định từ hồ sơ tải lên]"
