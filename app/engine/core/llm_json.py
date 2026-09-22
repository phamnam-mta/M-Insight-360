import re

# LLMs are instructed to reply with raw JSON only, but some still wrap the
# response in a markdown code fence (```json ... ``` or ``` ... ```) even
# when told not to. json.loads() rejects that wrapper outright, so a
# perfectly valid narrative response was falling into the "malformed JSON"
# degradation path — why=[] and the raw fenced text dumped into credit_memo.
_FENCE_RE = re.compile(r"^```(?:json)?\s*\n?(.*?)\n?```$", re.DOTALL)


def strip_markdown_json_fence(content: str) -> str:
    stripped = content.strip()
    match = _FENCE_RE.match(stripped)
    return match.group(1).strip() if match else stripped
