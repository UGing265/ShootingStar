"""External analysis orchestration service connecting storage, causal context, Gemini adapter, verifier, and repository."""

import hashlib
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
    build_feed_contract,
    extract_causal_window,
    feed_contract_to_dict,
)
from shootingstar.application.external_analysis.research_agent import (
    ResearchAgent,
    research_contract_to_dict,
)
from shootingstar.application.external_analysis.verifier import ExternalAnalysisVerifier
from shootingstar.application.patterns import (
    evaluate_pattern_diagnostics,
    pattern_diagnostics_to_dict,
)
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
        research_agent: Optional[ResearchAgent] = None,
        approved_lessons: Optional[List[Dict[str, Any]]] = None,
    ):
        self.job_repo = job_repository
        self.snapshot_repo = snapshot_repository
        self.snapshot_storage = snapshot_storage
        self.gemini_adapter = gemini_adapter or GeminiModelAdapter()
        self.research_agent = research_agent or ResearchAgent(lesson_service=None, model_adapter=self.gemini_adapter)  # type: ignore
        self.approved_lessons = approved_lessons or []
    def create_analysis_job(
        self,
        request: ExternalAnalysisRequest,
        mock_mode: bool = False,
        custom_mock_response: Optional[Dict[str, Any]] = None,
        run_immediately: bool = True,
    ) -> ExternalAnalysisJobDTO:
        """Creates an analysis job and sets initial state to PREPARING_FEED."""
        snap_rec = self.snapshot_repo.get_by_id(request.snapshot_id)
        if not snap_rec:
            raise ValueError(f"Snapshot with ID '{request.snapshot_id}' not found.")

        candles = self.snapshot_storage.load_snapshot(Path(snap_rec.file_path))
        if not candles:
            raise ValueError(f"Snapshot data file for '{request.snapshot_id}' is empty or unreadable.")

        job_id = str(uuid.uuid4())
        now_dt = datetime.now(timezone.utc)

        # Pre-flight check: Causal 6h window extraction fails closed before provider calls
        try:
            extract_causal_window(
                candles=candles,
                t_ms=request.prediction_time_t_ms,
                window_hours=6.0,
            )
        except InsufficientHistoryError as e:
            logger.info("Insufficient history for t=%s: %s", request.prediction_time_t_ms, e)
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

        # Initial job state: PREPARING_FEED
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
            model_id=self.gemini_adapter.model_name,
            status=AnalysisStatus.PREPARING_FEED.value,
            is_revealed=False,
            created_at=now_dt,
            updated_at=now_dt,
        )
        self.job_repo.save(job)

        if run_immediately:
            return self.run_pipeline(
                job_id=job_id,
                mock_mode=mock_mode,
                custom_mock_response=custom_mock_response,
            )

        return self._model_to_dto(job, leakage_banner=(request.mode == AnalysisMode.RETROSPECTIVE))

    def run_pipeline(
        self,
        job_id: str,
        mock_mode: bool = False,
        custom_mock_response: Optional[Dict[str, Any]] = None,
    ) -> ExternalAnalysisJobDTO:
        """Executes multi-stage orchestration pipeline: Feed -> Analyze -> Research -> Match -> Synthesize."""
        job = self.job_repo.get_by_id(job_id)
        if not job:
            raise ValueError(f"Job '{job_id}' not found.")

        snap_rec = self.snapshot_repo.get_by_id(job.snapshot_id)
        if not snap_rec:
            raise ValueError(f"Snapshot with ID '{job.snapshot_id}' not found.")

        candles = self.snapshot_storage.load_snapshot(Path(snap_rec.file_path))
        if not candles:
            raise ValueError(f"Snapshot data file for '{job.snapshot_id}' is empty or unreadable.")

        stages_records: List[Dict[str, Any]] = []

        # -------------------------------------------------------------
        # STAGE 1: PREPARING_FEED
        # -------------------------------------------------------------
        t0_iso = datetime.now(timezone.utc).isoformat()
        try:
            feed_contract = build_feed_contract(
                candles=candles,
                snapshot_id=snap_rec.id,
                snapshot_checksum=snap_rec.sha256,
                prediction_time_t_ms=job.prediction_time_t_ms,
                purchase_price_p=job.purchase_price_p,
                horizon_minutes=job.horizon_minutes,
            )
        except InsufficientHistoryError as e:
            job.status = AnalysisStatus.INSUFFICIENT_HISTORY.value
            job.error_message = str(e)
            self.job_repo.save(job)
            return self._model_to_dto(job)

        feed_dict = feed_contract_to_dict(feed_contract)
        stages_records.append({
            "stage_name": "PREPARING_FEED",
            "role": "Data Provider (Python)",
            "status": "COMPLETED",
            "started_at_iso": t0_iso,
            "ended_at_iso": datetime.now(timezone.utc).isoformat(),
            "output_hash": feed_contract.feed_hash,
        })

        # -------------------------------------------------------------
        # STAGE 2: ANALYZING (Preliminary hypothesis)
        # -------------------------------------------------------------
        job.status = AnalysisStatus.ANALYZING.value
        self.job_repo.save(job)
        t1_iso = datetime.now(timezone.utc).isoformat()

        hyp_contract = self.gemini_adapter.analyze_preliminary(
            feed_payload=feed_dict,
            mock_mode=mock_mode,
        )
        hyp_dict = {
            "hypothesis_id": hyp_contract.hypothesis_id,
            "feed_id": hyp_contract.feed_id,
            "feed_hash": hyp_contract.feed_hash,
            "observations": [
                {
                    "claim_id": o.claim_id,
                    "description": o.description,
                    "feature_ids": o.feature_ids,
                    "candle_ids": o.candle_ids,
                }
                for o in hyp_contract.observations
            ],
            "candidates": [
                {
                    "pattern_name": c.pattern_name,
                    "candle_ids": c.candle_ids,
                    "rationale": c.rationale,
                    "unresolved_context": c.unresolved_context,
                }
                for c in hyp_contract.candidates
            ],
            "missing_information": hyp_contract.missing_information,
            "questions_for_research": hyp_contract.questions_for_research,
        }
        stages_records.append({
            "stage_name": "ANALYZING",
            "role": "Preliminary Analyst (AI)",
            "status": "COMPLETED",
            "started_at_iso": t1_iso,
            "ended_at_iso": datetime.now(timezone.utc).isoformat(),
            "output_hash": hashlib.sha256(json.dumps(hyp_dict).encode("utf-8")).hexdigest()[:16],
        })

        # -------------------------------------------------------------
        # STAGE 3: RESEARCHING (Grounded search)
        # -------------------------------------------------------------
        job.status = AnalysisStatus.RESEARCHING.value
        self.job_repo.save(job)
        t2_iso = datetime.now(timezone.utc).isoformat()

        try:
            res_contract = self.research_agent.conduct_job_research(
                hypothesis=hyp_contract,
                job_id=job.id,
                feed_hash=feed_contract.feed_hash,
                mock_mode=mock_mode,
            )
            res_dict = research_contract_to_dict(res_contract)
            stages_records.append({
                "stage_name": "RESEARCHING",
                "role": "Research Agent (Google Search Grounding)",
                "status": "COMPLETED",
                "started_at_iso": t2_iso,
                "ended_at_iso": datetime.now(timezone.utc).isoformat(),
                "search_provider": res_contract.search_provider,
                "queries_executed": res_contract.queries_executed,
            })
        except Exception as e:
            logger.warning("Research stage encountered error for job %s: %s", job.id, e)
            job.status = AnalysisStatus.RESEARCH_INCOMPLETE.value
            job.error_message = f"Grounded research không hoàn tất: {e}"
            self.job_repo.save(job)
            return self._model_to_dto(job)

        # -------------------------------------------------------------
        # STAGE 4: MATCHING (Deterministic Python criteria diagnostics)
        # -------------------------------------------------------------
        job.status = AnalysisStatus.MATCHING.value
        self.job_repo.save(job)
        t3_iso = datetime.now(timezone.utc).isoformat()

        # Sliced causal candles for diagnostics (zero future)
        causal_candles = [
            c for c in candles
            if c.close_time_ms <= job.prediction_time_t_ms
        ]
        diagnostics = evaluate_pattern_diagnostics(
            candles=causal_candles,
            target_index=-1,
            feed_hash=feed_contract.feed_hash,
        )
        diagnostics_dicts = [pattern_diagnostics_to_dict(d) for d in diagnostics]
        stages_records.append({
            "stage_name": "MATCHING",
            "role": "Pattern Diagnostic Engine (Python)",
            "status": "COMPLETED",
            "started_at_iso": t3_iso,
            "ended_at_iso": datetime.now(timezone.utc).isoformat(),
            "patterns_checked": len(diagnostics_dicts),
        })

        # -------------------------------------------------------------
        # STAGE 5: SYNTHESIZING (Report synthesis)
        # -------------------------------------------------------------
        job.status = AnalysisStatus.SYNTHESIZING.value
        self.job_repo.save(job)
        t4_iso = datetime.now(timezone.utc).isoformat()

        report_payload = self.gemini_adapter.synthesize_evidence_report(
            feed_dict=feed_dict,
            hypothesis_dict=hyp_dict,
            research_dict=res_dict,
            diagnostics_list=diagnostics_dicts,
            purchase_price_p=job.purchase_price_p,
            mock_mode=mock_mode,
            custom_mock=custom_mock_response,
        )
        stages_records.append({
            "stage_name": "SYNTHESIZING",
            "role": "Evidence Synthesizer (AI)",
            "status": "COMPLETED",
            "started_at_iso": t4_iso,
            "ended_at_iso": datetime.now(timezone.utc).isoformat(),
        })

        direction_str = report_payload.get("direction", "ABSTAIN").strip().upper()
        if direction_str not in ("UP", "DOWN", "ABSTAIN"):
            direction_str = "ABSTAIN"

        final_status = AnalysisStatus.READY if direction_str != "ABSTAIN" else AnalysisStatus.ABSTAIN

        envelope = {
            "protocol_version": "evidence-pipeline-v1",
            "feed": feed_dict,
            "stages": stages_records,
            "hypothesis": hyp_dict,
            "research": res_dict,
            "diagnostics": diagnostics_dicts,
            "report_sections": report_payload.get("sections", {}),
            "final_direction": direction_str,
            "probability_up": None,
            "probability_down": None,
        }

        now_dt = datetime.now(timezone.utc)
        job.status = final_status.value
        job.direction = direction_str
        job.rationale = report_payload.get("rationale", "")
        job.evidence_times_json = json.dumps(report_payload.get("evidence_candle_times", []))
        job.lesson_ids_json = json.dumps(report_payload.get("lesson_ids", []))
        job.raw_output_json = json.dumps(report_payload)
        job.evidence_envelope_json = json.dumps(envelope)
        job.prompt_tokens = report_payload.get("prompt_tokens")
        job.completion_tokens = report_payload.get("completion_tokens")
        job.estimated_cost_usd = report_payload.get("estimated_cost_usd")
        job.updated_at = now_dt
        self.job_repo.save(job)

        is_retrospective = (job.mode == "RETROSPECTIVE")
        return self._model_to_dto(job, leakage_banner=is_retrospective)
    def record_user_vote(self, job_id: str, vote: str) -> ExternalAnalysisJobDTO:
        """Records isolated user vote (UP or DOWN). Never fed to model or training."""
        job = self.job_repo.get_by_id(job_id)
        if not job:
            raise ValueError(f"Job '{job_id}' not found.")

        clean_vote = vote.strip().upper()
        if clean_vote not in ("UP", "DOWN"):
            raise ValueError(f"Invalid vote '{vote}'. Must be UP or DOWN.")
        if job.user_vote is not None:
            if job.user_vote == clean_vote:
                return self._model_to_dto(job, leakage_banner=(job.mode == "RETROSPECTIVE"))
            raise ValueError(f"Vote for job '{job_id}' is already locked to '{job.user_vote}' and cannot be changed.")

        job.user_vote = clean_vote
        self.job_repo.save(job)
        return self._model_to_dto(job, leakage_banner=(job.mode == "RETROSPECTIVE"))

    def reveal_outcome(self, job_id: str) -> ExternalAnalysisJobDTO:
        """Reveals and matures outcome evaluated against purchase price P at t + 30m."""
        job = self.job_repo.get_by_id(job_id)
        if not job:
            raise ValueError(f"Job '{job_id}' not found.")
        if job.user_vote is None:
            raise ValueError("Phải khóa dự đoán của bạn trước khi xem kết quả thực tế.")

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
        envelope_data = None
        stages_data = None
        if job.evidence_envelope_json:
            try:
                envelope_data = json.loads(job.evidence_envelope_json)
                stages_data = envelope_data.get("stages")
            except Exception:
                pass

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
            evidence_envelope=envelope_data,
            stages=stages_data,
        )
