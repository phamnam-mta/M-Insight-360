import zipfile

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
