"""External analysis orchestration service connecting storage, causal context, Gemini adapter, verifier, and repository."""

import json
import logging
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from shootingstar.adapters.db.models import ExternalAnalysisJobModel, SnapshotModel
from shootingstar.adapters.db.repository import ExternalAnalysisJobRepository, SnapshotRepository
from shootingstar.adapters.model_api.gemini_adapter import GeminiModelAdapter
from shootingstar.adapters.storage import SnapshotStorage
from shootingstar.application.external_analysis.contracts import (
    AnalysisDirection,
    AnalysisMode,
    AnalysisStatus,
    ContextVariant,
    ExternalAnalysisJobDTO,
    ExternalAnalysisRequest,
    ModelPredictionOutput,
)
from shootingstar.application.external_analysis.context import (
    InsufficientHistoryError,
    build_context_a,
    build_context_b,
    extract_causal_window,
)
from shootingstar.application.external_analysis.verifier import ExternalAnalysisVerifier
from shootingstar.domain.models import Timeframe

logger = logging.getLogger(__name__)


class ExternalAnalysisService:
    """Orchestrates end-to-end external model analysis pipeline."""

    def __init__(
        self,
        job_repository: ExternalAnalysisJobRepository,
        snapshot_repository: SnapshotRepository,
        snapshot_storage: SnapshotStorage,
        gemini_adapter: Optional[GeminiModelAdapter] = None,
        approved_lessons: Optional[List[Dict[str, Any]]] = None,
    ):
        self.job_repo = job_repository
        self.snapshot_repo = snapshot_repository
        self.snapshot_storage = snapshot_storage
        self.gemini_adapter = gemini_adapter or GeminiModelAdapter()
        self.approved_lessons = approved_lessons or []

    def create_analysis_job(
        self,
        request: ExternalAnalysisRequest,
        mock_mode: bool = False,
        custom_mock_response: Optional[Dict[str, Any]] = None,
    ) -> ExternalAnalysisJobDTO:
        """Creates analysis job, enforces causal 6h history, calls model, and persists immutable record."""
        # 1. Fetch snapshot metadata from DB
        snap_rec = self.snapshot_repo.get_by_id(request.snapshot_id)
        if not snap_rec:
            raise ValueError(f"Snapshot with ID '{request.snapshot_id}' not found.")

        # 2. Load candles from snapshot storage
        candles = self.snapshot_storage.load_snapshot(Path(snap_rec.file_path))
        if not candles:
            raise ValueError(f"Snapshot data file for '{request.snapshot_id}' is empty or unreadable.")

        job_id = str(uuid.uuid4())
        now_dt = datetime.now(timezone.utc)

        # 3. Causal 6h window extraction (Fail-closed before API call)
        try:
            window_candles = extract_causal_window(
                candles=candles,
                t_ms=request.prediction_time_t_ms,
                window_hours=6.0,
            )
        except InsufficientHistoryError as e:
            logger.info("Insufficient history for t=%s: %s", request.prediction_time_t_ms, e)
            # Persist INSUFFICIENT_HISTORY job WITHOUT calling model API (Zero cost incurred)
            job = ExternalAnalysisJobModel(
                id=job_id,
                snapshot_id=snap_rec.id,
                snapshot_hash=snap_rec.sha256,
                symbol=snap_rec.symbol,
                timeframe=snap_rec.timeframe,
                prediction_time_t_ms=request.prediction_time_t_ms,
                purchase_price_p=request.purchase_price_p,
                horizon_minutes=request.horizon_minutes,
                mode=request.mode.value,
                context_variant=request.context_variant.value,
                status=AnalysisStatus.INSUFFICIENT_HISTORY.value,
                error_message=str(e),
                created_at=now_dt,
                updated_at=now_dt,
            )
            self.job_repo.save(job)
            return self._model_to_dto(job, leakage_banner=False)

        # 4. Build context payload
        if request.context_variant == ContextVariant.B:
            context_payload = build_context_b(
                candles=window_candles,
                purchase_price_p=request.purchase_price_p,
                snapshot_hash=snap_rec.sha256,
            )
        else:
            context_payload = build_context_a(
                candles=window_candles,
                snapshot_hash=snap_rec.sha256,
            )

        # 5. Call model adapter
        raw_output = self.gemini_adapter.analyze(
            context_payload=context_payload,
            approved_lessons=self.approved_lessons,
            prompt_version="v1",
            mock_mode=mock_mode,
            mock_response=custom_mock_response,
        )

        # 6. Verify and sanitize model response
        valid_candle_times = {c.open_time_ms for c in window_candles}
        approved_lesson_ids = {l.get("id", "") for l in self.approved_lessons if "id" in l}

        prediction = ExternalAnalysisVerifier.verify(
            raw_payload=raw_output,
            valid_candle_times=valid_candle_times,
            approved_lesson_ids=approved_lesson_ids,
            model_id=raw_output.get("model_id", "gemini-2.5-flash"),
            prompt_version="v1",
            key_index=raw_output.get("key_index"),
            prompt_tokens=raw_output.get("prompt_tokens"),
            completion_tokens=raw_output.get("completion_tokens"),
            estimated_cost_usd=raw_output.get("estimated_cost_usd"),
        )

        final_status = AnalysisStatus.READY if prediction.direction != AnalysisDirection.ABSTAIN else AnalysisStatus.ABSTAIN

        # Check leakage risk: if historical replay, model may have future knowledge
        is_retrospective = (request.mode == AnalysisMode.RETROSPECTIVE)

        # 7. Persist job in DB
        job = ExternalAnalysisJobModel(
            id=job_id,
            snapshot_id=snap_rec.id,
            snapshot_hash=snap_rec.sha256,
            symbol=snap_rec.symbol,
            timeframe=snap_rec.timeframe,
            prediction_time_t_ms=request.prediction_time_t_ms,
            purchase_price_p=request.purchase_price_p,
            horizon_minutes=request.horizon_minutes,
            mode=request.mode.value,
            context_variant=request.context_variant.value,
            prompt_version="v1",
            model_id=prediction.model_id,
            key_index=prediction.key_index,
            status=final_status.value,
            direction=prediction.direction.value,
            rationale=prediction.rationale,
            evidence_times_json=json.dumps(prediction.evidence_candle_times),
            lesson_ids_json=json.dumps(prediction.lesson_ids),
            raw_output_json=json.dumps(raw_output),
            prompt_tokens=prediction.prompt_tokens,
            completion_tokens=prediction.completion_tokens,
            estimated_cost_usd=prediction.estimated_cost_usd,
            is_revealed=False,
            created_at=now_dt,
            updated_at=now_dt,
        )
        self.job_repo.save(job)
        return self._model_to_dto(job, leakage_banner=is_retrospective)

    def record_user_vote(self, job_id: str, vote: str) -> ExternalAnalysisJobDTO:
        """Records isolated user vote (UP or DOWN). Never fed to model or training."""
        job = self.job_repo.get_by_id(job_id)
        if not job:
            raise ValueError(f"Job '{job_id}' not found.")

        clean_vote = vote.strip().upper()
        if clean_vote not in ("UP", "DOWN"):
            raise ValueError(f"Invalid vote '{vote}'. Must be UP or DOWN.")

        job.user_vote = clean_vote
        self.job_repo.save(job)
        return self._model_to_dto(job, leakage_banner=(job.mode == "RETROSPECTIVE"))

    def reveal_outcome(self, job_id: str) -> ExternalAnalysisJobDTO:
        """Reveals and matures outcome evaluated against purchase price P at t + 30m."""
        job = self.job_repo.get_by_id(job_id)
        if not job:
            raise ValueError(f"Job '{job_id}' not found.")

        # Load snapshot candles to evaluate outcome
        snap_rec = self.snapshot_repo.get_by_id(job.snapshot_id)
        if not snap_rec:
            raise ValueError(f"Snapshot with ID '{job.snapshot_id}' not found.")
        candles = self.snapshot_storage.load_snapshot(Path(snap_rec.file_path))
        tf = Timeframe(job.timeframe)
        horizon_ms = job.horizon_minutes * 60 * 1000
        target_time_ms = job.prediction_time_t_ms + horizon_ms

        now_ms = int(time.time() * 1000)

        # Prospective mode safety: cannot reveal future if real-time has not reached t + 30m
        if job.mode == "PROSPECTIVE" and now_ms < target_time_ms:
            dto = self._model_to_dto(job, leakage_banner=False)
            dto.outcome = "PENDING"
            return dto

        # Target horizon timestamp is strictly t + horizon_ms (interval containment only)
        target_candle = next(
            (c for c in candles if c.open_time_ms <= target_time_ms <= c.close_time_ms),
            None
        )
        if not target_candle:
            # Missing outcome candle in historical snapshot
            job.outcome = "UNSCORABLE"
            job.is_revealed = True
            job.outcome_evaluated_at_ms = now_ms
            self.job_repo.save(job)
            return self._model_to_dto(job, leakage_banner=(job.mode == "RETROSPECTIVE"))

        # Evaluate directional return relative to purchase price P
        target_price = target_candle.close
        job.target_price = target_price

        if target_price > job.purchase_price_p:
            outcome_direction = "UP"
        elif target_price < job.purchase_price_p:
            outcome_direction = "DOWN"
        else:
            outcome_direction = "FLAT"

        job.outcome = outcome_direction
        job.is_revealed = True
        job.outcome_evaluated_at_ms = now_ms
        self.job_repo.save(job)
        return self._model_to_dto(job, leakage_banner=(job.mode == "RETROSPECTIVE"))

    def get_job(self, job_id: str) -> Optional[ExternalAnalysisJobDTO]:
        job = self.job_repo.get_by_id(job_id)
        if not job:
            return None
        return self._model_to_dto(job, leakage_banner=(job.mode == "RETROSPECTIVE"))

    def _model_to_dto(self, job: ExternalAnalysisJobModel, leakage_banner: bool = False) -> ExternalAnalysisJobDTO:
        """Converts DB model to DTO. Outcome is strictly None unless is_revealed is True."""
        evidence_times = json.loads(job.evidence_times_json) if job.evidence_times_json else []
        lesson_ids = json.loads(job.lesson_ids_json) if job.lesson_ids_json else []

        ai_pred = None
        if job.direction:
            ai_pred = ModelPredictionOutput(
                direction=AnalysisDirection(job.direction),
                rationale=job.rationale or "",
                evidence_candle_times=evidence_times,
                lesson_ids=lesson_ids,
                probability_up=None,
                probability_down=None,
                model_id=job.model_id,
                prompt_version=job.prompt_version,
                key_index=job.key_index,
                prompt_tokens=job.prompt_tokens,
                completion_tokens=job.completion_tokens,
                estimated_cost_usd=job.estimated_cost_usd,
            )

        # STRICT INVARIANT: Outcome is hidden before reveal!
        revealed_outcome = job.outcome if job.is_revealed else None
        revealed_target_price = job.target_price if job.is_revealed else None

        return ExternalAnalysisJobDTO(
            id=job.id,
            snapshot_id=job.snapshot_id,
            snapshot_hash=job.snapshot_hash,
            symbol=job.symbol,
            timeframe=job.timeframe,
            prediction_time_t_ms=job.prediction_time_t_ms,
            purchase_price_p=job.purchase_price_p,
            horizon_minutes=job.horizon_minutes,
            mode=job.mode,
            context_variant=job.context_variant,
            status=job.status,
            created_at_iso=job.created_at.isoformat() if job.created_at else "",
            ai_prediction=ai_pred,
            user_vote=job.user_vote,
            outcome=revealed_outcome,
            target_price=revealed_target_price,
            outcome_evaluated_at_ms=job.outcome_evaluated_at_ms if job.is_revealed else None,
            error_message=job.error_message,
            leakage_risk_banner=leakage_banner,
        )
