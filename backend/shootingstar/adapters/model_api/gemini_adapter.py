"""Gemini API model adapter with structured output parsing and quota discipline."""

import json
import logging
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional
from shootingstar.adapters.model_api.key_manager import GeminiKeyManager, KeySlot, mask_secret

logger = logging.getLogger(__name__)


class GeminiAPIError(Exception):
    """Base error for Gemini API interactions."""
    pass


class GeminiQuotaExceededError(GeminiAPIError):
    """HTTP 429 Rate limit / Project quota exhausted."""
    pass


class GeminiAuthError(GeminiAPIError):
    """HTTP 401 or 403 Invalid or revoked API key."""
    pass


class GeminiModelAdapter:
    """Adapter for Google Gemini models enforcing structured outputs and quota safety."""

    DEFAULT_MODEL = "gemini-2.5-flash"
    API_URL_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"

    def __init__(
        self,
        key_manager: Optional[GeminiKeyManager] = None,
        model_name: str = DEFAULT_MODEL,
        timeout_seconds: float = 30.0,
    ):
        self.key_manager = key_manager or GeminiKeyManager()
        self.model_name = model_name
        self.timeout_seconds = timeout_seconds

    def analyze(
        self,
        context_payload: Dict[str, Any],
        approved_lessons: Optional[List[Dict[str, Any]]] = None,
        prompt_version: str = "v1",
        mock_mode: bool = False,
        mock_response: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Sends context to Gemini and receives structured directional analysis."""
        if mock_mode:
            return self._generate_mock_response(context_payload, mock_response)

        max_attempts = max(1, self.key_manager.total_slots)
        last_error: Optional[Exception] = None

        for _ in range(max_attempts):
            slot = self.key_manager.get_next_slot()
            if not slot:
                if last_error:
                    raise last_error
                raise GeminiQuotaExceededError(
                    "No available Gemini API key slots (all keys inactive or in cooldown). Please wait."
                )

            url = self.API_URL_TEMPLATE.format(model=self.model_name, key=slot.api_key)
            prompt_text = self._build_prompt_text(context_payload, approved_lessons)
            request_body = {
                "contents": [
                    {
                        "parts": [
                            {"text": prompt_text}
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.1,
                    "response_mime_type": "application/json",
                },
            }

            data_bytes = json.dumps(request_body).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data_bytes,
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            try:
                with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                    status_code = resp.getcode()
                    body = resp.read().decode("utf-8")
                    return self._parse_gemini_response(body, slot.index)

            except urllib.error.HTTPError as e:
                if e.code in (401, 403):
                    self.key_manager.record_401_403(slot.index, str(e))
                    last_error = GeminiAuthError(f"Gemini API key in slot #{slot.index} is invalid or unauthorized: {e}")
                    continue
                elif e.code == 429:
                    self.key_manager.record_429_quota_exhausted(slot.index)
                    last_error = GeminiQuotaExceededError(
                        f"Gemini project '{slot.project_id}' rate limit reached (HTTP 429). Placed on cooldown."
                    )
                    logger.info("Project '%s' hit 429; rotating to next available non-cooling project if any.", slot.project_id)
                    continue
                else:
                    raise GeminiAPIError(f"Gemini API HTTP {e.code} error: {e}")
            except urllib.error.URLError as e:
                raise GeminiAPIError(f"Network error connecting to Gemini API: {e}")

        if last_error:
            raise last_error
        raise GeminiQuotaExceededError("Exhausted all available Gemini slots due to rate limiting.")
    def _build_prompt_text(
        self,
        context_payload: Dict[str, Any],
        approved_lessons: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Constructs strictly bounded system prompt with JSON response schema instruction."""
        schema_instruction = (
            "You are an evidence-based financial quantitative assistant analyzing Bitcoin spot data.\n"
            "Predict whether the price 30 minutes after cutoff time will be UP, DOWN, or ABSTAIN relative to the target purchase price.\n\n"
            "CRITICAL INSTRUCTIONS:\n"
            "1. Output MUST be valid JSON adhering strictly to this schema:\n"
            "   {\n"
            "     \"direction\": \"UP\" | \"DOWN\" | \"ABSTAIN\",\n"
            "     \"rationale\": \"Lý do giải thích súc tích (tối đa 3 câu) viết hoàn toàn bằng TIẾNG VIỆT\",\n"
            "     \"evidence_candle_times\": [list of integer open_time_ms timestamps explicitly cited from the input],\n"
            "     \"lesson_ids\": [list of approved lesson_id strings referenced, or empty list]\n"
            "   }\n"
            "2. LANGUAGE REQUIREMENT: The \"rationale\" field MUST be written entirely in natural, professional Vietnamese (Tiếng Việt). Do NOT write English in rationale.\n"
            "3. Do NOT hallucinate timestamps outside the input window.\n"
            "4. Do NOT invent probabilities. Return only direction, rationale, evidence_candle_times, and lesson_ids.\n"
        )
        lessons_context = ""
        if approved_lessons:
            lessons_context = "\nAPPROVED LESSONS REPOSITORY:\n" + json.dumps(approved_lessons, indent=2) + "\n"

        input_context = "\nMARKET DATA CONTEXT (STRICTLY CAUSAL BEFORE CUTOFF):\n" + json.dumps(context_payload, indent=2)

        return schema_instruction + lessons_context + input_context

    def _parse_gemini_response(self, response_body_str: str, key_index: int) -> Dict[str, Any]:
        """Parses Gemini JSON response and extracts structured content."""
        data = json.loads(response_body_str)
        candidates = data.get("candidates", [])
        if not candidates:
            raise GeminiAPIError("No candidates returned by Gemini.")

        parts = candidates[0].get("content", {}).get("parts", [])
        if not parts:
            raise GeminiAPIError("Empty candidate content from Gemini.")

        raw_text = parts[0].get("text", "")
        parsed_payload = json.loads(raw_text)

        # Usage metadata
        usage = data.get("usageMetadata", {})
        prompt_tokens = usage.get("promptTokenCount", 0)
        completion_tokens = usage.get("candidatesTokenCount", 0)

        # Gemini 2.5 Flash approximate pricing: ~$0.075 / 1M prompt, $0.30 / 1M completion
        cost_usd = (prompt_tokens * 0.000000075) + (completion_tokens * 0.00000030)

        parsed_payload["model_id"] = self.model_name
        parsed_payload["key_index"] = key_index
        parsed_payload["prompt_tokens"] = prompt_tokens
        parsed_payload["completion_tokens"] = completion_tokens
        parsed_payload["estimated_cost_usd"] = cost_usd

        return parsed_payload

    def _generate_mock_response(
        self,
        context_payload: Dict[str, Any],
        custom_mock: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generates deterministic mock response for testing and offline development."""
        if custom_mock:
            return custom_mock

        candles = context_payload.get("candles", [])
        evidence_times = [candles[-1]["open_time_ms"]] if candles else []

        return {
            "direction": "UP",
            "rationale": "Phân tích mô phỏng: Quan sát thấy xung lực tăng giá (bullish momentum) trên chuỗi nến 6 giờ gần nhất trước mốc mua.",
            "evidence_candle_times": evidence_times,
            "lesson_ids": [],
            "model_id": f"{self.model_name}-mock",
            "key_index": 0,
            "prompt_tokens": 120,
            "completion_tokens": 45,
            "estimated_cost_usd": 0.0000225,
        }

    def extract_lessons_from_text(
        self,
        document_text: str,
        source_name: str,
        source_url: str,
        target_pattern_query: Optional[str] = None,
        mock_mode: bool = False,
    ) -> List[Dict[str, Any]]:
        """Analyzes literature/textbook text and extracts structured candidate lessons."""
        if mock_mode:
            return self._generate_mock_extracted_lessons(document_text, target_pattern_query)

        query_instruction = (
            f"Focus particularly on pattern: {target_pattern_query}."
            if target_pattern_query
            else "Identify all prominent candlestick patterns, chart formations, or price action rules in the text."
        )

        prompt_text = (
            "You are an expert quantitative technical analysis researcher.\n"
            "Analyze the following textbook/trading literature excerpt, identify chart/candlestick patterns, and extract structured candidate lessons.\n\n"
            f"{query_instruction}\n\n"
            "CRITICAL INSTRUCTIONS:\n"
            "1. Output MUST be a valid JSON array of objects strictly adhering to this schema:\n"
            "[\n"
            "  {\n"
            "    \"lesson_id\": \"unique_slug_identifying_pattern (e.g. double_bottom, bullish_engulfing)\",\n"
            "    \"title\": \"Clear pattern title\",\n"
            "    \"short_definition\": \"Brief definition and recognition rules (max 3 sentences) WRITTEN ENTIRELY IN NATURAL VIETNAMESE (Tiếng Việt)\",\n"
            "    \"caveats\": \"Limitations, false breakout traps, and volume/context requirements WRITTEN ENTIRELY IN NATURAL VIETNAMESE (Tiếng Việt)\",\n"
            "    \"source_snippet\": \"Verbatim quote (1-3 sentences) from the input text verifying the pattern\"\n"
            "  }\n"
            "]\n"
            "2. All explanations in short_definition and caveats MUST be in natural Vietnamese (Tiếng Việt).\n"
            "3. Do NOT invent concepts not supported by the excerpt.\n"
            "4. If no chart or candlestick patterns are present, return an empty array [].\n\n"
            f"DOCUMENT EXCERPT (Source: {source_name}):\n"
            f"{document_text[:8000]}"
        )

        max_attempts = max(1, self.key_manager.total_slots)
        last_error: Optional[Exception] = None

        for _ in range(max_attempts):
            slot = self.key_manager.get_next_slot()
            if not slot:
                if last_error:
                    raise last_error
                raise GeminiQuotaExceededError("No available Gemini API key slots.")

            url = self.API_URL_TEMPLATE.format(model=self.model_name, key=slot.api_key)
            request_body = {
                "contents": [{"parts": [{"text": prompt_text}]}],
                "generationConfig": {
                    "temperature": 0.1,
                    "response_mime_type": "application/json",
                },
            }

            try:
                import urllib.request
                import json

                req = urllib.request.Request(
                    url,
                    data=json.dumps(request_body).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
                    res_body = response.read().decode("utf-8")
                    data = json.loads(res_body)
                    text_parts = data.get("candidates", [])[0].get("content", {}).get("parts", [])
                    raw_text = text_parts[0].get("text", "[]") if text_parts else "[]"
                    lessons = json.loads(raw_text)
                    if isinstance(lessons, dict):
                        lessons = [lessons]
                    return lessons
            except Exception as e:
                last_error = e
                if "429" in str(e):
                    self.key_manager.mark_slot_cooldown(slot.index, 60.0)
                    continue
                import re
                sanitized_msg = re.sub(r'key=[^&\s]+', 'key=[REDACTED]', str(e))
                raise GeminiAPIError(f"Error querying Gemini for lesson extraction: {sanitized_msg}")
        raise GeminiQuotaExceededError("Exhausted all Gemini slots during lesson extraction.")

    def _generate_mock_extracted_lessons(
        self,
        document_text: str,
        target_pattern_query: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Generates deterministic mock extracted lessons grounded in document_text."""
        if not document_text or not document_text.strip():
            return []

        if target_pattern_query:
            query_clean = target_pattern_query.lower()
            if query_clean not in document_text.lower():
                return []
            slug = query_clean.replace(" ", "_")
            idx = document_text.lower().find(query_clean)
            start_idx = max(0, idx - 50)
            end_idx = min(len(document_text), idx + 200)
            real_snippet = document_text[start_idx:end_idx].strip()
            return [
                {
                    "lesson_id": slug,
                    "title": target_pattern_query,
                    "short_definition": f"Mô hình {target_pattern_query} được trích xuất từ tài liệu đối chiếu.",
                    "caveats": "Cần kiểm tra kỹ điều kiện thị trường và xác nhận khối lượng trước khi áp dụng.",
                    "source_snippet": real_snippet,
                }
            ]

        return []
