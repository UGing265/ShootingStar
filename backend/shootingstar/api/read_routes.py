"""FastAPI read-only contracts router for ShootingStar.

All routes enforce strict security invariants:
- No database credentials, connection strings, or raw exception traces.
- No local filesystem paths in responses.
- Strict limit bounds [1, 100] (up to 500 for bounded candles).
- Stable ordering with tie-break ID and cursor support.
"""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Response
from fastapi.responses import JSONResponse
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from shootingstar.adapters.db.models import (
    AuditLogModel,
    ExperimentModel,
    ExperimentSplitModel,
    IngestionRunModel,
    MetricReportModel,
    ModelArtifactModel,
    PatternHitModel,
    PatternRuleModel,
    ReviewOverrideModel,
    SignalOutcomeModel,
    SignalPredictionModel,
    SnapshotModel,
)
from shootingstar.adapters.db.repository import (
    ExperimentRepository,
    MetricReportRepository,
    SignalRepository,
    SnapshotRepository,
)
from shootingstar.adapters.db.session import get_db_session
from shootingstar.adapters.storage import SnapshotStorage
from shootingstar.application.patterns import PatternLabService
from shootingstar.api.schemas import (
    AuditLogDTO,
    CalibrationBinDTO,
    CalibrationReportDTO,
    CandleDTO,
    ExperimentDetailResponse,
    ExperimentSplitDTO,
    ExperimentSummary,
    HealthResponse,
    IngestionRunSummary,
    MetricReportDTO,
    ModelArtifactDTO,
    PatternHitDTO,
    PatternRuleDTO,
    ReviewOverrideDTO,
    SignalDetailResponse,
    SignalOutcomeDTO,
    SignalPredictionDTO,
    SignalSummary,
    SnapshotQualityResponse,
    SnapshotSummary,
)
def _resolve_snapshot_file_path(file_path_str: str) -> Optional[Path]:
    """Resolves snapshot file path robustly against cwd, repo root, and backend dir."""
    if not file_path_str:
        return None
    p = Path(file_path_str)
    # Absolute paths must be resolved strictly; never fall through if missing
    if p.is_absolute():
        return p if p.exists() else None
    if p.exists():
        return p.resolve()
    repo_root = Path(__file__).resolve().parents[3]
    candidate = repo_root / p
    if candidate.exists():
        return candidate.resolve()
    backend_dir = repo_root / "backend"
    candidate = backend_dir / p
    if candidate.exists():
        return candidate.resolve()
    return None

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

def _parse_cursor_ms_id(cursor: Optional[str]) -> Optional[tuple[int, str]]:
    """Parses a cursor formatted as '<time_ms>|<id>'."""
    if not cursor:
        return None
    parts = cursor.split("|", 1)
    if len(parts) != 2:
        raise HTTPException(status_code=422, detail="Invalid cursor format; expected '<time_ms>|<id>'")
    try:
        t_ms = int(parts[0])
        return t_ms, parts[1]
    except Exception:
        raise HTTPException(status_code=422, detail="Invalid integer timestamp in cursor")


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
    resolved_path = _resolve_snapshot_file_path(file_path_str)
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


@router.get("/experiments", response_model=List[ExperimentSummary])
def list_experiments(
    limit: int = Query(default=20, ge=1, le=100),
    cursor: Optional[str] = Query(default=None),
):
    """Lists registered research experiments with cursor pagination."""
    parsed_cursor = _parse_cursor_iso_id(cursor)
    with get_db_session() as session:
        stmt = select(ExperimentModel)
        if parsed_cursor:
            c_time, c_id = parsed_cursor
            stmt = stmt.where(
                (ExperimentModel.created_at < c_time)
                | ((ExperimentModel.created_at == c_time) & (ExperimentModel.id < c_id))
            )
        stmt = stmt.order_by(ExperimentModel.created_at.desc(), ExperimentModel.id.desc()).limit(limit)
        experiments = session.scalars(stmt).all()
        results = []
        for e in experiments:
            params = json.loads(e.parameters_json) if e.parameters_json else {}
            results.append(
                ExperimentSummary(
                    id=e.id,
                    name=e.name,
                    config_hash=e.config_hash,
                    snapshot_id=e.snapshot_id,
                    parameters=params,
                    created_at=e.created_at.isoformat(),
                )
            )
        return results


@router.get("/experiments/{experiment_id}", response_model=ExperimentDetailResponse)
def get_experiment_detail(experiment_id: str):
    """Retrieves full experiment provenance, ordered splits, all reports, and artifacts."""
    with get_db_session() as session:
        exp_repo = ExperimentRepository(session)
        exp = exp_repo.get_by_id(experiment_id)
        if not exp:
            raise HTTPException(status_code=404, detail=f"Experiment '{experiment_id}' not found")

        # Snapshot SHA provenance
        snap_stmt = select(SnapshotModel).where(SnapshotModel.id == exp.snapshot_id)
        snap = session.scalars(snap_stmt).first()
        snapshot_sha = snap.sha256 if snap else None

        # Ordered splits: chronological by start_time_ms, tie-break id
        split_stmt = (
            select(ExperimentSplitModel)
            .where(ExperimentSplitModel.experiment_id == experiment_id)
            .order_by(ExperimentSplitModel.start_time_ms.asc(), ExperimentSplitModel.id.asc())
        )
        splits = [
            ExperimentSplitDTO(
                id=s.id,
                split_type=s.split_type,
                start_time_ms=s.start_time_ms,
                end_time_ms=s.end_time_ms,
                sample_count=s.sample_count,
            )
            for s in session.scalars(split_stmt).all()
        ]

        # Artifacts (strictly omitting artifact_path!)
        art_stmt = (
            select(ModelArtifactModel)
            .where(ModelArtifactModel.experiment_id == experiment_id)
            .order_by(ModelArtifactModel.created_at.desc(), ModelArtifactModel.id.asc())
        )
        artifacts = [
            ModelArtifactDTO(
                id=a.id,
                model_type=a.model_type,
                artifact_hash=a.artifact_hash,
                created_at=a.created_at.isoformat(),
            )
            for a in session.scalars(art_stmt).all()
        ]

        # All reports: ordered by split_type, report_type, created_at desc, id asc
        rep_stmt = (
            select(MetricReportModel)
            .where(MetricReportModel.experiment_id == experiment_id)
            .order_by(
                MetricReportModel.split_type.asc(),
                MetricReportModel.report_type.asc(),
                MetricReportModel.created_at.desc(),
                MetricReportModel.id.asc(),
            )
        )
        reports = []
        for r in session.scalars(rep_stmt).all():
            m_data = json.loads(r.metrics_json) if r.metrics_json else {}
            c_data = json.loads(r.calibration_json) if r.calibration_json else None
            calib_dto: Optional[CalibrationReportDTO] = None
            if c_data is not None:
                raw_bins = c_data.get("bins", c_data) if isinstance(c_data, dict) else c_data
                if isinstance(raw_bins, list):
                    calib_bins = []
                    for idx, b in enumerate(raw_bins):
                        if isinstance(b, dict):
                            b_idx = b.get("bin_index", b.get("bin", idx))
                            b_range = b.get("bin_range") or f"Bin {b_idx}"
                            s_cnt = b.get("sample_count", 0)
                            m_prob = float(b.get("mean_predicted_prob", 0.0))
                            e_freq = float(b.get("empirical_frequency", b.get("empirical_positive_rate", 0.0)))
                            calib_bins.append(
                                CalibrationBinDTO(
                                    bin_index=b_idx,
                                    bin_range=b_range,
                                    sample_count=s_cnt,
                                    mean_predicted_prob=m_prob,
                                    empirical_frequency=e_freq,
                                )
                            )
                    calib_dto = CalibrationReportDTO(bins=calib_bins)
            reports.append(
                MetricReportDTO(
                    id=r.id,
                    split_type=r.split_type,
                    report_type=r.report_type,
                    metrics=m_data,
                    calibration=calib_dto,
                    created_at=r.created_at.isoformat(),
                )
            )

        params = json.loads(exp.parameters_json) if exp.parameters_json else {}

        return ExperimentDetailResponse(
            id=exp.id,
            name=exp.name,
            config_hash=exp.config_hash,
            snapshot_id=exp.snapshot_id,
            snapshot_sha256=snapshot_sha,
            parameters=params,
            created_at=exp.created_at.isoformat(),
            splits=splits,
            artifacts=artifacts,
            reports=reports,
        )


@router.get("/pattern-rules", response_model=List[PatternRuleDTO])
def list_pattern_rules(
    limit: int = Query(default=20, ge=1, le=100),
    cursor: Optional[str] = Query(default=None),
):
    """Lists persisted pattern rules with stable ordering and cursor pagination."""
    parsed_cursor = _parse_cursor_iso_id(cursor)
    with get_db_session() as session:
        stmt = select(PatternRuleModel)
        if parsed_cursor:
            c_time, c_id = parsed_cursor
            stmt = stmt.where(
                (PatternRuleModel.created_at < c_time)
                | ((PatternRuleModel.created_at == c_time) & (PatternRuleModel.id < c_id))
            )
        stmt = stmt.order_by(
            PatternRuleModel.created_at.desc(),
            PatternRuleModel.id.desc(),
        ).limit(limit)
        rules = session.scalars(stmt).all()
        results = []
        for r in rules:
            def_dict = json.loads(r.definition_json) if r.definition_json else {}
            results.append(
                PatternRuleDTO(
                    id=r.id,
                    name=r.name,
                    version=r.version,
                    description=r.description,
                    definition=def_dict,
                    created_at=r.created_at.isoformat(),
                )
            )
        return results


@router.get("/pattern-rules/{rule_id}", response_model=PatternRuleDTO)
def get_pattern_rule_detail(rule_id: str):
    """Retrieves single pattern rule definition by ID."""
    with get_db_session() as session:
        rule = session.get(PatternRuleModel, rule_id)
        if not rule:
            raise HTTPException(status_code=404, detail=f"Pattern rule '{rule_id}' not found")
        def_dict = json.loads(rule.definition_json) if rule.definition_json else {}
        return PatternRuleDTO(
            id=rule.id,
            name=rule.name,
            version=rule.version,
            description=rule.description,
            definition=def_dict,
            created_at=rule.created_at.isoformat(),
        )


@router.get("/pattern-rules/{rule_id}/hits", response_model=List[PatternHitDTO])
def list_pattern_rule_hits(
    rule_id: str,
    limit: int = Query(default=50, ge=1, le=100),
    cursor: Optional[str] = Query(default=None),
):
    """Lists persisted hits for a pattern rule with stable ordering and cursor pagination."""
    parsed_cursor = _parse_cursor_ms_id(cursor)
    with get_db_session() as session:
        rule = session.get(PatternRuleModel, rule_id)
        if not rule:
            raise HTTPException(status_code=404, detail=f"Pattern rule '{rule_id}' not found")

        stmt = select(PatternHitModel).where(PatternHitModel.rule_id == rule_id)
        if parsed_cursor:
            c_time, c_id = parsed_cursor
            stmt = stmt.where(
                (PatternHitModel.detected_time_ms < c_time)
                | ((PatternHitModel.detected_time_ms == c_time) & (PatternHitModel.id < c_id))
            )
        stmt = stmt.order_by(PatternHitModel.detected_time_ms.desc(), PatternHitModel.id.desc()).limit(limit)
        hits = session.scalars(stmt).all()
        return [
            PatternHitDTO(
                id=h.id,
                rule_id=h.rule_id,
                detected_time_ms=h.detected_time_ms,
                symbol=h.symbol,
                timeframe=h.timeframe,
                outcome_return_30m=h.outcome_return_30m,
                outcome_label=h.outcome_label,
                created_at=h.created_at.isoformat(),
            )
            for h in hits
        ]

@router.get("/patterns")
def get_patterns(snapshot_id: Optional[str] = None):
    """Evaluates Pattern Lab rules on a snapshot as an on-demand statistical aggregate.

    Snapshot selection is strictly deterministic: resolves from PostgreSQL catalog
    by sha256/id or selects the latest registered snapshot (ordered by end_time_ms desc, id asc).
    Enforces SHA-256 verification and strictly omits raw filesystem paths.
    """
    with get_db_session() as session:
        snap_repo = SnapshotRepository(session)
        if snapshot_id:
            snap = snap_repo.get_by_sha256(snapshot_id)
            if not snap:
                all_snaps = snap_repo.list_all(limit=100)
                matches = [s for s in all_snaps if snapshot_id in s.id or snapshot_id in s.sha256]
                if matches:
                    snap = matches[0]
                else:
                    raise HTTPException(status_code=404, detail=f"Snapshot '{snapshot_id}' not found")
        else:
            stmt = (
                select(SnapshotModel)
                .order_by(SnapshotModel.end_time_ms.desc(), SnapshotModel.id.asc())
                .limit(1)
            )
            snap = session.scalars(stmt).first()
            if not snap:
                raise HTTPException(status_code=404, detail="No snapshots available for pattern analysis")
        target_file_path = snap.file_path
        snap_id = snap.id
        snap_sha256 = snap.sha256

    resolved_path = _resolve_snapshot_file_path(target_file_path)
    if not resolved_path or not resolved_path.exists():
        raise HTTPException(status_code=404, detail="Snapshot data file not found on disk")
    target_path = resolved_path

    # Security & provenance invariant: verify SHA-256 before processing
    file_bytes = target_path.read_bytes()
    computed_sha = hashlib.sha256(file_bytes).hexdigest()
    if computed_sha != snap_sha256:
        raise HTTPException(
            status_code=422,
            detail="Snapshot checksum mismatch between database record and disk file",
        )

    storage = SnapshotStorage()
    candles = storage.load_snapshot(target_path)
    lab = PatternLabService()
    reports = lab.analyze_all(candles, horizon_minutes=30)

    return {
        "snapshot_id": snap_id,
        "snapshot_sha256": snap_sha256,
        "candle_count": len(candles),
        "reports": [r.to_dict() for r in reports],
        "computation_type": "ON_DEMAND_SNAPSHOT_AGGREGATE",
        "hypothesis_track": "SEPARATE_HYPOTHESIS_TRACK_NOT_IN_MODEL_FEATURES",
    }


@router.get("/signals", response_model=List[SignalSummary])
def list_signals(
    limit: int = Query(default=50, ge=1, le=100),
    cursor: Optional[str] = Query(default=None),
):
    """Lists append-only predictions and their outcomes with cursor pagination."""
    parsed_cursor = _parse_cursor_ms_id(cursor)
    with get_db_session() as session:
        stmt = select(SignalPredictionModel)
        if parsed_cursor:
            c_time, c_id = parsed_cursor
            stmt = stmt.where(
                (SignalPredictionModel.prediction_time_ms < c_time)
                | (
                    (SignalPredictionModel.prediction_time_ms == c_time)
                    & (SignalPredictionModel.id < c_id)
                )
            )
        stmt = stmt.order_by(
            SignalPredictionModel.prediction_time_ms.desc(),
            SignalPredictionModel.id.desc(),
        ).limit(limit)
        preds = session.scalars(stmt).all()
        results = []
        for p in preds:
            out_stmt = select(SignalOutcomeModel).where(SignalOutcomeModel.signal_id == p.id)
            outcome = session.scalars(out_stmt).first()
            results.append(
                SignalSummary(
                    id=p.id,
                    prediction_time_ms=p.prediction_time_ms,
                    symbol=p.symbol,
                    timeframe=p.timeframe,
                    horizon_minutes=p.horizon_minutes,
                    predicted_class=p.predicted_class,
                    decision=p.decision,
                    decision_reason=p.decision_reason,
                    probability_up=p.probability_up,
                    probability_down=p.probability_down,
                    probability_no_trade=p.probability_no_trade,
                    status=outcome.status if outcome else "PENDING",
                    realized_label=outcome.realized_label if outcome else None,
                    realized_return=outcome.realized_return if outcome else None,
                    is_match=outcome.is_match if outcome else None,
                    unscorable_reason=outcome.unscorable_reason if outcome else None,
                    created_at=p.created_at.isoformat(),
                )
            )
        return results


@router.get("/signals/{signal_id}", response_model=SignalDetailResponse)
def get_signal_detail(signal_id: str):
    """Retrieves full signal detail with separated decision, outcome, reviews, and audit logs."""
    with get_db_session() as session:
        pred = session.get(SignalPredictionModel, signal_id)
        if not pred:
            raise HTTPException(status_code=404, detail=f"Signal '{signal_id}' not found")

        out_stmt = select(SignalOutcomeModel).where(SignalOutcomeModel.signal_id == signal_id)
        outcome_m = session.scalars(out_stmt).first()
        outcome_dto = None
        if outcome_m:
            outcome_dto = SignalOutcomeDTO(
                id=outcome_m.id,
                status=outcome_m.status,
                evaluated_at_ms=outcome_m.evaluated_at_ms,
                realized_return=outcome_m.realized_return,
                realized_label=outcome_m.realized_label,
                is_match=outcome_m.is_match,
                unscorable_reason=outcome_m.unscorable_reason,
                created_at=outcome_m.created_at.isoformat(),
            )

        rev_stmt = (
            select(ReviewOverrideModel)
            .where(ReviewOverrideModel.signal_id == signal_id)
            .order_by(ReviewOverrideModel.created_at.asc(), ReviewOverrideModel.id.asc())
        )
        reviews = [
            ReviewOverrideDTO(
                id=r.id,
                reviewer_id=r.reviewer_id,
                override_decision=r.override_decision,
                notes=r.notes,
                created_at=r.created_at.isoformat(),
            )
            for r in session.scalars(rev_stmt).all()
        ]

        audit_stmt = (
            select(AuditLogModel)
            .where(AuditLogModel.entity_type == "signal", AuditLogModel.entity_id == signal_id)
            .order_by(AuditLogModel.created_at.asc(), AuditLogModel.id.asc())
        )
        audit_logs = []
        for a in session.scalars(audit_stmt).all():
            details_dict = json.loads(a.details_json) if a.details_json else {}
            audit_logs.append(
                AuditLogDTO(
                    id=a.id,
                    action=a.action,
                    details=details_dict,
                    created_at=a.created_at.isoformat(),
                )
            )

        pred_dto = SignalPredictionDTO(
            id=pred.id,
            prediction_time_ms=pred.prediction_time_ms,
            experiment_id=pred.experiment_id,
            symbol=pred.symbol,
            timeframe=pred.timeframe,
            horizon_minutes=pred.horizon_minutes,
            probability_up=pred.probability_up,
            probability_down=pred.probability_down,
            probability_no_trade=pred.probability_no_trade,
            predicted_class=pred.predicted_class,
            decision=pred.decision,
            decision_reason=pred.decision_reason,
            created_at=pred.created_at.isoformat(),
        )

        return SignalDetailResponse(
            prediction=pred_dto,
            outcome=outcome_dto,
            reviews=reviews,
            audit_logs=audit_logs,
        )


@router.get("/narrative")
def get_narrative():
    """Returns the evidence-first landing narrative document."""
    narrative_path = Path("docs/landing-page-narrative.md")
    if not narrative_path.exists():
        raise HTTPException(status_code=404, detail="Narrative document not found")
    return {"markdown": narrative_path.read_text(encoding="utf-8")}
