"""Integration tests for PostgreSQL persistence, repositories, and provenance constraints."""

import uuid
import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from shootingstar.adapters.db.models import (
    AuditLogModel,
    Base,
    ExperimentModel,
    IngestionRunModel,
    SignalOutcomeModel,
    SignalPredictionModel,
    SnapshotModel,
)
from shootingstar.adapters.db.repository import (
    AuditLogRepository,
    ExperimentRepository,
    IngestionRunRepository,
    SignalRepository,
    SnapshotRepository,
)
from shootingstar.adapters.db.session import get_database_url


@pytest.fixture(scope="module")
def test_engine():
    url = get_database_url(test_mode=True)
    engine = create_engine(url, pool_pre_ping=True)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(test_engine):
    with Session(test_engine) as session:
        yield session
        session.rollback()


def test_ingestion_run_and_snapshot_persistence(db_session: Session):
    run_repo = IngestionRunRepository(db_session)
    snap_repo = SnapshotRepository(db_session)

    run_id = str(uuid.uuid4())
    run = IngestionRunModel(
        id=run_id,
        venue="BINANCE",
        symbol="BTCUSDT",
        timeframe="5m",
        start_time_ms=1700000000000,
        end_time_ms=1700086400000,
        valid_candles_count=288,
        missing_intervals_count=0,
        duplicate_candles_count=0,
        coverage_ratio=1.0,
        is_pristine=True,
        raw_files_count=1,
    )
    run_repo.save(run)

    loaded_run = run_repo.get_by_id(run_id)
    assert loaded_run is not None
    assert loaded_run.valid_candles_count == 288
    assert loaded_run.is_pristine is True

    # Save snapshot linked to run
    snap_hash = uuid.uuid4().hex + uuid.uuid4().hex
    snapshot = SnapshotModel(
        id=snap_hash,
        ingestion_run_id=run_id,
        venue="BINANCE",
        symbol="BTCUSDT",
        timeframe="5m",
        start_time_ms=1700000000000,
        end_time_ms=1700086400000,
        candle_count=288,
        file_path="data/snapshots/sample.parquet",
        sha256=snap_hash,
    )
    snap_repo.save(snapshot)

    loaded_snap = snap_repo.get_by_sha256(snap_hash)
    assert loaded_snap is not None
    assert loaded_snap.ingestion_run_id == run_id
    assert loaded_snap.candle_count == 288


def test_experiment_and_signal_append_only_contracts(db_session: Session):
    snap_repo = SnapshotRepository(db_session)
    exp_repo = ExperimentRepository(db_session)
    sig_repo = SignalRepository(db_session)

    # 1. Setup Snapshot and Experiment
    snap_hash = uuid.uuid4().hex + uuid.uuid4().hex
    snapshot = SnapshotModel(
        id=snap_hash,
        venue="BINANCE",
        symbol="BTCUSDT",
        timeframe="5m",
        start_time_ms=1700000000000,
        end_time_ms=1700086400000,
        candle_count=288,
        file_path="data/snapshots/exp_snap.parquet",
        sha256=snap_hash,
    )
    snap_repo.save(snapshot)

    exp_id = "exp_" + uuid.uuid4().hex[:12]
    exp = ExperimentModel(
        id=exp_id,
        name="Pilot Logistic Regression 5m",
        config_hash=uuid.uuid4().hex,
        snapshot_id=snap_hash,
        parameters_json='{"timeframe": "5m", "horizon": 30}',
    )
    exp_repo.save(exp)

    # 2. Immutable prediction record
    sig_id = "sig_" + uuid.uuid4().hex[:16]
    pred = SignalPredictionModel(
        id=sig_id,
        prediction_time_ms=1700086400000,
        experiment_id=exp_id,
        symbol="BTCUSDT",
        timeframe="5m",
        horizon_minutes=30,
        probability_up=0.62,
        probability_down=0.28,
        probability_no_trade=0.10,
        predicted_class="UP",
        decision="UP",
        decision_reason="Probability exceeds threshold",
    )
    sig_repo.save_prediction(pred)

    loaded_pred = sig_repo.get_prediction_by_id(sig_id)
    assert loaded_pred is not None
    assert loaded_pred.predicted_class == "UP"
    assert loaded_pred.decision == "UP"

    # 3. Separate outcome maturation record
    outcome = SignalOutcomeModel(
        signal_id=sig_id,
        status="EVALUATED",
        evaluated_at_ms=1700088200000,
        realized_return=0.0075,
        realized_label="UP",
        is_match=True,
    )
    sig_repo.save_outcome(outcome)

    loaded_outcome = sig_repo.get_outcome_by_signal_id(sig_id)
    assert loaded_outcome is not None
    assert loaded_outcome.realized_return == 0.0075
    assert loaded_outcome.is_match is True

    # 4. Enforce uniqueness: duplicate outcome for same signal must violate constraint
    duplicate_outcome = SignalOutcomeModel(
        signal_id=sig_id,
        status="EVALUATED",
        evaluated_at_ms=1700088200000,
        realized_return=0.0080,
    )
    with pytest.raises(IntegrityError):
        sig_repo.save_outcome(duplicate_outcome)
        db_session.flush()


def test_audit_log_append_only(db_session: Session):
    audit_repo = AuditLogRepository(db_session)
    log = audit_repo.record(
        entity_type="EXPERIMENT",
        entity_id="exp_test_001",
        action="CREATE",
        details={"user": "operator", "reason": "model validation"},
    )
    assert log.id is not None
    assert log.entity_type == "EXPERIMENT"
    assert log.action == "CREATE"
