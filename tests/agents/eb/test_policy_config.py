from app.agents.eb.policy_config import POLICY_CONFIG, PolicyThreshold


def test_demo_threshold_renders_demo_label():
    t = PolicyThreshold(20_000_000_000)
    assert t.is_demo is True
    assert t.policy_version_label == "Ngưỡng demo – chờ nghiệp vụ xác nhận"


def test_confirmed_threshold_renders_doc_code_label():
    t = PolicyThreshold(20_000_000_000, doc_code="QĐ.EB.012", version="1.0", effective_date="2026-01-01", is_demo=False)
    assert "QĐ.EB.012" in t.policy_version_label
    assert "2026-01-01" in t.policy_version_label


def test_revenue_thresholds_are_registered():
    assert POLICY_CONFIG["REVENUE_12M_MIN_VND"].value == 20_000_000_000
    assert POLICY_CONFIG["REVENUE_12M_MAX_VND"].value == 1_000_000_000_000


def test_top_partners_threshold_carries_open_question():
    t = POLICY_CONFIG["TOP_PARTNERS_COUNT"]
    assert t.value == 5
    assert t.open_question is not None
    assert "đầu ra" in t.open_question or "đầu vào" in t.open_question
