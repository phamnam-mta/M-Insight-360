from app.engine.core.llm_json import strip_markdown_json_fence


def test_strip_markdown_json_fence_with_json_label():
    content = '```json\n{"why": ["a"], "credit_memo": "b"}\n```'
    assert strip_markdown_json_fence(content) == '{"why": ["a"], "credit_memo": "b"}'


def test_strip_markdown_json_fence_without_language_label():
    content = '```\n{"why": [], "credit_memo": "x"}\n```'
    assert strip_markdown_json_fence(content) == '{"why": [], "credit_memo": "x"}'


def test_strip_markdown_json_fence_leaves_plain_json_untouched():
    content = '{"why": [], "credit_memo": "x"}'
    assert strip_markdown_json_fence(content) == '{"why": [], "credit_memo": "x"}'


def test_strip_markdown_json_fence_leaves_non_json_text_untouched():
    content = "not json at all"
    assert strip_markdown_json_fence(content) == "not json at all"


def test_strip_markdown_json_fence_handles_surrounding_whitespace():
    content = '  \n```json\n{"a": 1}\n```\n  '
    assert strip_markdown_json_fence(content) == '{"a": 1}'
