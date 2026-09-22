import io

import docx

from app.agents.eb.mb02_export import build_mb02_docx


def test_export_produces_openable_docx_with_disclaimer():
    computed = {
        "customer_profile": {"customer_name": "CONG TY TNHH TEST", "tax_id": "0100000001"},
        "credit_engine": {"nwc": {"metric": "nwc", "value": -500000000, "status": "OK"}},
        "risk_flags": [{"rule_id": "RF01", "rule_name": "Mất cân đối vốn", "status": "KÍCH HOẠT", "severity": "HIGH"}],
        "missing_data": ["FINANCIAL_STATEMENT"],
        "recommendation": "ADDITIONAL_DOCUMENTS_REQUIRED",
        "why": ["Thiếu BCTC kỳ gần nhất"],
        "credit_memo": "Tóm tắt hồ sơ...",
    }
    raw = build_mb02_docx(computed)
    doc = docx.Document(io.BytesIO(raw))
    full_text = "\n".join(p.text for p in doc.paragraphs)
    assert "CONG TY TNHH TEST" in full_text
    assert "RF01" in full_text
    assert "không phải quyết định phê duyệt" in full_text.lower()


def test_export_handles_missing_optional_fields_without_crashing():
    raw = build_mb02_docx({"customer_profile": {"customer_name": "X", "tax_id": "Y"}})
    doc = docx.Document(io.BytesIO(raw))
    assert len(doc.paragraphs) > 0


def test_export_does_not_fabricate_missing_metrics():
    # Metrics with status NEED_MORE_DATA must show as such, never a fabricated number.
    computed = {
        "customer_profile": {"customer_name": "X", "tax_id": "Y"},
        "credit_engine": {"nwc": {"metric": "nwc", "value": None, "status": "NEED_MORE_DATA"}},
    }
    raw = build_mb02_docx(computed)
    doc = docx.Document(io.BytesIO(raw))
    full_text = "\n".join(p.text for p in doc.paragraphs)
    assert "NEED_MORE_DATA" in full_text or "chưa đủ dữ liệu" in full_text.lower()


def test_export_handles_completely_empty_computed_dict():
    raw = build_mb02_docx({})
    doc = docx.Document(io.BytesIO(raw))
    assert len(doc.paragraphs) > 0


def test_docx_overview_section_matches_json_values():
    computed = {
        "customer_profile": {"customer_name": "CONG TY TNHH TEST", "tax_id": "0100000001"},
        "credit_engine": {}, "risk_flags": [], "missing_data": [],
        "recommendation": "PROCEED_FOR_HUMAN_REVIEW", "why": [], "credit_memo": "",
        "overview": [
            {
                "condition_id": "C08", "condition_name": "Vốn chủ sở hữu",
                "observed": {"value": 500000000.0, "status": "COMPUTED"},
                "compare_rule": "> 0", "result": "PASS", "reason_if_incomplete": None,
            },
            {
                "condition_id": "C11", "condition_name": "Lịch sử quan hệ tín dụng",
                "observed": {"value": None, "status": "MISSING_DATA"},
                "compare_rule": "...", "result": "PENDING_INTERNAL_CHECK",
                "reason_if_incomplete": "Cần dữ liệu CIC.",
            },
        ],
    }
    docx_bytes = build_mb02_docx(computed)
    doc = docx.Document(io.BytesIO(docx_bytes))
    full_text = "\n".join(p.text for p in doc.paragraphs)
    assert "Vốn chủ sở hữu" in full_text
    assert "500000000.0" in full_text
    assert "PASS" in full_text
    assert "Lịch sử quan hệ tín dụng" in full_text
    assert "Cần dữ liệu CIC." in full_text


def test_export_includes_stress_scenario_section_when_provided():
    scenario = {
        "name": "Thận trọng",
        "request": {"deltas": {"revenue_pct": -10, "ebit_pct": -15, "interest_pct": 15}},
        "response": {"before": {"dscr": {"value": 1.3}}, "after": {"dscr": {"value": 0.95}}},
    }
    docx_bytes = build_mb02_docx({"customer_profile": {"customer_name": "X", "tax_id": "1"}}, stress_scenario=scenario)
    document = docx.Document(io.BytesIO(docx_bytes))
    full_text = "\n".join(p.text for p in document.paragraphs)
    assert "Thận trọng" in full_text
    assert "0.95" in full_text


def test_export_without_stress_scenario_is_unaffected():
    docx_bytes = build_mb02_docx({"customer_profile": {"customer_name": "X", "tax_id": "1"}})
    assert len(docx_bytes) > 0
