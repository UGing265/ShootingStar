import json

import pytest

from shootingstar.adapters.model_api.gemini_adapter import GeminiModelAdapter


def _envelope(model_text: str) -> str:
    return json.dumps({"candidates": [{"content": {"parts": [{"text": model_text}]}}], "usageMetadata": {}})


def test_model_text_with_raw_newline_in_string_parses_and_malformed_still_fails():
    adapter = GeminiModelAdapter(key_manager=object(), model_name="m")

    # Gemini can emit a literal newline/tab inside a JSON string value.
    parsed = adapter._parse_gemini_response(_envelope('{"summary": "line1\nline2\tend"}'), key_index=0)
    assert parsed["summary"] == "line1\nline2\tend"

    # Truncated JSON must still be rejected.
    with pytest.raises(json.JSONDecodeError):
        adapter._parse_gemini_response(_envelope('{"summary": "cut'), key_index=0)
