"""FastAPI routes for Causal Historical Replay sessions."""

import logging
from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException, status

from shootingstar.adapters.db.repository import SnapshotRepository
from shootingstar.adapters.db.session import get_db_session
from shootingstar.api.schemas import (
    CandleDTO,
    CreateSimulationJobRequest,
    SimulationAIPredictionDTO,
    SimulationJobResponse,
    SimulationOutcomeDTO,
    SimulationUserVoteDTO,
    SimulationUserVoteRequest,
)
from shootingstar.application.replay import (
    SimulationJob,
    SimulationJobManager,
)
from shootingstar.domain.exceptions import DomainError
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/replay", tags=["replay"])

simulation_manager = SimulationJobManager()


def _to_job_response(job: SimulationJob) -> SimulationJobResponse:
    ai_dto = (
        SimulationAIPredictionDTO(
            predicted_direction=job.ai_prediction.predicted_direction,
            probability_up=job.ai_prediction.probability_up,
            probability_down=job.ai_prediction.probability_down,
            model_version=job.ai_prediction.model_version,
            model_cutoff_ms=job.ai_prediction.model_cutoff_ms,
            evidence_summary=job.ai_prediction.evidence_summary,
            is_calibrated=job.ai_prediction.is_calibrated,
        )
        if job.ai_prediction
        else None
    )
    user_dto = (
        SimulationUserVoteDTO(
            user_direction=job.user_vote.user_direction,
            voted_at_utc=job.user_vote.voted_at_utc,
            is_locked=job.user_vote.is_locked,
        )
        if job.user_vote
        else None
    )
    outcome_dto = (
        SimulationOutcomeDTO(
            status=job.outcome.status,
            horizon_time_ms=job.outcome.horizon_time_ms,
            future_price=job.outcome.future_price,
            price_change_pct=job.outcome.price_change_pct,
            market_direction=job.outcome.market_direction,
            ai_is_correct=job.outcome.ai_is_correct,
            user_is_correct=job.outcome.user_is_correct,
            unscorable_reason=job.outcome.unscorable_reason,
            revealed_at_utc=job.outcome.revealed_at_utc,
        )
        if job.outcome
        else None
    )
    return SimulationJobResponse(
        job_id=job.job_id,
        snapshot_id=job.snapshot_id,
        symbol=job.symbol,
        timeframe=job.timeframe,
        buy_time_ms=job.buy_time_ms,
        buy_price=job.buy_price,
        candle_close_at_buy=job.candle_close_at_buy,
        price_offset_pct=job.price_offset_pct,
        horizon_minutes=job.horizon_minutes,
        status=job.status,
        created_at_utc=job.created_at_utc,
        ai_prediction=ai_dto,
        user_vote=user_dto,
        outcome=outcome_dto,
    )

@router.post("/jobs", response_model=SimulationJobResponse, status_code=status.HTTP_201_CREATED)
def create_simulation_job(req: CreateSimulationJobRequest):
    """Creates a point-in-time simulation job with zero-lookahead AI prediction."""
    with get_db_session() as session:
        repo = SnapshotRepository(session)
        snap = repo.get_by_id(req.snapshot_id)
        if not snap:
            raise HTTPException(status_code=404, detail=f"Snapshot '{req.snapshot_id}' not found")
        snap_path = Path(snap.file_path)

    try:
        job = simulation_manager.create_job(
            snapshot_path=snap_path,
            snapshot_id=req.snapshot_id,
            buy_time_ms=req.buy_time_ms,
            buy_price=req.buy_price,
            horizon_minutes=req.horizon_minutes,
            model_artifact_hash=req.model_artifact_hash,
        )
        return _to_job_response(job)
    except DomainError as err:
        raise HTTPException(status_code=400, detail=str(err))


@router.get("/jobs/{job_id}", response_model=SimulationJobResponse)
def get_simulation_job(job_id: str):
    """Retrieves simulation job status and AI prediction. Strict zero-lookahead (outcome hidden until revealed)."""
    try:
        job = simulation_manager.get_job(job_id)
        return _to_job_response(job)
    except DomainError as err:
        raise HTTPException(status_code=404, detail=str(err))


@router.post("/jobs/{job_id}/vote", response_model=SimulationJobResponse)
def vote_simulation_job(job_id: str, req: SimulationUserVoteRequest):
    """Locks user's UP or DOWN prediction for this simulation job."""
    try:
        job = simulation_manager.record_vote(job_id, req.user_direction)
        return _to_job_response(job)
    except DomainError as err:
        raise HTTPException(status_code=400, detail=str(err))


@router.post("/jobs/{job_id}/reveal", response_model=SimulationJobResponse)
def reveal_simulation_outcome(job_id: str):
    """Reveals realized market outcome and independently scores AI and user predictions."""
    try:
        job = simulation_manager.get_job(job_id)
    except DomainError as err:
        raise HTTPException(status_code=404, detail=str(err))

    with get_db_session() as session:
        repo = SnapshotRepository(session)
        snap = repo.get_by_id(job.snapshot_id)
        if not snap:
            raise HTTPException(status_code=404, detail=f"Snapshot '{job.snapshot_id}' not found")
        snap_path = Path(snap.file_path)

    try:
        updated_job = simulation_manager.reveal_outcome(job_id, snap_path)
        return _to_job_response(updated_job)
    except DomainError as err:
        raise HTTPException(status_code=400, detail=str(err))
