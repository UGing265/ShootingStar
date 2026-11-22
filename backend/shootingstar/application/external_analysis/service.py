"""External analysis job lifecycle and forecast orchestration."""

import json
import math
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from shootingstar.adapters.db.models import ExternalAnalysisJobModel
from shootingstar.adapters.model_api.gemini_adapter import GeminiModelAdapter
from shootingstar.adapters.storage import resolve_snapshot_file_path
from shootingstar.adapters.model_api.prompts.forecast_6h_prompt import PROMPT_VERSION
from shootingstar.application.forecast.errors import InsufficientHistoryError
from shootingstar.application.external_analysis.contracts import AnalysisMode, AnalysisStatus
from shootingstar.application.external_analysis.forecast_pipeline import run_forecast_pipeline
from shootingstar.application.external_analysis.job_dto import model_to_dto
from shootingstar.application.forecast.candle_window import candle_window
from shootingstar.application.forecast.outcome import evaluate_direction_outcome
from shootingstar.application.forecast.technical_digest import build_technical_digest
from shootingstar.domain.models import Timeframe


class ExternalAnalysisService:
    def __init__(self, job_repository, snapshot_repository, snapshot_storage, gemini_adapter=None):
        self.job_repo = job_repository
        self.snapshot_repo = snapshot_repository
        self.snapshot_storage = snapshot_storage
        self.gemini_adapter = gemini_adapter or GeminiModelAdapter()

    @staticmethod
    def _snapshot_path(snapshot) -> Path:
        path = resolve_snapshot_file_path(snapshot.file_path)
        if path is None:
            raise ValueError(f"Snapshot data file for '{snapshot.id}' not found on disk.")
        return path

    def _window(self, snapshot, t_ms, lookback_days, horizon_minutes, snapshot_candles=None):
        if snapshot_candles is None:
            start = t_ms - (max(lookback_days, 9) + 1) * 86_400_000
            end = t_ms + horizon_minutes * 60_000 + 2 * Timeframe(snapshot.timeframe).duration_ms
            candles = self.snapshot_storage.load_snapshot_window(self._snapshot_path(snapshot), start_ms=start, end_ms=end)
            candles.sort(key=lambda c: c.open_time_ms)
        else:
            candles = snapshot_candles
        return candle_window(candles, t_ms, lookback_days, horizon_minutes)

    def create_analysis_job(self, request, mock_mode=False, custom_mock_response=None, run_immediately=True, snapshot_candles=None):
        if mock_mode or custom_mock_response is not None:
            raise ValueError("Production mock forecasts are disabled")
        if request.horizon_minutes <= 0 or request.lookback_days <= 0 or not math.isfinite(request.purchase_price_p) or request.purchase_price_p <= 0:
            raise ValueError("Invalid horizon, lookback or purchase price")
        snapshot = self.snapshot_repo.get_by_id(request.snapshot_id)
        if not snapshot:
            raise ValueError(f"Snapshot with ID '{request.snapshot_id}' not found.")
        now = datetime.now(timezone.utc)
        job = ExternalAnalysisJobModel(
            id=str(uuid.uuid4()), snapshot_id=snapshot.id, snapshot_hash=snapshot.sha256,
            symbol=snapshot.symbol, timeframe=snapshot.timeframe, prediction_time_t_ms=request.prediction_time_t_ms,
            purchase_price_p=request.purchase_price_p, horizon_minutes=request.horizon_minutes,
            mode=request.mode.value, context_variant=request.context_variant.value, prompt_version=PROMPT_VERSION,
            model_id=self.gemini_adapter.model_name, status=AnalysisStatus.PREPARING_FEED.value,
            evidence_envelope_json=json.dumps({"lookback_days": request.lookback_days}),
            is_revealed=False, created_at=now, updated_at=now)
        try:
            candles = self._window(snapshot, request.prediction_time_t_ms, request.lookback_days, request.horizon_minutes, snapshot_candles)
            build_technical_digest(candles, request.prediction_time_t_ms, request.lookback_days)
        except InsufficientHistoryError as error:
            job.status = AnalysisStatus.INSUFFICIENT_HISTORY.value
            job.error_message = str(error)
        self.job_repo.save(job)
        if run_immediately and job.status == AnalysisStatus.PREPARING_FEED.value:
            return self.run_pipeline(job.id, snapshot_candles=snapshot_candles)
        return model_to_dto(job, leakage_banner=request.mode == AnalysisMode.RETROSPECTIVE)

    def run_pipeline(self, job_id, mock_mode=False, custom_mock_response=None, snapshot_candles=None):
        job = self.job_repo.get_by_id(job_id)
        if not job:
            raise ValueError(f"Job '{job_id}' not found.")
        if mock_mode or custom_mock_response is not None:
            job.status = AnalysisStatus.FAILED.value
            job.error_message = "Production mock forecasts are disabled"
            self.job_repo.save(job)
            return model_to_dto(job, leakage_banner=job.mode == "RETROSPECTIVE")
        snapshot = self.snapshot_repo.get_by_id(job.snapshot_id)
        if not snapshot:
            raise ValueError(f"Snapshot with ID '{job.snapshot_id}' not found.")
        try:
            options = json.loads(job.evidence_envelope_json or "{}")
            lookback = options.get("lookback_days", 14)
            candles = self._window(snapshot, job.prediction_time_t_ms, lookback, job.horizon_minutes, snapshot_candles)
            job.status = AnalysisStatus.ANALYZING.value
            self.job_repo.save(job)
            envelope = run_forecast_pipeline(candles, job.prediction_time_t_ms, job.horizon_minutes,
                                             job.purchase_price_p, lookback, self.gemini_adapter)
            answer = envelope["answer"]
            usage = envelope["token_usage"]
            job.direction = answer["direction"]
            job.rationale = " ".join(reason["text"] for reason in answer["reasons"])
            job.evidence_times_json = "[]"
            job.raw_output_json = json.dumps(answer, ensure_ascii=False)
            job.evidence_envelope_json = json.dumps(envelope, ensure_ascii=False, allow_nan=False)
            job.key_index = usage.get("key_index")
            job.prompt_tokens = usage.get("prompt_tokens")
            job.completion_tokens = usage.get("completion_tokens")
            job.status = AnalysisStatus.READY.value
            job.error_message = None
        except InsufficientHistoryError as error:
            job.status = AnalysisStatus.INSUFFICIENT_HISTORY.value
            job.error_message = str(error)
        except Exception as error:
            job.status = AnalysisStatus.FAILED.value
            job.error_message = f"Forecast failed: {type(error).__name__}"
        job.updated_at = datetime.now(timezone.utc)
        self.job_repo.save(job)
        return model_to_dto(job, leakage_banner=job.mode == "RETROSPECTIVE")

    def record_user_vote(self, job_id, vote):
        job = self.job_repo.get_by_id(job_id)
        if not job:
            raise ValueError(f"Job '{job_id}' not found.")
        clean_vote = vote.strip().upper()
        if clean_vote not in ("UP", "DOWN"):
            raise ValueError(f"Invalid vote '{vote}'. Must be UP or DOWN.")
        if job.user_vote is not None and job.user_vote != clean_vote:
            raise ValueError(f"Vote for job '{job_id}' is already locked to '{job.user_vote}' and cannot be changed.")
        job.user_vote = clean_vote
        self.job_repo.save(job)
        return model_to_dto(job, leakage_banner=job.mode == "RETROSPECTIVE")

    def reveal_outcome(self, job_id):
        job = self.job_repo.get_by_id(job_id)
        if not job:
            raise ValueError(f"Job '{job_id}' not found.")
        if job.user_vote is None:
            raise ValueError("Phải khóa dự đoán của bạn trước khi xem kết quả thực tế.")
        target = job.prediction_time_t_ms + job.horizon_minutes * 60_000
        now_ms = int(time.time() * 1000)
        if job.mode == "PROSPECTIVE" and now_ms < target:
            dto = model_to_dto(job)
            dto.outcome = "PENDING"
            return dto
        snapshot = self.snapshot_repo.get_by_id(job.snapshot_id)
        if not snapshot:
            raise ValueError(f"Snapshot with ID '{job.snapshot_id}' not found.")
        candles = self._window(snapshot, job.prediction_time_t_ms, 14, job.horizon_minutes)
        result = evaluate_direction_outcome(candles, job.prediction_time_t_ms, job.horizon_minutes, job.purchase_price_p)
        job.outcome = result["outcome"]
        job.target_price = result["target_price"]
        job.is_revealed = True
        job.outcome_evaluated_at_ms = now_ms
        self.job_repo.save(job)
        return model_to_dto(job, leakage_banner=job.mode == "RETROSPECTIVE")

    def get_job(self, job_id):
        job = self.job_repo.get_by_id(job_id)
        return model_to_dto(job, leakage_banner=job.mode == "RETROSPECTIVE") if job else None
