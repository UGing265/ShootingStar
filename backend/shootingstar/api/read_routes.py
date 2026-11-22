"""FastAPI read-only contracts router for ShootingStar.

All routes enforce strict security invariants:
- No database credentials, connection strings, or raw exception traces.
- No local filesystem paths in responses.
- Strict limit bounds [1, 100] (up to 500 for bounded candles).
- Stable ordering with tie-break ID and cursor support.
"""

from datetime import datetime, timezone
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import JSONResponse
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from shootingstar.adapters.db.models import (
    IngestionRunModel,
    SnapshotModel,
)
from shootingstar.adapters.db.session import get_db_session
from shootingstar.adapters.storage import SnapshotStorage, resolve_snapshot_file_path
from shootingstar.api.schemas import (
    CandleDTO,
    HealthResponse,
    IngestionRunSummary,
    SnapshotQualityResponse,
    SnapshotSummary,
)
def _verify_snapshot_checksum(target_path: Path, expected_sha: str) -> bool:
    """Verifies file sha256 directly on disk to guarantee bit-for-bit cryptographic provenance."""
    try:
        hasher = hashlib.sha256()
        with target_path.open("rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        computed_sha = hasher.hexdigest()
        return computed_sha == expected_sha
    except Exception:
        return False

router = APIRouter()


def _parse_cursor_iso_id(cursor: Optional[str]) -> Optional[tuple[datetime, str]]:
    """Parses a cursor formatted as '<iso_time>|<id>'."""
    if not cursor:
        return None
    cursor = cursor.replace(" ", "+")
    parts = cursor.split("|", 1)
    if len(parts) != 2:
        raise HTTPException(status_code=422, detail="Invalid cursor format; expected '<iso_time>|<id>'")
    try:
        dt = datetime.fromisoformat(parts[0])
        return dt, parts[1]
    except Exception:
        raise HTTPException(status_code=422, detail="Invalid timestamp in cursor")


@router.get("/health", response_model=HealthResponse)
def get_health():
    """Health check endpoint verifying PostgreSQL connectivity without leaking secrets."""
    utc_str = datetime.now(timezone.utc).isoformat()
    try:
        with get_db_session() as session:
            session.execute(text("SELECT 1"))
        return HealthResponse(
            status="ok",
            database="connected",
            database_status="connected",
            engine="PostgreSQL",
            timestamp_utc=utc_str,
        )
    except Exception:
        # Strict invariant: Never leak raw exception or connection URL in health check
        return JSONResponse(
            status_code=503,
            content={
                "status": "degraded",
                "database": "offline",
                "database_status": "offline",
                "engine": "PostgreSQL",
                "timestamp_utc": utc_str,
            },
        )


@router.get("/ingestion-runs", response_model=List[IngestionRunSummary])
def list_ingestion_runs(
    limit: int = Query(default=20, ge=1, le=100),
    cursor: Optional[str] = Query(default=None),
):
    """Lists ingestion runs with stable ordering and cursor pagination."""
    parsed_cursor = _parse_cursor_iso_id(cursor)
    with get_db_session() as session:
        stmt = select(IngestionRunModel)
        if parsed_cursor:
            c_time, c_id = parsed_cursor
            stmt = stmt.where(
                (IngestionRunModel.created_at < c_time)
                | ((IngestionRunModel.created_at == c_time) & (IngestionRunModel.id < c_id))
            )
        stmt = stmt.order_by(IngestionRunModel.created_at.desc(), IngestionRunModel.id.desc()).limit(limit)
        runs = session.scalars(stmt).all()
        return [
            IngestionRunSummary(
                id=r.id,
                venue=r.venue,
                symbol=r.symbol,
                timeframe=r.timeframe,
                start_time_ms=r.start_time_ms,
                end_time_ms=r.end_time_ms,
                valid_candles_count=r.valid_candles_count,
                missing_intervals_count=r.missing_intervals_count,
                duplicate_candles_count=r.duplicate_candles_count,
                coverage_ratio=r.coverage_ratio,
                is_pristine=r.is_pristine,
                raw_files_count=r.raw_files_count,
                created_at=r.created_at.isoformat(),
            )
            for r in runs
        ]


@router.get("/snapshots", response_model=List[SnapshotSummary])
def list_snapshots(
    limit: int = Query(default=20, ge=1, le=100),
    cursor: Optional[str] = Query(default=None),
):
    """Lists snapshots with stable ordering and cursor pagination.

    Security invariant: file_path is strictly excluded.
    """
    parsed_cursor = _parse_cursor_iso_id(cursor)
    with get_db_session() as session:
        stmt = select(SnapshotModel)
        if parsed_cursor:
            c_time, c_id = parsed_cursor
            stmt = stmt.where(
                (SnapshotModel.created_at < c_time)
                | ((SnapshotModel.created_at == c_time) & (SnapshotModel.id < c_id))
            )
        stmt = stmt.order_by(SnapshotModel.created_at.desc(), SnapshotModel.id.desc()).limit(limit)
        snapshots = session.scalars(stmt).all()
        return [
            SnapshotSummary(
                id=s.id,
                ingestion_run_id=s.ingestion_run_id,
                venue=s.venue,
                symbol=s.symbol,
                timeframe=s.timeframe,
                candle_count=s.candle_count,
                start_time_ms=s.start_time_ms,
                end_time_ms=s.end_time_ms,
                sha256=s.sha256,
                created_at=s.created_at.isoformat(),
            )
            for s in snapshots
        ]


@router.get("/snapshots/{snapshot_id}/quality", response_model=SnapshotQualityResponse)
def get_snapshot_quality(snapshot_id: str):
    """Retrieves ingestion quality provenance for a snapshot."""
    with get_db_session() as session:
        stmt = select(SnapshotModel).where(
            (SnapshotModel.id == snapshot_id) | (SnapshotModel.sha256 == snapshot_id)
        )
        snap = session.scalars(stmt).first()
        if not snap:
            raise HTTPException(status_code=404, detail=f"Snapshot '{snapshot_id}' not found")

        run = None
        if snap.ingestion_run_id:
            run = session.get(IngestionRunModel, snap.ingestion_run_id)

        if run:
            quality_status = "VERIFIED_PRISTINE" if run.is_pristine else "VERIFIED_WITH_GAPS"
            coverage_ratio = run.coverage_ratio
            missing_intervals = run.missing_intervals_count
            duplicate_candles = run.duplicate_candles_count
            is_pristine = run.is_pristine
        else:
            quality_status = "UNAVAILABLE_NO_INGESTION_RUN"
            coverage_ratio = None
            missing_intervals = None
            duplicate_candles = None
            is_pristine = None

        return SnapshotQualityResponse(
            snapshot_id=snap.id,
            sha256=snap.sha256,
            venue=snap.venue,
            symbol=snap.symbol,
            timeframe=snap.timeframe,
            candle_count=snap.candle_count,
            start_time_ms=snap.start_time_ms,
            end_time_ms=snap.end_time_ms,
            ingestion_run_id=snap.ingestion_run_id,
            coverage_ratio=coverage_ratio,
            missing_intervals_count=missing_intervals,
            duplicate_candles_count=duplicate_candles,
            is_pristine=is_pristine,
            quality_status=quality_status,
            gap_list_status="UNAVAILABLE_NOT_PERSISTED",
            missing_timestamps=[],
            created_at=snap.created_at.isoformat(),
        )


@router.get("/snapshots/{snapshot_id}/candles", response_model=List[CandleDTO])
def get_snapshot_candles(
    snapshot_id: str,
    response: Response,
    start_ms: Optional[int] = Query(default=None, ge=0),
    end_ms: Optional[int] = Query(default=None, ge=0),
    limit: int = Query(default=100, ge=1, le=1500),
):
    """Extracts bounded candles from registered Parquet snapshot after verifying SHA-256."""
    if start_ms is not None and end_ms is not None and start_ms > end_ms:
        raise HTTPException(status_code=422, detail="start_ms must be <= end_ms")

    with get_db_session() as session:
        stmt = select(SnapshotModel).where(
            (SnapshotModel.id == snapshot_id) | (SnapshotModel.sha256 == snapshot_id)
        )
        snap = session.scalars(stmt).first()
        if not snap:
            raise HTTPException(status_code=404, detail=f"Snapshot '{snapshot_id}' not found")
        snap_id = snap.id
        file_path_str = snap.file_path
        expected_sha = snap.sha256
    resolved_path = resolve_snapshot_file_path(file_path_str)
    if not resolved_path or not resolved_path.exists():
        raise HTTPException(status_code=404, detail="Snapshot data file not found on disk")
    target_path = resolved_path

    # Strict provenance check: verify sha256 via cached mtime verification
    if not _verify_snapshot_checksum(target_path, expected_sha):
        raise HTTPException(
            status_code=422,
            detail="Snapshot checksum mismatch between database record and disk file",
        )

    storage = SnapshotStorage()
    candles = storage.load_snapshot_window(
        target_path,
        start_ms=start_ms,
        end_ms=end_ms,
        limit=limit,
    )

    response.headers["X-Snapshot-Id"] = snap_id
    response.headers["X-Snapshot-Sha256"] = expected_sha
    return [
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
        for c in candles
    ]


@router.get("/narrative")
def get_narrative():
    """Returns the evidence-first landing narrative document."""
    narrative_path = Path(__file__).resolve().parents[3] / "docs" / "landing-page-narrative.md"
    if not narrative_path.exists():
        raise HTTPException(status_code=404, detail="Narrative document not found")
    return {"markdown": narrative_path.read_text(encoding="utf-8")}
