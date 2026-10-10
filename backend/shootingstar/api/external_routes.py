"""API endpoints for external model analysis jobs with strict fail-closed administrator gating."""

import logging
import os
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Query, status
from pydantic import BaseModel, Field

from shootingstar.adapters.db.repository import ExternalAnalysisJobRepository, SnapshotRepository
from shootingstar.adapters.db.session import get_db_session, load_env_file
from shootingstar.adapters.storage import SnapshotStorage
from shootingstar.application.external_analysis.contracts import (
    AnalysisMode,
    AnalysisStatus,
    ContextVariant,
    ExternalAnalysisRequest,
)
from shootingstar.application.external_analysis.service import ExternalAnalysisService

logger = logging.getLogger(__name__)

load_env_file()
router = APIRouter(prefix="/external-analysis", tags=["External Analysis"])


class CreateAnalysisJobRequest(BaseModel):
    snapshot_id: str
    prediction_time_t_ms: int
    purchase_price_p: float
    horizon_minutes: int = 30
    context_variant: str = "A"  # "A" or "B"
    mode: str = "RETROSPECTIVE"  # "RETROSPECTIVE" or "PROSPECTIVE"
    mock_mode: bool = False

class RecordVoteRequest(BaseModel):
    vote: str = Field(..., description="'UP' or 'DOWN'")


def verify_admin_authorization(x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key")) -> None:
    """Strict server-side administrator gating.

    FAIL-CLOSED INVARIANTS:
    1. If SHOOTINGSTAR_EXTERNAL_API_ENABLED != 'true', all external analysis endpoints are blocked (503).
    2. If SHOOTINGSTAR_ADMIN_KEY is not configured or x_admin_key does not match, calls are blocked (403).
    """
    is_enabled = os.environ.get("SHOOTINGSTAR_EXTERNAL_API_ENABLED", "").lower() in ("true", "1", "yes")
    if not is_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "External model API endpoints are gated pending operator authentication "
                "and budget approval. External model API is disabled by default."
            ),
        )

    expected_key = os.environ.get("SHOOTINGSTAR_ADMIN_KEY", "").strip()
    if not expected_key or not x_admin_key or x_admin_key != expected_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator authentication required via X-Admin-Key header.",
        )


@router.post("/jobs", status_code=status.HTTP_202_ACCEPTED)
def create_external_analysis_job(
    req: CreateAnalysisJobRequest,
    background_tasks: BackgroundTasks,
    mock_mode: bool = Query(False),
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
):
    """Creates and triggers an external analysis job. Returns HTTP 202 Accepted. Protected behind admin gate."""
    verify_admin_authorization(x_admin_key)

    try:
        variant = ContextVariant(req.context_variant.upper())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid context variant '{req.context_variant}'. Must be 'A' or 'B'.")

    try:
        mode = AnalysisMode(req.mode.upper())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid analysis mode '{req.mode}'. Must be 'RETROSPECTIVE' or 'PROSPECTIVE'.")

    is_mock = mock_mode or req.mock_mode
    storage = SnapshotStorage()
    with get_db_session() as session:
        job_repo = ExternalAnalysisJobRepository(session)
        snap_repo = SnapshotRepository(session)
        service = ExternalAnalysisService(
            job_repository=job_repo,
            snapshot_repository=snap_repo,
            snapshot_storage=storage,
        )

        domain_req = ExternalAnalysisRequest(
            snapshot_id=req.snapshot_id,
            prediction_time_t_ms=req.prediction_time_t_ms,
            purchase_price_p=req.purchase_price_p,
            horizon_minutes=req.horizon_minutes,
            context_variant=variant,
            mode=mode,
        )

        try:
            job_dto = service.create_analysis_job(request=domain_req, mock_mode=is_mock, run_immediately=False)
            session.commit()
        except ValueError as e:
            session.rollback()
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            session.rollback()
            raise HTTPException(status_code=500, detail=f"External analysis failed: {e}")

    if job_dto.status == AnalysisStatus.PREPARING_FEED.value:
        background_tasks.add_task(_execute_job_in_background, job_dto.id, is_mock)

    return job_dto


def _execute_job_in_background(job_id: str, is_mock: bool) -> None:
    """Runs pipeline stages in background using an isolated DB session."""
    try:
        storage = SnapshotStorage()
        with get_db_session() as session:
            job_repo = ExternalAnalysisJobRepository(session)
            snap_repo = SnapshotRepository(session)
            service = ExternalAnalysisService(
                job_repository=job_repo,
                snapshot_repository=snap_repo,
                snapshot_storage=storage,
            )
            service.run_pipeline(job_id=job_id, mock_mode=is_mock)
            session.commit()
    except Exception as e:
        logger.error("Background job execution error for %s: %s", job_id, e)
        try:
            with get_db_session() as session:
                job_repo = ExternalAnalysisJobRepository(session)
                job = job_repo.get_by_id(job_id)
                if job:
                    job.status = AnalysisStatus.FAILED.value
                    job.error_message = f"Lỗi thực thi nền: {e}"
                    job_repo.save(job)
                    session.commit()
        except Exception:
            pass

@router.get("/jobs/{job_id}")
def get_external_analysis_job(
    job_id: str,
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
):
    """Retrieves an external analysis job. Strictly protected behind admin gate.

    CRITICAL INVARIANT: Outcome is hidden (None) unless explicitly revealed!
    """
    verify_admin_authorization(x_admin_key)

    storage = SnapshotStorage()
    with get_db_session() as session:
        job_repo = ExternalAnalysisJobRepository(session)
        snap_repo = SnapshotRepository(session)
        service = ExternalAnalysisService(
            job_repository=job_repo,
            snapshot_repository=snap_repo,
            snapshot_storage=storage,
        )
        job_dto = service.get_job(job_id)
        if not job_dto:
            raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
        return job_dto


@router.post("/jobs/{job_id}/vote")
def record_user_vote(
    job_id: str,
    req: RecordVoteRequest,
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
):
    """Submits user's UP or DOWN prediction vote. Strictly protected behind admin gate.

    CRITICAL INVARIANT: User vote is isolated and never fed into AI or training pipeline.
    """
    verify_admin_authorization(x_admin_key)

    storage = SnapshotStorage()
    with get_db_session() as session:
        job_repo = ExternalAnalysisJobRepository(session)
        snap_repo = SnapshotRepository(session)
        service = ExternalAnalysisService(
            job_repository=job_repo,
            snapshot_repository=snap_repo,
            snapshot_storage=storage,
        )
        try:
            updated_dto = service.record_user_vote(job_id, req.vote)
            session.commit()
            return updated_dto
        except ValueError as e:
            session.rollback()
            err_msg = str(e)
            if "already locked" in err_msg:
                raise HTTPException(status_code=409, detail=err_msg)
            if "not found" in err_msg.lower():
                raise HTTPException(status_code=404, detail=err_msg)
            raise HTTPException(status_code=400, detail=err_msg)


@router.post("/jobs/{job_id}/reveal")
def reveal_external_analysis_outcome(
    job_id: str,
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
):
    """Reveals evaluated outcome against purchase price P at t + 30m. Strictly protected behind admin gate."""
    verify_admin_authorization(x_admin_key)

    storage = SnapshotStorage()
    with get_db_session() as session:
        job_repo = ExternalAnalysisJobRepository(session)
        snap_repo = SnapshotRepository(session)
        service = ExternalAnalysisService(
            job_repository=job_repo,
            snapshot_repository=snap_repo,
            snapshot_storage=storage,
        )
        try:
            revealed_dto = service.reveal_outcome(job_id)
            session.commit()
            return revealed_dto
        except ValueError as e:
            session.rollback()
            err_msg = str(e)
            if "not found" in err_msg.lower():
                raise HTTPException(status_code=404, detail=err_msg)
            raise HTTPException(status_code=400, detail=err_msg)
