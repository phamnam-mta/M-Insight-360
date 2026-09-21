import json

import httpx

from app.agents.rb import narrative


def test_generate_narrative_parses_structured_json_response(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    from app.config import get_settings

    get_settings.cache_clear()

    llm_payload = {"why": ["Hồ sơ đủ điều kiện", "DTI trong ngưỡng an toàn"], "credit_memo": "Tóm tắt hồ sơ..."}

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.read())
        assert body["model"] == "z-ai/glm-5.2-hackathon"
        return httpx.Response(
            200, json={"choices": [{"message": {"content": json.dumps(llm_payload, ensure_ascii=False)}}]}
        )

    monkeypatch.setattr(narrative, "_client", httpx.Client(transport=httpx.MockTransport(handler)))

    result = narrative.generate_narrative({"credit_readiness": "READY", "recommendation": "PROCEED_FOR_HUMAN_REVIEW"})
    assert result["why"] == llm_payload["why"]
    assert result["credit_memo"] == llm_payload["credit_memo"]


def test_generate_narrative_degrades_gracefully_on_failure(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    from app.config import get_settings

    get_settings.cache_clear()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    monkeypatch.setattr(narrative, "_client", httpx.Client(transport=httpx.MockTransport(handler)))

    result = narrative.generate_narrative({"credit_readiness": "READY"})
    assert result["why"] == []
    assert "không thể sinh" in result["credit_memo"].lower() or result["credit_memo"] == ""


def test_generate_narrative_degrades_gracefully_on_malformed_json(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    from app.config import get_settings

    get_settings.cache_clear()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": "not json at all"}}]})

    monkeypatch.setattr(narrative, "_client", httpx.Client(transport=httpx.MockTransport(handler)))

    result = narrative.generate_narrative({"credit_readiness": "READY"})
    assert result["why"] == []
    assert result["credit_memo"] == "not json at all"


def test_generate_narrative_degrades_gracefully_on_timeout(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    from app.config import get_settings

    get_settings.cache_clear()

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out")

    monkeypatch.setattr(narrative, "_client", httpx.Client(transport=httpx.MockTransport(handler)))

    result = narrative.generate_narrative({"credit_readiness": "READY"})
    assert result["why"] == []
    assert isinstance(result["credit_memo"], str)


def test_generate_narrative_never_overwrites_numeric_fields(monkeypatch):
    # Layer 3 must only ever return why/credit_memo - it cannot alter any computed field.
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    from app.config import get_settings

    get_settings.cache_clear()

    llm_payload = {
        "why": ["ok"],
        "credit_memo": "memo",
        "credit_engine": {"dti": {"value": 0.0}},
        "credit_readiness": "READY",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"choices": [{"message": {"content": json.dumps(llm_payload)}}]}
        )

    monkeypatch.setattr(narrative, "_client", httpx.Client(transport=httpx.MockTransport(handler)))

    result = narrative.generate_narrative({"credit_engine": {"dti": {"value": 0.99}}})
    assert set(result.keys()) == {"why", "credit_memo"}
