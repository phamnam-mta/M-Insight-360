import json

import httpx

from app.config import get_settings

SYSTEM_PROMPT = (
    "Bạn là Chuyên gia Phân tích Dữ liệu & Bán chéo (Cross-sell) tại MSB. "
    "Bạn CHỈ được viết nhận xét/kịch bản tiếp cận dựa trên dữ liệu JSON đã tính toán sẵn — "
    "KHÔNG được tự bịa số liệu, KHÔNG đề xuất sản phẩm nếu không có tín hiệu giao dịch tương ứng. "
    "Trả lời DUY NHẤT bằng JSON hợp lệ đúng schema: {\"why\": [\"...\"], \"credit_memo\": \"...\"}. "
    "credit_memo là kịch bản tiếp cận khách hàng, tuân thủ TƯỜNG LỬA DỮ LIỆU (không nêu số liệu "
    "riêng của khách hàng khác)."
)

_client = httpx.Client(timeout=60.0)


def generate_narrative(computed: dict) -> dict:
    settings = get_settings()
    try:
        response = _client.post(
            f"{settings.llm_base_url}/chat/completions",
            headers={"Authorization": f"Bearer {settings.llm_api_key}"},
            json={
                "model": settings.narrative_model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps(computed, ensure_ascii=False)},
                ],
                "max_tokens": 2000,
            },
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
    except (httpx.HTTPError, KeyError, IndexError):
        return {"why": [], "credit_memo": ""}

    try:
        parsed = json.loads(content)
        return {"why": parsed.get("why", []), "credit_memo": parsed.get("credit_memo", "")}
    except json.JSONDecodeError:
        return {"why": [], "credit_memo": content}
