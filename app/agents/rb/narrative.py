import json

import httpx

from app.config import get_settings

SYSTEM_PROMPT = (
    "Bạn là Trợ lý AI Thẩm định Tín dụng Khối Bán lẻ của MSB CreditPilot. "
    "Bạn CHỈ được viết nhận xét dựa trên dữ liệu JSON đã được tính toán sẵn dưới đây — "
    "KHÔNG được tự tính hoặc thay đổi bất kỳ con số nào, KHÔNG được kết luận chứng từ "
    "là giả mạo/gian lận (mọi nghi vấn phải là 'cần xác minh thủ công'). "
    "Trả lời DUY NHẤT bằng một JSON hợp lệ, không kèm giải thích, đúng schema: "
    '{"why": ["..."], "credit_memo": "..."}. '
    "why là danh sách gạch đầu dòng ngắn gọn giải thích vì sao đưa ra khuyến nghị. "
    "credit_memo là đoạn văn tóm tắt dự thảo tờ trình, kết thúc bằng câu: "
    '"Đánh giá này được tạo nhằm hỗ trợ RM/Credit Officer xem xét hồ sơ. '
    'Không phải quyết định phê duyệt hoặc từ chối tín dụng tự động."'
)

_DEGRADED_MEMO = "Không thể sinh nhận xét AI cho hồ sơ này vào lúc này — vui lòng xem các số liệu đã tính toán bên trên."

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
    except (httpx.HTTPError, KeyError, IndexError, ValueError):
        return {"why": [], "credit_memo": _DEGRADED_MEMO}

    try:
        parsed = json.loads(content)
        # Layer 3 may only ever supply narrative text — even if the LLM includes
        # other keys in its JSON (e.g. echoing back a "credit_engine" object),
        # only why/credit_memo are ever taken from it.
        return {"why": parsed.get("why", []), "credit_memo": parsed.get("credit_memo", "")}
    except json.JSONDecodeError:
        return {"why": [], "credit_memo": content}
