import httpx
import pytest

from app.extraction import ocr_vision


def _mock_transport(expected_model: str, response_text: str) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        body = request.read()
        import json

        payload = json.loads(body)
        assert payload["model"] == expected_model
        assert payload["messages"][0]["content"][1]["type"] == "image_url"
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": response_text}}]},
        )

    return httpx.MockTransport(handler)


def test_ocr_image_returns_model_text(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    from app.config import get_settings

    get_settings.cache_clear()

    transport = _mock_transport("qwen/qwen3.6-flash", "Doanh thu: 500 trieu")
    monkeypatch.setattr(ocr_vision, "_client", httpx.Client(transport=transport))

    result = ocr_vision.ocr_image(b"\x89PNG\r\n\x1a\nfakepngbytes")
    assert result == "Doanh thu: 500 trieu"


def test_ocr_image_raises_on_http_error(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    from app.config import get_settings

    get_settings.cache_clear()

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    monkeypatch.setattr(ocr_vision, "_client", httpx.Client(transport=httpx.MockTransport(handler)))

    with pytest.raises(httpx.HTTPStatusError):
        ocr_vision.ocr_image(b"fakebytes")
