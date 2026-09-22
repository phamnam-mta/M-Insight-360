import json

import httpx

from app.config import get_settings
from app.engine.core.llm_json import strip_markdown_json_fence

SYSTEM_PROMPT = (
    "Bạn là Trợ lý AI Thẩm định Tín dụng Khối Doanh nghiệp SME của MSB. "
    "Bạn CHỈ được viết nhận xét dựa trên dữ liệu JSON đã tính toán sẵn — KHÔNG được tự tính "
    "hoặc thay đổi bất kỳ con số hay red-flag nào. Trả lời DUY NHẤT bằng JSON hợp lệ đúng schema: "
    '{"why": ["..."], "credit_memo": "..."}. '
    "credit_memo kết thúc bằng: \"Agent chỉ chuẩn bị hồ sơ và kiến nghị để cán bộ có thẩm quyền "
    "xem xét; không tự phê duyệt, cam kết cấp hạn mức hoặc thay thế kết luận thẩm định của MSB.\""
)

_client = httpx.Client(timeout=300.0)


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
        parsed = json.loads(strip_markdown_json_fence(content))
        return {"why": parsed.get("why", []), "credit_memo": parsed.get("credit_memo", "")}
    except json.JSONDecodeError:
        return {"why": [], "credit_memo": content}
