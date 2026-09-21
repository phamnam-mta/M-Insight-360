import json

import httpx

from app.agents.eb import narrative


def test_generate_narrative_parses_structured_response(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    from app.config import get_settings

    get_settings.cache_clear()

    payload = {"why": ["NWC âm cần lưu ý"], "credit_memo": "Tóm tắt EB..."}

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.read())
        assert body["model"] == "z-ai/glm-5.2-hackathon"
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(payload, ensure_ascii=False)}}]})

    monkeypatch.setattr(narrative, "_client", httpx.Client(transport=httpx.MockTransport(handler)))

    result = narrative.generate_narrative({"risk_flags": []})
    assert result == payload


def test_generate_narrative_degrades_on_error(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    from app.config import get_settings

    get_settings.cache_clear()

    monkeypatch.setattr(
        narrative, "_client", httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(500)))
    )
    result = narrative.generate_narrative({"risk_flags": []})
    assert result["why"] == []


def test_generate_narrative_degrades_on_malformed_json(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    from app.config import get_settings

    get_settings.cache_clear()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": "not json at all"}}]})

    monkeypatch.setattr(narrative, "_client", httpx.Client(transport=httpx.MockTransport(handler)))
    result = narrative.generate_narrative({"risk_flags": []})
    assert result["why"] == []
    assert result["credit_memo"] == "not json at all"
