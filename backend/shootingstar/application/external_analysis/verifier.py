"""Output schema and constraint verifier for external model responses."""

import logging
from typing import Any, Dict, List, Optional, Set
from shootingstar.application.external_analysis.contracts import (
    AnalysisDirection,
    ModelPredictionOutput,
)

logger = logging.getLogger(__name__)


class VerificationError(Exception):
    """Raised when external model payload fails fundamental schema contracts."""
    pass


class ExternalAnalysisVerifier:
    """Verifies and sanitizes external AI model responses against causal constraints."""

    @classmethod
    def verify(
        cls,
        raw_payload: Dict[str, Any],
        valid_candle_times: Set[int],
        approved_lesson_ids: Optional[Set[str]] = None,
        model_id: str = "gemini-2.5-flash",
        prompt_version: str = "v1",
        key_index: Optional[int] = None,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
        estimated_cost_usd: Optional[float] = None,
    ) -> ModelPredictionOutput:
        """Sanitizes raw model output against allowlists.

        INVARIANTS:
        1. Direction must strictly be UP, DOWN, or ABSTAIN. Malformed directions fallback to ABSTAIN.
        2. Evidence candle timestamps must exist in valid_candle_times (the 6h input window).
           Timestamps outside the input window are rejected as potential hallucinations.
        3. Lesson IDs must exist in approved_lesson_ids. Unapproved or fabricated IDs are stripped.
        4. Probability must remain None until explicit calibration pipeline is implemented.
        """
        approved_lesson_ids = approved_lesson_ids or set()

        # 1. Parse direction
        raw_direction = str(raw_payload.get("direction", "")).strip().upper()
        if raw_direction in ("UP", "DOWN", "ABSTAIN"):
            direction = AnalysisDirection(raw_direction)
        else:
            logger.warning("Invalid model direction '%s', defaulting to ABSTAIN", raw_direction)
            direction = AnalysisDirection.ABSTAIN

        # 2. Parse rationale
        rationale = str(raw_payload.get("rationale", "")).strip()
        if not rationale:
            rationale = "No rationale provided by model."

        # 3. Sanitize evidence candle timestamps
        raw_evidence = raw_payload.get("evidence_candle_times", [])
        sanitized_evidence: List[int] = []
        if isinstance(raw_evidence, list):
            for t in raw_evidence:
                try:
                    t_int = int(t)
                    if t_int in valid_candle_times:
                        sanitized_evidence.append(t_int)
                    else:
                        logger.warning("Rejected hallucinated candle timestamp %s not in 6h window", t_int)
                except (ValueError, TypeError):
                    continue

        # 4. Sanitize lesson IDs
        raw_lessons = raw_payload.get("lesson_ids", [])
        sanitized_lessons: List[str] = []
        if isinstance(raw_lessons, list):
            for l_id in raw_lessons:
                l_str = str(l_id).strip()
                if l_str in approved_lesson_ids:
                    sanitized_lessons.append(l_str)
                else:
                    logger.warning("Rejected unapproved or hallucinated lesson ID '%s'", l_str)

        # 5. Probability strictly None (Honest reporting: uncalibrated LLM probabilities are not real metrics)
        return ModelPredictionOutput(
            direction=direction,
            rationale=rationale,
            evidence_candle_times=sanitized_evidence,
            lesson_ids=sanitized_lessons,
            probability_up=None,
            probability_down=None,
            model_id=model_id,
            prompt_version=prompt_version,
            key_index=key_index,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            estimated_cost_usd=estimated_cost_usd,
        )
