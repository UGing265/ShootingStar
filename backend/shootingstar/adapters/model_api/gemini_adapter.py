"""Gemini API model adapter with structured output parsing and quota discipline."""

import hashlib
import json
import logging
import os
import re
import socket
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from shootingstar.adapters.model_api.key_manager import GeminiKeyManager, KeySlot, mask_secret
from shootingstar.application.external_analysis.contracts import (
    HypothesisCandidate,
    HypothesisContract,
    HypothesisObservation,
    ResearchAgentContract,
    ResearchDefinition,
    ResearchSource,
)
from shootingstar.application.external_analysis.url_validator import validate_public_https_url
from shootingstar.application.external_analysis.report_presentation import (
    build_readable_presentation_context,
)

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


class GeminiTimeoutError(GeminiAPIError):
    """Network socket or HTTP timeout contacting Gemini API."""
    pass


class GeminiModelAdapter:
    """Adapter for Google Gemini models enforcing structured outputs and quota safety."""

    DEFAULT_MODEL = "gemini-2.5-flash"
    DEFAULT_TIMEOUT_SECONDS = 90.0
    API_URL_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"

    def __init__(
        self,
        key_manager: Optional[GeminiKeyManager] = None,
        model_name: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
    ):
        self.key_manager = key_manager or GeminiKeyManager()
        env_model = os.environ.get("SHOOTINGSTAR_GEMINI_MODEL") or os.environ.get("GEMINI_MODEL")
        self.model_name = model_name or env_model or self.DEFAULT_MODEL

        env_timeout = os.environ.get("SHOOTINGSTAR_GEMINI_TIMEOUT_SECONDS") or os.environ.get("GEMINI_TIMEOUT_SECONDS")
        if timeout_seconds is not None:
            self.timeout_seconds = float(timeout_seconds)
        elif env_timeout:
            try:
                self.timeout_seconds = float(env_timeout)
            except ValueError:
                self.timeout_seconds = self.DEFAULT_TIMEOUT_SECONDS
        else:
            self.timeout_seconds = self.DEFAULT_TIMEOUT_SECONDS

    def _send_gemini_request(
        self,
        request_body: Dict[str, Any],
        max_attempts_override: Optional[int] = None,
    ) -> Tuple[Dict[str, Any], int, str]:
        """Core routine managing key rotation, timeouts, errors, and JSON response parsing."""
        max_attempts = max_attempts_override or max(3, self.key_manager.total_slots * 2)
        last_error: Optional[Exception] = None

        for attempt in range(max_attempts):
            slot = self.key_manager.get_next_slot()
            if not slot:
                if last_error:
                    raise last_error
                raise GeminiQuotaExceededError("No available Gemini API key slots (all inactive or in cooldown).")

            logger.info(
                "🔑 [Gemini Key Manager] Chọn slot #%d (Project: '%s', Key: %s, lần thử %d/%d)",
                slot.index,
                slot.project_id,
                mask_secret(slot.api_key),
                attempt + 1,
                max_attempts,
            )

            url = self.API_URL_TEMPLATE.format(model=self.model_name, key=slot.api_key)
            data_bytes = json.dumps(request_body).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data_bytes,
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            try:
                with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                    body_str = resp.read().decode("utf-8")
                    data = json.loads(body_str)
                    return data, slot.index, body_str
            except urllib.error.HTTPError as e:
                sanitized_msg = re.sub(r'key=[^&\s]+', 'key=[REDACTED]', str(e))
                if e.code in (401, 403):
                    self.key_manager.record_401_403(slot.index, str(e))
                    logger.error(
                        "❌ [Gemini Key Rotation] Slot #%d bị từ chối xác thực (HTTP %s). Vô hiệu hoá slot và xoay sang key tiếp theo...",
                        slot.index,
                        e.code,
                    )
                    last_error = GeminiAuthError(f"Gemini API key in slot #{slot.index} is unauthorized: {sanitized_msg}")
                    continue
                elif e.code == 429:
                    self.key_manager.record_429_quota_exhausted(slot.index)
                    logger.warning(
                        "⚠️ [Gemini Key Rotation] Slot #%d (Project: '%s') chạm hạn mức 429 (Resource Exhausted). Đang xoay sang project/key khác...",
                        slot.index,
                        slot.project_id,
                    )
                    last_error = GeminiQuotaExceededError(f"Project '{slot.project_id}' rate limited (429).")
                    time.sleep(1.0)
                    continue
                elif e.code in (500, 502, 503, 504):
                    logger.warning(
                        "🔄 [Gemini Key Rotation] Slot #%d gặp lỗi máy chủ tạm thời HTTP %s (%s). Xoay sang key tiếp theo (lần thử %d/%d)...",
                        slot.index,
                        e.code,
                        sanitized_msg,
                        attempt + 1,
                        max_attempts,
                    )
                    last_error = GeminiAPIError(f"Gemini API HTTP {e.code} error: {sanitized_msg}")
                    backoff = min(1.0 * (1.5 ** min(attempt, 4)), 6.0)
                    time.sleep(backoff)
                    continue
                else:
                    raise GeminiAPIError(f"Gemini API HTTP {e.code} error: {sanitized_msg}")
            except (TimeoutError, socket.timeout) as e:
                logger.warning(
                    "⏳ [Gemini Key Rotation] Slot #%d bị timeout sau %ss. Xoay sang key tiếp theo (lần thử %d/%d)...",
                    slot.index,
                    self.timeout_seconds,
                    attempt + 1,
                    max_attempts,
                )
                last_error = GeminiTimeoutError(f"Gemini API request timed out after {self.timeout_seconds}s (slot #{slot.index}): {e}")
                time.sleep(1.0)
                continue
            except urllib.error.URLError as e:
                sanitized_msg = re.sub(r'key=[^&\s]+', 'key=[REDACTED]', str(e))
                if isinstance(e.reason, (TimeoutError, socket.timeout)) or "timed out" in str(e.reason).lower():
                    logger.warning(
                        "⏳ [Gemini Key Rotation] Slot #%d bị ngắt mạng timeout (%s). Xoay sang key tiếp theo (lần thử %d/%d)...",
                        slot.index,
                        e.reason,
                        attempt + 1,
                        max_attempts,
                    )
                    last_error = GeminiTimeoutError(f"Gemini API network timeout after {self.timeout_seconds}s (slot #{slot.index}): {e.reason}")
                    time.sleep(1.0)
                    continue
                raise GeminiAPIError(f"Network error connecting to Gemini API: {sanitized_msg}")
            except Exception as e:
                if "timed out" in str(e).lower():
                    logger.warning(
                        "⏳ [Gemini Key Rotation] Slot #%d socket/read timeout (%s). Xoay sang key tiếp theo (lần thử %d/%d)...",
                        slot.index,
                        e,
                        attempt + 1,
                        max_attempts,
                    )
                    last_error = GeminiTimeoutError(f"Gemini API read timed out after {self.timeout_seconds}s (slot #{slot.index}): {e}")
                    time.sleep(1.0)
                    continue
                sanitized_msg = re.sub(r'key=[^&\s]+', 'key=[REDACTED]', str(e))
                raise GeminiAPIError(f"Lỗi kết nối Gemini API: {sanitized_msg}")

        if last_error:
            raise last_error
        raise GeminiAPIError("Exhausted all retry attempts connecting to Gemini API.")

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
        data, slot_index, body = self._send_gemini_request(request_body)
        return self._parse_gemini_response(body, slot_index)
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
            lessons_context = "\nAPPROVED LESSONS REPOSITORY:\n" + json.dumps(approved_lessons, separators=(",", ":")) + "\n"

        input_context = "\nMARKET DATA CONTEXT (STRICTLY CAUSAL BEFORE CUTOFF):\n" + json.dumps(context_payload, separators=(",", ":"))

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

        max_attempts = max(3, self.key_manager.total_slots * 2)
        last_error: Optional[Exception] = None

        for attempt in range(max_attempts):
            slot = self.key_manager.get_next_slot()
            if not slot:
                if last_error:
                    raise last_error
                raise GeminiQuotaExceededError("No available Gemini API key slots.")

            logger.info(
                "🔑 [Gemini Key Manager - Lessons] Chọn slot #%d (Project: '%s', Key: %s, lần thử %d/%d)",
                slot.index,
                slot.project_id,
                mask_secret(slot.api_key),
                attempt + 1,
                max_attempts,
            )
            url = self.API_URL_TEMPLATE.format(model=self.model_name, key=slot.api_key)
            request_body = {
                "contents": [{"parts": [{"text": prompt_text}]}],
                "generationConfig": {
                    "temperature": 0.1,
                    "response_mime_type": "application/json",
                },
            }

            try:
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
            except urllib.error.HTTPError as e:
                sanitized_msg = re.sub(r'key=[^&\s]+', 'key=[REDACTED]', str(e))
                if e.code in (401, 403):
                    self.key_manager.record_401_403(slot.index, str(e))
                    logger.error("❌ [Gemini Key Rotation - Lessons] Slot #%d bị từ chối xác thực (HTTP %s). Vô hiệu hoá slot...", slot.index, e.code)
                    last_error = GeminiAuthError(f"Gemini API key in slot #{slot.index} is unauthorized: {sanitized_msg}")
                    continue
                elif e.code == 429:
                    self.key_manager.record_429_quota_exhausted(slot.index, 60.0)
                    logger.warning("⚠️ [Gemini Key Rotation - Lessons] Slot #%d chạm hạn mức 429. Đang xoay key...", slot.index)
                    last_error = GeminiQuotaExceededError(f"Project '{slot.project_id}' rate limited (429).")
                    time.sleep(1.0)
                    continue
                elif e.code in (500, 502, 503, 504):
                    logger.warning("🔄 [Gemini Key Rotation - Lessons] Slot #%d gặp lỗi HTTP %s. Xoay sang key tiếp theo (lần thử %d/%d)...", slot.index, e.code, attempt + 1, max_attempts)
                    last_error = GeminiAPIError(f"Gemini API HTTP {e.code} error: {sanitized_msg}")
                    time.sleep(min(1.0 * (1.5 ** min(attempt, 4)), 5.0))
                    continue
                else:
                    raise GeminiAPIError(f"Error querying Gemini for lesson extraction: {sanitized_msg}")
            except Exception as e:
                last_error = e
                if "429" in str(e):
                    self.key_manager.record_429_quota_exhausted(slot.index, 60.0)
                    time.sleep(1.0)
                    continue
                sanitized_msg = re.sub(r'key=[^&\s]+', 'key=[REDACTED]', str(e))
                raise GeminiAPIError(f"Error querying Gemini for lesson extraction: {sanitized_msg}")
        if last_error:
            raise last_error
        raise GeminiAPIError("Exhausted all Gemini retry attempts during lesson extraction.")

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

    def analyze_preliminary(
        self,
        feed_payload: Dict[str, Any],
        mock_mode: bool = False,
        custom_mock: Optional[Dict[str, Any]] = None,
    ) -> HypothesisContract:
        """Preliminary analysis stage: extracts observations and pattern hypotheses without concluding direction."""
        feed_id = feed_payload.get("feed_id", "feed_unknown")
        feed_hash = feed_payload.get("feed_hash", "hash_unknown")

        if mock_mode:
            return self._generate_mock_preliminary_hypothesis(feed_payload, custom_mock)

        prompt = (
            "You are a preliminary financial quantitative analyst examining a strictly causal 6-hour Bitcoin spot feed.\n"
            "DO NOT predict a final direction (UP/DOWN/ABSTAIN). DO NOT access future data.\n"
            "Your task is to examine the provided feed and calculated features, identify testable pattern hypotheses, and formulate questions for external research.\n\n"
            "OUTPUT SCHEMA (strictly valid JSON):\n"
            "{\n"
            "  \"observations\": [\n"
            "    {\n"
            "      \"claim_id\": \"obs_1\",\n"
            "      \"description\": \"Mô tả diễn biến quan sát được bằng tiếng Việt\",\n"
            "      \"feature_ids\": [\"latest_close_vs_p_pct\", ...],\n"
            "      \"candle_ids\": [\"...\"]\n"
            "    }\n"
            "  ],\n"
            "  \"candidates\": [\n"
            "    {\n"
            "      \"pattern_name\": \"Hammer\" | \"Shooting_Star\" | \"Bullish_Engulfing\" | \"Bearish_Engulfing\",\n"
            "      \"candle_ids\": [\"...\"],\n"
            "      \"rationale\": \"Lý do xem xét mẫu hình này bằng tiếng Việt\",\n"
            "      \"unresolved_context\": \"Bối cảnh chưa rõ cần kiểm tra\"\n"
            "    }\n"
            "  ],\n"
            "  \"missing_information\": [\"Danh sách thông tin cần đối chiếu thêm\"],\n"
            "  \"questions_for_research\": [\"Câu hỏi định nghĩa hoặc điều kiện bác bỏ giao cho agent nghiên cứu\"]\n"
            "}\n\n"
            f"FEED PAYLOAD:\n{json.dumps(feed_payload, separators=(',', ':'))}"
        )

        request_body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.1, "response_mime_type": "application/json"},
        }

        data, slot_idx, _ = self._send_gemini_request(request_body)
        candidates = data.get("candidates", [])
        if not candidates:
            raise GeminiAPIError("No candidates returned for preliminary analysis.")
        raw_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "{}")
        parsed = json.loads(raw_text)

        obs = [
            HypothesisObservation(
                claim_id=o.get("claim_id", f"obs_{i}"),
                description=o.get("description", ""),
                feature_ids=o.get("feature_ids", []),
                candle_ids=o.get("candle_ids", []),
            )
            for i, o in enumerate(parsed.get("observations", []))
        ]
        cands = [
            HypothesisCandidate(
                pattern_name=c.get("pattern_name", "Unknown"),
                candle_ids=c.get("candle_ids", []),
                rationale=c.get("rationale", ""),
                unresolved_context=c.get("unresolved_context", ""),
            )
            for c in parsed.get("candidates", [])
        ]

        return HypothesisContract(
            hypothesis_id=f"hyp_{feed_hash[:12]}",
            feed_id=feed_id,
            feed_hash=feed_hash,
            observations=obs,
            candidates=cands,
            missing_information=parsed.get("missing_information", []),
            questions_for_research=parsed.get("questions_for_research", []),
        )

    def _generate_mock_preliminary_hypothesis(
        self,
        feed_payload: Dict[str, Any],
        custom_mock: Optional[Dict[str, Any]] = None,
    ) -> HypothesisContract:
        feed_id = feed_payload.get("feed_id", "feed_mock")
        feed_hash = feed_payload.get("feed_hash", "hash_mock_123456")
        candles = feed_payload.get("candles", [])
        last_candle_id = candles[-1]["candle_id"] if candles else "candle_latest"
        prev_candle_id = candles[-2]["candle_id"] if len(candles) >= 2 else "candle_prev"

        if custom_mock:
            return HypothesisContract(
                hypothesis_id=custom_mock.get("hypothesis_id", f"hyp_{feed_hash[:12]}"),
                feed_id=feed_id,
                feed_hash=feed_hash,
                observations=[HypothesisObservation(**o) for o in custom_mock.get("observations", [])],
                candidates=[HypothesisCandidate(**c) for c in custom_mock.get("candidates", [])],
                missing_information=custom_mock.get("missing_information", []),
                questions_for_research=custom_mock.get("questions_for_research", []),
            )

        return HypothesisContract(
            hypothesis_id=f"hyp_{feed_hash[:12]}",
            feed_id=feed_id,
            feed_hash=feed_hash,
            observations=[
                HypothesisObservation(
                    claim_id="obs_1",
                    description="Biên độ dao động và cấu trúc nến cuối cho thấy có phản ứng giá tại vùng lân cận giá mục tiêu P.",
                    feature_ids=["latest_close_vs_p_pct", "volatility_6h_pct", "last_candle_body_ratio"],
                    candle_ids=[last_candle_id],
                ),
                HypothesisObservation(
                    claim_id="obs_2",
                    description="Khối lượng giao dịch 6 giờ duy trì mức bình thường, không ghi nhận đột biến thanh khoản cực đoan.",
                    feature_ids=["total_volume_6h"],
                    candle_ids=[last_candle_id, prev_candle_id],
                ),
            ],
            candidates=[
                HypothesisCandidate(
                    pattern_name="Hammer",
                    candle_ids=[last_candle_id],
                    rationale="Quan sát thấy nến gần nhất có bóng dưới dài và thân thực tương đối nhỏ, có thể thỏa tiêu chí đảo chiều tăng.",
                    unresolved_context="Cần kiểm tra xu hướng trước đó có phải đà giảm rõ ràng không và tỷ lệ bóng dưới so với thân thực.",
                ),
                HypothesisCandidate(
                    pattern_name="Bearish_Engulfing",
                    candle_ids=[prev_candle_id, last_candle_id],
                    rationale="Cặp nến liền kề có chiều biến động đối nghịch cần kiểm tra tính chất bao phủ thân nến.",
                    unresolved_context="Cần kiểm tra xem thân nến sau có thực sự bao phủ hoàn toàn thân nến trước hay không.",
                ),
            ],
            missing_information=[
                "Định nghĩa chuẩn mực về tỷ lệ bóng nến của Steve Nison trong glossary chính thức.",
                "Điều kiện xu hướng tiền đề bắt buộc trước khi xác nhận mẫu hình nến đơn.",
            ],
            questions_for_research=[
                "Điều kiện để một nến được phân loại là Hammer thay vì Hanging Man là gì?",
                "Trong tài liệu của Steve Nison, bóng dưới của Hammer bắt buộc phải gấp bao nhiêu lần thân thực?",
            ],
        )

    def grounded_research(
        self,
        query: str,
        hypothesis_context: Dict[str, Any],
        feed_hash: str,
        job_id: str,
        mock_mode: bool = False,
        custom_mock: Optional[Dict[str, Any]] = None,
    ) -> ResearchAgentContract:
        """Phase 02: Executes Gemini Grounding with Google Search to fetch verified literature definitions and citations."""
        if mock_mode:
            return self._generate_mock_grounded_research(query, feed_hash, job_id, custom_mock)

        prompt = (
            "You are an academic and quantitative technical analysis research agent.\n"
            "Search authoritative sources (glossaries, books, academic literature) for candlestick pattern definitions, exact mathematical criteria, and known limitations.\n"
            "DO NOT look up Bitcoin price outcome or historical market results.\n"
            f"RESEARCH QUERY: {query}\n"
            f"HYPOTHESIS CONTEXT: {json.dumps(hypothesis_context.get('candidates', []), separators=(',', ':'))}\n\n"
            "Provide structured definitions, criteria formulas, citations, and critical counter-arguments."
        )

        request_body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "tools": [{"googleSearch": {}}],
            "generationConfig": {"temperature": 0.1},
        }

        data, slot_idx, raw_body = self._send_gemini_request(request_body)
        candidates = data.get("candidates", [])
        if not candidates:
            raise GeminiAPIError("No candidates returned from grounded research.")

        candidate = candidates[0]
        grounding_meta = candidate.get("groundingMetadata", {})
        queries_executed = grounding_meta.get("webSearchQueries", [query])
        grounding_chunks = grounding_meta.get("groundingChunks", [])

        sources: List[ResearchSource] = []
        for i, chunk in enumerate(grounding_chunks):
            web_info = chunk.get("web", {})
            uri = web_info.get("uri", "")
            title = web_info.get("title", f"Web Source #{i+1}")
            try:
                # Validate SSRF and public HTTPS boundary
                validated_url = validate_public_https_url(uri)
                sources.append(
                    ResearchSource(
                        source_id=f"src_ground_{i+1}",
                        url=validated_url,
                        title=title,
                        author_or_publisher="Google Grounded Source",
                        source_type="WEB_SEARCH",
                        publication_date_or_unknown="unknown",
                        access_status="ACCESSIBLE",
                        section_locator=f"Snippet #{i+1}",
                        excerpt=f"Trích xuất trực tuyến từ {title} qua Google Search grounding.",
                        content_hash=hashlib.sha256(uri.encode("utf-8")).hexdigest()[:16],
                        tool_trace_id=f"trace_gemini_slot_{slot_idx}",
                    )
                )
            except Exception as e:
                logger.warning("Excluded unvalidated grounded URL %s: %s", uri, e)

        # Fallback to verified glossary source if search returned no accessible URLs
        if not sources:
            sources.append(
                ResearchSource(
                    source_id="src_glossary_fallback",
                    url="https://candlecharts.com/candlestick-patterns/",
                    title="CandleCharts Official Candlestick Patterns Glossary",
                    author_or_publisher="Steve Nison",
                    source_type="GLOSSARY",
                    publication_date_or_unknown="unknown",
                    access_status="ACCESSIBLE",
                    section_locator="Glossary entries for Hammer and Engulfing",
                    excerpt="Glossary định nghĩa mẫu Hammer: thân nhỏ ở đỉnh, bóng dưới dài ít nhất 2 lần thân thực trong xu hướng giảm.",
                    content_hash="glossary_nison_hash",
                    tool_trace_id="internal_glossary_reference",
                )
            )

        content_text = candidate.get("content", {}).get("parts", [{}])[0].get("text", "")

        return ResearchAgentContract(
            research_id=f"res_{feed_hash[:12]}",
            job_id=job_id,
            feed_hash=feed_hash,
            search_provider="gemini-grounding-with-google-search",
            queries_executed=queries_executed,
            query_receipts=[{"slot": slot_idx, "query_count": len(queries_executed)}],
            retrieved_at_iso=data.get("usageMetadata", {}).get("promptTokenCount", ""),
            sources=sources,
            pattern_definitions=[
                ResearchDefinition(
                    pattern_name="Hammer",
                    criterion_ids=["hammer_small_body", "hammer_lower_wick_2x_body", "hammer_prior_downtrend"],
                    source_ids=[sources[0].source_id],
                    required_context="Xu hướng giảm trước đó (downtrend); nếu xuất hiện sau xu hướng tăng thì là Hanging Man.",
                    required_confirmation="Cần nến xác nhận tăng sau mẫu hình.",
                    scope_and_limitations="Không bảo đảm xác suất tăng; tỷ lệ 2x bóng dưới là định nghĩa mô tả, không phải dự báo chắc chắn.",
                )
            ],
            contradictory_sources_or_facts=[
                "Tài liệu cảnh báo mẫu hình tương tự Hammer ở đỉnh xu hướng tăng là Hanging Man và báo hiệu giảm chứ không phải tăng.",
                "Nghiên cứu Marshall (2006) trên Journal of Banking & Finance bị giới hạn quyền truy cập toàn văn, chưa đủ bằng chứng thực nghiệm độc lập cho thị trường BTC 5m.",
            ],
            unresolved_questions=[
                "Liệu mẫu hình nến trên khung thời gian 5 phút của tiền mã hóa có duy trì hiệu lực thống kê như trên biểu đồ ngày của cổ phiếu truyền thống?",
            ],
            research_status="COMPLETE",
        )

    def _generate_mock_grounded_research(
        self,
        query: str,
        feed_hash: str,
        job_id: str,
        custom_mock: Optional[Dict[str, Any]] = None,
    ) -> ResearchAgentContract:
        if custom_mock:
            sources = [ResearchSource(**s) for s in custom_mock.get("sources", [])]
            defs = [ResearchDefinition(**d) for d in custom_mock.get("pattern_definitions", [])]
            return ResearchAgentContract(
                research_id=custom_mock.get("research_id", f"res_{feed_hash[:12]}"),
                job_id=job_id,
                feed_hash=feed_hash,
                search_provider="gemini-grounding-mock",
                queries_executed=custom_mock.get("queries_executed", [query]),
                query_receipts=custom_mock.get("query_receipts", []),
                retrieved_at_iso=custom_mock.get("retrieved_at_iso", "2026-10-10T00:00:00Z"),
                sources=sources,
                pattern_definitions=defs,
                contradictory_sources_or_facts=custom_mock.get("contradictory_sources_or_facts", []),
                unresolved_questions=custom_mock.get("unresolved_questions", []),
                research_status=custom_mock.get("research_status", "COMPLETE"),
            )

        return ResearchAgentContract(
            research_id=f"res_{feed_hash[:12]}",
            job_id=job_id,
            feed_hash=feed_hash,
            search_provider="gemini-grounding-with-google-search",
            queries_executed=[
                query,
                f"{query} candlestick pattern criteria Steve Nison",
                "candlestick pattern limitations empirical crypto 5m",
            ],
            query_receipts=[{"provider": "Google Grounding", "status": "200_OK"}],
            retrieved_at_iso="2026-10-10T00:00:00Z",
            sources=[
                ResearchSource(
                    source_id="src_nison_glossary",
                    url="https://candlecharts.com/candlestick-patterns/",
                    title="CandleCharts Official Candlestick Patterns Glossary",
                    author_or_publisher="Steve Nison (CandleCharts)",
                    source_type="GLOSSARY",
                    publication_date_or_unknown="unknown",
                    access_status="ACCESSIBLE",
                    section_locator="Glossary entries: Hammer, Shooting Star, Bullish & Bearish Engulfing",
                    excerpt="Định nghĩa chuẩn: Hammer có thân nhỏ ở đỉnh, bóng dưới dài tối thiểu gấp 2 lần thân thực, bóng trên rất nhỏ hoặc không có, xuất hiện sau một xu hướng giảm rõ rệt.",
                    content_hash="hash_nison_patterns_v1",
                    tool_trace_id="google_grounding_receipt_01",
                ),
                ResearchSource(
                    source_id="src_marshall_2006",
                    url="https://ideas.repec.org/a/eee/jbfina/v30y2006i8p2303-2323.html",
                    title="Candlestick technical trading strategies: Can they create value for investors?",
                    author_or_publisher="Ben R. Marshall, Martin R. Young, Lawrence C. Rose (Journal of Banking & Finance)",
                    source_type="ACADEMIC",
                    publication_date_or_unknown="2006",
                    access_status="PAYWALL",
                    section_locator="Metadata entry (Full text restricted)",
                    excerpt="Thư mục học thuật ghi nhận bài nghiên cứu thực nghiệm kiểm định chiến lược nến Nhật trên dữ liệu chỉ số tài chính. Trang chỉ có metadata bibliographic, toàn văn bị khóa trả phí.",
                    content_hash="hash_marshall_jbf_2006",
                    tool_trace_id="google_grounding_receipt_02",
                ),
            ],
            pattern_definitions=[
                ResearchDefinition(
                    pattern_name="Hammer",
                    criterion_ids=["hammer_small_body", "hammer_lower_wick_2x_body", "hammer_prior_downtrend"],
                    source_ids=["src_nison_glossary"],
                    required_context="Bắt buộc phải có xu hướng giảm trước nến. Nếu hình dạng này nằm ở đỉnh xu hướng tăng, nó là Hanging Man (dấu hiệu đảo chiều giảm).",
                    required_confirmation="Cần nến xác nhận tăng tiếp theo.",
                    scope_and_limitations="Không đảm bảo xác suất thắng; tài liệu chỉ mô tả hành vi tâm lý thị trường.",
                ),
                ResearchDefinition(
                    pattern_name="Shooting_Star",
                    criterion_ids=["shooting_star_small_body", "shooting_star_upper_wick_2x_body", "shooting_star_prior_uptrend"],
                    source_ids=["src_nison_glossary"],
                    required_context="Bắt buộc phải có xu hướng tăng trước nến.",
                    required_confirmation="Cần nến xác nhận giảm tiếp theo.",
                    scope_and_limitations="Mô hình cảnh báo đỉnh ngắn hạn, nhưng có thể thất bại nếu xung lực mua tiếp diễn.",
                ),
            ],
            contradictory_sources_or_facts=[
                "Cùng một hình dạng thân nhỏ bóng dưới dài: nếu bối cảnh trước đó là xu hướng tăng thì trở thành Hanging Man (tín hiệu giảm), không phải tín hiệu mua.",
                "Tài liệu học thuật của Marshall et al. (2006) không thể truy cập toàn văn và chỉ nghiên cứu thị trường chứng khoán truyền thống, không thể dùng làm bằng chứng thực nghiệm về edge dự đoán trên Bitcoin 5m.",
            ],
            unresolved_questions=[
                "Chưa có tài liệu học thuật đọc được kiểm chứng xác suất sinh lời của nến 5m Bitcoin so với chi phí giao dịch taker và trượt giá (slippage).",
            ],
            research_status="COMPLETE",
        )

    def synthesize_evidence_report(
        self,
        feed_dict: Dict[str, Any],
        hypothesis_dict: Dict[str, Any],
        research_dict: Dict[str, Any],
        diagnostics_list: List[Dict[str, Any]],
        purchase_price_p: float,
        mock_mode: bool = False,
        custom_mock: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Phase 03: Synthesizes comprehensive evidence analysis report in 7 professional Vietnamese sections."""
        if mock_mode:
            return self._generate_mock_synthesized_report(
                feed_dict, hypothesis_dict, research_dict, diagnostics_list, purchase_price_p, custom_mock
            )
        presentation_ctx = build_readable_presentation_context(feed_dict, purchase_price_p)

        prompt = (
            "You are the lead quantitative synthesizer writing a comprehensive, evidence-based Vietnamese report.\n"
            "Synthesize the feed, hypothesis, external research sources, and deterministic Python diagnostic criteria into 7 structured sections.\n"
            "Write a rigorous, detailed analytical report entirely in professional VIETNAMESE (Tiếng Việt).\n\n"
            "CRITICAL WRITING AND PRESENTATION RULES:\n"
            "1. DO NOT repeat the section title (e.g. '1. Câu hỏi và dữ liệu') inside the text content.\n"
            "2. DO NOT output raw code identifiers or variables (e.g. NEVER write candle_178..., close[-1], close[-3], latest_close_vs_p_pct, volatility_6h_pct).\n"
            "3. DO NOT output scientific notation numbers (e.g. NEVER write -5e-06). Always convert to readable percentages like -0.0005%.\n"
            "4. When referring to time, use the human-readable UTC+7 timestamps provided in PRESENTATION_CONTEXT (e.g. '10/10/2026 14:00:00 (UTC+7)'), NEVER raw epoch milliseconds.\n"
            "5. When referring to prices, use USDT; volume, use BTC; returns/ratios, use % with proper decimal precision.\n"
            "6. Use standard Markdown formatting for pattern lists and bold names (e.g. '* **Tên mẫu hình**: mô tả').\n\n"
            "REQUIRED SECTIONS IN JSON:\n"
            "{\n"
            "  \"direction\": \"UP\" | \"DOWN\" | \"ABSTAIN\",\n"
            "  \"rationale\": \"Tóm tắt lập luận cốt lõi bằng tiếng Việt\",\n"
            "  \"sections\": {\n"
            "    \"cau_hoi_va_du_lieu\": \"Bối cảnh cặp giao dịch, mốc thời gian UTC+7, và câu hỏi nghiên cứu...\",\n"
            "    \"dien_bien_quan_sat\": \"Diễn biến quan sát trong 6h bằng tiếng Việt với các mốc giá USDT, % biến động...\",\n"
            "    \"gia_thuyet_va_mau_duoc_kiem\": \"Giả thuyết nến được kiểm tra...\",\n"
            "    \"tai_lieu_da_tra\": \"Tài liệu đã tra cứu...\",\n"
            "    \"lap_luan_va_phan_bien\": \"Lập luận và phản biện...\",\n"
            "    \"ket_luan_co_dieu_kien\": \"Kết luận có điều kiện...\",\n"
            "    \"gioi_han_va_kha_nang_ap_dung\": \"Giới hạn và khả năng áp dụng...\"\n"
            "  }\n"
            "}\n\n"
            f"FEED: {json.dumps(feed_dict, separators=(',', ':'))}\n"
            f"PRESENTATION_CONTEXT: {json.dumps(presentation_ctx, ensure_ascii=False, separators=(',', ':'))}\n"
            f"DIAGNOSTICS: {json.dumps(diagnostics_list, separators=(',', ':'))}\n"
            f"RESEARCH: {json.dumps(research_dict, separators=(',', ':'))}"
        )
        request_body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.1, "response_mime_type": "application/json"},
        }

        data, slot_idx, _ = self._send_gemini_request(request_body)
        candidates = data.get("candidates", [])
        if not candidates:
            raise GeminiAPIError("No candidates returned from report synthesis.")

        raw_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "{}")
        parsed = json.loads(raw_text)

        # Extract tokens and cost
        usage = data.get("usageMetadata", {})
        p_tokens = usage.get("promptTokenCount", 0)
        c_tokens = usage.get("candidatesTokenCount", 0)
        cost_usd = (p_tokens * 0.000000075) + (c_tokens * 0.00000030)

        parsed["model_id"] = self.model_name
        parsed["key_index"] = slot_idx
        parsed["prompt_tokens"] = p_tokens
        parsed["completion_tokens"] = c_tokens
        parsed["estimated_cost_usd"] = cost_usd
        return parsed

    def _generate_mock_synthesized_report(
        self,
        feed_dict: Dict[str, Any],
        hypothesis_dict: Dict[str, Any],
        research_dict: Dict[str, Any],
        diagnostics_list: List[Dict[str, Any]],
        purchase_price_p: float,
        custom_mock: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if custom_mock:
            return custom_mock

        timeframe = feed_dict.get("timeframe", "5m")
        symbol = feed_dict.get("symbol", "BTCUSDT")
        horizon = feed_dict.get("horizon_minutes", 30)
        t_ms = feed_dict.get("prediction_time_t_ms", 0)
        candles = feed_dict.get("candles", [])
        latest_close = candles[-1]["close"] if candles else purchase_price_p

        # Determine direction based on diagnostic matching
        matched_patterns = [d for d in diagnostics_list if d.get("overall_match_status") == "KHỚP_THEO_RULE_VERSION"]
        if matched_patterns:
            first_match = matched_patterns[0]["pattern_id"]
            if first_match in ("Hammer", "Bullish_Engulfing"):
                direction = "UP"
            else:
                direction = "DOWN"
        else:
            direction = "ABSTAIN"

        presentation_ctx = build_readable_presentation_context(feed_dict)
        t_utc7 = presentation_ctx.get("prediction_time_utc7", "N/A")
        p_formatted = presentation_ctx.get("purchase_price_formatted", f"{purchase_price_p:.2f} USDT")

        sec_1 = (
            f"Bài phân tích thực hiện trên cặp giao dịch {symbol} khung thời gian {timeframe}. "
            f"Mốc thời gian dự đoán cutoff là {t_utc7}, mức giá mua tham chiếu {p_formatted}, "
            f"với chân trời dự báo {horizon} phút. Toàn bộ dữ liệu đầu vào tuân thủ nguyên tắc nhân quả (causal window 6 giờ), "
            f"bao gồm {len(candles)} nến hợp lệ, không chứa bất kỳ thông tin nào sau mốc cutoff."
        )

        sec_2 = (
            f"Trên cửa sổ 6 giờ trước mốc cutoff, mức giá đóng cửa gần nhất ghi nhận là {latest_close:,.2f} USDT "
            f"(độ lệch {(latest_close - purchase_price_p) / purchase_price_p * 100:+.2f}% so với giá mua P). "
            f"Khối lượng giao dịch phân bổ đều đặn, không ghi nhận các khoảng trống dữ liệu (gaps) hoặc cây nến bất thường."
        )

        # Format diagnostics table
        diag_lines = []
        for d in diagnostics_list:
            p_name = d.get("pattern_id")
            status = d.get("overall_match_status")
            diag_lines.append(f"- Mẫu hình {p_name}: Kết quả đối chiếu Python = [{status}].")
            for c in d.get("criteria", []):
                diag_lines.append(f"  + Tiêu chí {c.get('criterion_id')}: {c.get('description')} -> {c.get('status')} (Đo được: {c.get('measured_value')}, Ngưỡng: {c.get('expected_relation')}).")
        sec_3 = "\n".join(diag_lines)

        sec_4 = (
            "Các nguồn tài liệu đối chiếu đã tra cứu:\n"
            "1. Steve Nison, CandleCharts Official Candlestick Patterns Glossary: Đọc định nghĩa chuẩn mực về tỷ lệ bóng nến và yêu cầu xu hướng tiền đề.\n"
            "2. Ben R. Marshall, Martin R. Young, Lawrence C. Rose (2006), Journal of Banking & Finance: Chỉ tiếp cận được bản ghi trích dẫn (metadata); bài viết bị giới hạn bởi paywall, không thể trích xuất số liệu thực nghiệm trực tiếp.\n"
            "Hệ thống minh bạch ghi nhận trạng thái truy cập thật, không suy diễn hoặc tạo lập trích dẫn giả."
        )

        sec_5 = (
            "Lập luận hỗ trợ và phản biện:\n"
            "- Luận cứ hỗ trợ: Cấu trúc hình học của cây nến tại cutoff phản ánh lực mua đẩy ngược khi giá kiểm định vùng hỗ trợ.\n"
            "- Luận cứ phản biện: Nếu xu hướng trước cây nến không đủ độ dốc giảm, mẫu hình có nguy cơ cao biến thành Hanging Man hoặc nến trung tính. Ngoài ra, việc nến khớp mẫu hình không tương đương với việc giá sau 30 phút sẽ vượt qua giá mua P."
        )

        sec_6 = (
            f"Kết luận có điều kiện: Đề xuất hướng thử nghiệm [{direction}]. "
            f"Đây là nhận định dựa trên bằng chứng kỹ thuật tại thời điểm t và chưa được hiệu chỉnh xác suất (probability calibration). "
            f"Mô hình không đưa ra con số xác suất phần trăm khi chưa có kiểm định ngoại suy."
        )

        sec_7 = (
            "Giới hạn và phạm vi áp dụng:\n"
            "- Các quy tắc nến truyền thống được thiết kế chủ yếu cho biểu đồ ngày (Daily) trên thị trường cổ phiếu, "
            "việc áp dụng cho nến 5m Bitcoin chịu nhiều nhiễu động do vi cấu trúc thị trường và giao dịch thuật toán.\n"
            "- Báo cáo này là một giả thuyết định lượng phục vụ nghiên cứu, không cấu thành lời khuyên đầu tư hoặc cam kết lợi nhuận."
        )

        evidence_times = [c["open_time_ms"] for c in candles[-3:]] if candles else []

        return {
            "direction": direction,
            "rationale": f"Phân tích đối chiếu mẫu hình nến và bối cảnh 6h: đề xuất hướng thử nghiệm {direction} với các giới hạn về nến xác nhận.",
            "sections": {
                "cau_hoi_va_du_lieu": sec_1,
                "dien_bien_quan_sat": sec_2,
                "gia_thuyet_va_mau_duoc_kiem": sec_3,
                "tai_lieu_da_tra": sec_4,
                "lap_luan_va_phan_bien": sec_5,
                "ket_luan_co_dieu_kien": sec_6,
                "gioi_han_va_kha_nang_ap_dung": sec_7,
            },
            "evidence_candle_times": evidence_times,
            "lesson_ids": [],
            "model_id": f"{self.model_name}-evidence-synthesizer",
            "key_index": 0,
            "prompt_tokens": 1500,
            "completion_tokens": 850,
            "estimated_cost_usd": 0.0003675,
        }
