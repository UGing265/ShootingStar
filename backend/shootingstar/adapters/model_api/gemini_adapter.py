"""Gemini forecast adapter: one structured generation per forecast."""

import json

from shootingstar.adapters.model_api.gemini_transport import (
    GeminiAPIError, GeminiAuthError, GeminiQuotaExceededError, GeminiTimeoutError, GeminiTransport,
)
from shootingstar.adapters.model_api.prompts.forecast_6h_prompt import RESPONSE_SCHEMA, build_prompt


class GeminiModelAdapter:
    def __init__(self, key_manager=None, model_name=None, timeout_seconds=None):
        self.transport = GeminiTransport(key_manager, model_name, timeout_seconds)
        self.model_name = self.transport.model_name

    def forecast(self, digest, horizon_minutes, purchase_price):
        body = {
            "contents": [{"parts": [{"text": build_prompt(digest, horizon_minutes, purchase_price)}]}],
            "generationConfig": {"temperature": 0.1, "response_mime_type": "application/json",
                                 "responseSchema": RESPONSE_SCHEMA},
        }
        data, slot = self.transport.send(body)
        try:
            answer = self._parse_gemini_response(data, slot)
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise GeminiAPIError("Gemini returned an invalid forecast response") from error
        usage = data.get("usageMetadata", {})
        return answer, {"key_index": slot, "prompt_tokens": usage.get("promptTokenCount"),
                        "completion_tokens": usage.get("candidatesTokenCount"),
                        "total_tokens": usage.get("totalTokenCount")}

    def _parse_gemini_response(self, response_body, key_index):
        """Decode provider JSON, including literal control characters in model text."""
        data = json.loads(response_body) if isinstance(response_body, str) else response_body
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(text, strict=False)
