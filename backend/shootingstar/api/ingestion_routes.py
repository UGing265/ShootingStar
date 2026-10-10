"""FastAPI routes and background execution for market data ingestion jobs."""

from datetime import datetime, timezone
import logging
import threading
import time
from typing import Dict, List, Optional
import uuid

from fastapi import APIRouter, HTTPException, status

import hashlib
from shootingstar.api.schemas import (
    CandleDTO,
    CreateIngestionJobRequest,
    IngestionJobResponse,
    PreviewIngestionRequest,
    PreviewIngestionResponse,
)
from shootingstar.application.ingestion import (
    execute_and_persist_ingestion,
    preview_ingestion,
)
from shootingstar.domain.exceptions import DomainError
from shootingstar.domain.models import Timeframe

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ingestion", tags=["ingestion"])


class IngestionJobManager:
    """Thread-safe manager for tracking bounded ingestion jobs."""

    def __init__(self):
        self._lock = threading.Lock()
        self._jobs: Dict[str, dict] = {}

    def get_job(self, job_id: str) -> Optional[dict]:
        with self._lock:
            job = self._jobs.get(job_id)
            return dict(job) if job else None

    def list_jobs(self, limit: int = 50) -> List[dict]:
        with self._lock:
            sorted_jobs = sorted(
                self._jobs.values(),
                key=lambda j: j["created_at"],
                reverse=True,
            )
            return [dict(j) for j in sorted_jobs[:limit]]

    def is_any_running(self) -> bool:
        with self._lock:
            return any(j["status"] == "RUNNING" for j in self._jobs.values())

    def create_job(self, symbol: str, timeframe: str, start_time_ms: int, end_time_ms: int) -> dict:
        with self._lock:
            if any(j["status"] == "RUNNING" for j in self._jobs.values()):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="An ingestion job is already running. Please wait for it to finish.",
                )

            job_id = str(uuid.uuid4())
            now_iso = datetime.now(timezone.utc).isoformat()
            job_data = {
                "job_id": job_id,
                "symbol": symbol,
                "timeframe": timeframe,
                "start_time_ms": start_time_ms,
                "end_time_ms": end_time_ms,
                "status": "RUNNING",
                "created_at": now_iso,
                "completed_at": None,
                "snapshot_id": None,
                "valid_candles_count": None,
                "coverage_ratio": None,
                "is_pristine": None,
                "error_message": None,
            }
            self._jobs[job_id] = job_data
            return dict(job_data)

    def update_job_success(
        self,
        job_id: str,
        snapshot_id: str,
        valid_candles_count: int,
        coverage_ratio: float,
        is_pristine: bool,
    ) -> None:
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id]["status"] = "COMPLETED"
                self._jobs[job_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
                self._jobs[job_id]["snapshot_id"] = snapshot_id
                self._jobs[job_id]["valid_candles_count"] = valid_candles_count
                self._jobs[job_id]["coverage_ratio"] = coverage_ratio
                self._jobs[job_id]["is_pristine"] = is_pristine

    def update_job_failure(self, job_id: str, error_message: str) -> None:
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id]["status"] = "FAILED"
                self._jobs[job_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
                self._jobs[job_id]["error_message"] = error_message

class PreviewTokenManager:
    """Thread-safe manager for preview tokens with 15-minute TTL and input binding."""

    def __init__(self, ttl_seconds: int = 900):
        self._lock = threading.Lock()
        self._previews: Dict[str, dict] = {}
        self._ttl_seconds = ttl_seconds

    def register_preview(
        self,
        symbol: str,
        timeframe: str,
        start_time_ms: int,
        end_time_ms: int,
        sample_count: int,
    ) -> str:
        with self._lock:
            now = time.time()
            expired_keys = [k for k, v in self._previews.items() if now - v["created_at"] > self._ttl_seconds]
            for k in expired_keys:
                del self._previews[k]

            token_seed = f"{symbol}:{timeframe}:{start_time_ms}:{end_time_ms}:{now}:{uuid.uuid4().hex[:8]}"
            token = hashlib.sha256(token_seed.encode()).hexdigest()[:24]
            self._previews[token] = {
                "symbol": symbol,
                "timeframe": timeframe,
                "start_time_ms": start_time_ms,
                "end_time_ms": end_time_ms,
                "sample_count": sample_count,
                "created_at": now,
            }
            return token

    def validate_and_consume(
        self,
        token: str,
        symbol: str,
        timeframe: str,
        start_time_ms: int,
        end_time_ms: int,
    ) -> None:
        with self._lock:
            now = time.time()
            info = self._previews.get(token)
            if not info:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Preview token is invalid or expired. Please preview the range before confirming ingestion.",
                )
            if (now - info["created_at"]) > self._ttl_seconds:
                del self._previews[token]
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Preview token has expired (> 15 minutes). Please preview again.",
                )
            if (
                info["symbol"] != symbol
                or info["timeframe"] != timeframe
                or info["start_time_ms"] != start_time_ms
                or info["end_time_ms"] != end_time_ms
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Ingestion parameters do not match preview token. Parameters were modified after preview.",
                )


job_manager = IngestionJobManager()
preview_token_manager = PreviewTokenManager()

def _run_ingestion_background(job_id: str, symbol: str, timeframe: str, start_time_ms: int, end_time_ms: int):
    try:
        logger.info("Executing background ingestion job %s (%s %s)", job_id, symbol, timeframe)
        result, run_id, snapshot_id = execute_and_persist_ingestion(
            symbol=symbol,
            timeframe=timeframe,
            start_time_ms=start_time_ms,
            end_time_ms=end_time_ms,
        )
        report = result.report
        job_manager.update_job_success(
            job_id=job_id,
            snapshot_id=snapshot_id,
            valid_candles_count=report.valid_candles_count,
            coverage_ratio=report.coverage_ratio,
            is_pristine=report.is_pristine,
        )
        logger.info("Ingestion job %s completed successfully: snapshot=%s", job_id, snapshot_id)
    except Exception as exc:
        logger.exception("Ingestion job %s failed: %s", job_id, exc)
        raw_err = str(exc)
        # Strictly sanitize error message: avoid leaking local filesystem paths or database credentials
        if "postgresql://" in raw_err or "sqlite://" in raw_err or "@" in raw_err:
            safe_err = "Database connection or persistence error."
        elif ("\\" in raw_err or "/" in raw_err) and (":" in raw_err or "home" in raw_err or "Users" in raw_err):
            safe_err = "Storage file I/O error."
        else:
            safe_err = raw_err[:200]
        job_manager.update_job_failure(job_id=job_id, error_message=safe_err)

def validate_ingestion_bounds(symbol: str, timeframe: str, start_time_ms: int, end_time_ms: int) -> Tuple[Timeframe, int]:
    if symbol != "BTCUSDT":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only BTCUSDT is supported, got: {symbol}",
        )

    if timeframe not in ("1m", "5m"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported timeframe: {timeframe}. Must be '1m' or '5m'.",
        )

    if start_time_ms >= end_time_ms:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_time_ms must be strictly less than end_time_ms",
        )

    tf = Timeframe(timeframe)
    now_ms = int(time.time() * 1000)
    max_closed_end_ms = now_ms - (now_ms % tf.duration_ms) - 1

    if start_time_ms > max_closed_end_ms:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_time_ms cannot be in the future or after closed candle boundary.",
        )

    clamped_end_ms = min(end_time_ms, max_closed_end_ms)

    # Max bounded range check (65 days max to prevent timeout / unbounded API rate quota exhaustion)
    max_span_ms = 65 * 86400 * 1000
    if (clamped_end_ms - start_time_ms) > max_span_ms:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Time range cannot exceed 65 days. Requested: {(clamped_end_ms - start_time_ms) / 86400000:.1f} days.",
        )

    # Minimum span: at least 1 candle
    if (clamped_end_ms - start_time_ms) < tf.duration_ms:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Time range must span at least 1 candle.",
        )

    return tf, clamped_end_ms


@router.post("/preview", response_model=PreviewIngestionResponse)
def preview_ingestion_endpoint(req: PreviewIngestionRequest):
    """Previews an ingestion window without persisting raw bytes, parquet snapshots, or database records."""
    tf, clamped_end_ms = validate_ingestion_bounds(
        symbol=req.symbol,
        timeframe=req.timeframe,
        start_time_ms=req.start_time_ms,
        end_time_ms=req.end_time_ms,
    )
    try:
        sample_candles, est_count, quality = preview_ingestion(
            symbol=req.symbol,
            timeframe=req.timeframe,
            start_time_ms=req.start_time_ms,
            end_time_ms=clamped_end_ms,
            sample_limit=50,
        )
    except DomainError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))
    except Exception as err:
        logger.exception("Preview ingestion failed: %s", err)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to fetch preview from Binance Spot API.",
        )

    token = preview_token_manager.register_preview(
        symbol=req.symbol,
        timeframe=req.timeframe,
        start_time_ms=req.start_time_ms,
        end_time_ms=clamped_end_ms,
        sample_count=len(sample_candles),
    )
    return PreviewIngestionResponse(
        symbol=req.symbol,
        timeframe=req.timeframe,
        start_time_ms=req.start_time_ms,
        end_time_ms=clamped_end_ms,
        estimated_candle_count=est_count,
        sampled_candles_count=len(sample_candles),
        data_source="Binance Spot REST API (GET /api/v3/klines)",
        is_bounded=True,
        quality_status=quality,
        sample_candles=[
            CandleDTO(
                open_time_ms=c.open_time_ms,
                close_time_ms=c.close_time_ms,
                open=c.open,
                high=c.high,
                low=c.low,
                close=c.close,
                volume=c.volume,
                quote_volume=c.quote_volume,
                trades_count=c.trades_count,
            )
            for c in sample_candles
        ],
        preview_token=token,
    )


@router.post("/jobs", response_model=IngestionJobResponse, status_code=status.HTTP_202_ACCEPTED)
def create_ingestion_job(req: CreateIngestionJobRequest):
    """Triggers an ingestion job from Binance Spot within explicit time bounds."""
    tf, clamped_end_ms = validate_ingestion_bounds(
        symbol=req.symbol,
        timeframe=req.timeframe,
        start_time_ms=req.start_time_ms,
        end_time_ms=req.end_time_ms,
    )
    preview_token_manager.validate_and_consume(
        token=req.preview_token,
        symbol=req.symbol,
        timeframe=req.timeframe,
        start_time_ms=req.start_time_ms,
        end_time_ms=clamped_end_ms,
    )

    job_data = job_manager.create_job(
        symbol=req.symbol,
        timeframe=req.timeframe,
        start_time_ms=req.start_time_ms,
        end_time_ms=clamped_end_ms,
    )

    try:
        thread = threading.Thread(
            target=_run_ingestion_background,
            args=(job_data["job_id"], req.symbol, req.timeframe, req.start_time_ms, clamped_end_ms),
            daemon=True,
        )
        thread.start()
    except Exception as thread_err:
        logger.exception("Failed to start ingestion thread for job %s: %s", job_data["job_id"], thread_err)
        job_manager.update_job_failure(job_data["job_id"], "Failed to initialize background worker.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start ingestion task.",
        )

    return IngestionJobResponse(**job_data)


@router.get("/jobs", response_model=List[IngestionJobResponse])
def list_ingestion_jobs(limit: int = 20):
    """Lists recent ingestion jobs."""
    jobs = job_manager.list_jobs(limit=limit)
    return [IngestionJobResponse(**j) for j in jobs]


@router.get("/jobs/{job_id}", response_model=IngestionJobResponse)
def get_ingestion_job(job_id: str):
    """Retrieves current status and result of an ingestion job."""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ingestion job {job_id} not found",
        )
    return IngestionJobResponse(**job)
