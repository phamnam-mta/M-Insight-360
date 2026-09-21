import base64

import httpx

from ..config import get_settings

OCR_PROMPT = (
    "Đây là một trang tài liệu ngân hàng/tài chính dạng ảnh (đã scan). "
    "Hãy trích xuất TOÀN BỘ nội dung văn bản nhìn thấy được trên ảnh này, "
    "giữ nguyên số liệu, không suy diễn hay bổ sung thông tin không có trên ảnh. "
    "Nếu chữ mờ không đọc được, ghi [KHÔNG ĐỌC ĐƯỢC] tại vị trí đó."
)

# Module-level client so tests can monkeypatch the transport.
_client = httpx.Client(timeout=60.0)


def ocr_image(image_bytes: bytes, model: str | None = None) -> str:
    settings = get_settings()
    model = model or settings.ocr_vision_model
    b64 = base64.b64encode(image_bytes).decode()

    response = _client.post(
        f"{settings.llm_base_url}/chat/completions",
        headers={"Authorization": f"Bearer {settings.llm_api_key}"},
        json={
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": OCR_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{b64}"},
                        },
                    ],
                }
            ],
            "max_tokens": 4096,
        },
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]
