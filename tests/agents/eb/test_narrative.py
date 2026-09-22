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


def test_generate_narrative_parses_json_wrapped_in_markdown_fence(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    from app.config import get_settings

    get_settings.cache_clear()

    llm_payload = {"why": ["Không phát hiện cờ đỏ"], "credit_memo": "Tóm tắt..."}
    fenced_content = "```json\n" + json.dumps(llm_payload, ensure_ascii=False) + "\n```"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": fenced_content}}]})

    monkeypatch.setattr(narrative, "_client", httpx.Client(transport=httpx.MockTransport(handler)))
    result = narrative.generate_narrative({"risk_flags": []})
    assert result["why"] == llm_payload["why"]
    assert result["credit_memo"] == llm_payload["credit_memo"]


def test_system_prompt_requires_five_part_structure_and_id_citation():
    for phrase in ("Phát hiện", "Số liệu và nguồn", "Ý nghĩa tín dụng", "Điều chưa chắc chắn", "Việc cán bộ cần làm"):
        assert phrase in narrative.SYSTEM_PROMPT
    assert "field_id" in narrative.SYSTEM_PROMPT or "condition_id" in narrative.SYSTEM_PROMPT


def test_generate_narrative_parses_five_part_why_entry(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    from app.config import get_settings

    get_settings.cache_clear()

    entry = (
        "Phát hiện: NWC âm | Số liệu và nguồn: NWC = -500.000.000 (field_id=nwc) | "
        "Ý nghĩa tín dụng: rủi ro thanh khoản ngắn hạn | Điều chưa chắc chắn: chưa rõ nguyên nhân | "
        "Việc cán bộ cần làm: yêu cầu giải trình"
    )
    payload = {"why": [entry], "credit_memo": "Tóm tắt..."}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(payload, ensure_ascii=False)}}]})

    monkeypatch.setattr(narrative, "_client", httpx.Client(transport=httpx.MockTransport(handler)))
    result = narrative.generate_narrative({"risk_flags": []})
    assert result["why"][0].startswith("Phát hiện:")
    assert "field_id=nwc" in result["why"][0]
