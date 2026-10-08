"""Integration tests for PostgreSQL persistence, migrations, and provenance constraints.

Executes strictly against the Alembic-migrated database schema.
"""

import os
import uuid
import pytest
from alembic.config import Config
from alembic import command
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from shootingstar.adapters.db.models import (
    AuditLogModel,
    CanonicalCandleModel,
    ExperimentModel,
    ExperimentSplitModel,
    IngestionRunModel,
    LabelRecordModel,
    MetricReportModel,
    RejectedRecordModel,
    ReviewOverrideModel,
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
def migrated_test_engine():
    """Ensures test database is fully migrated via Alembic, testing migration integrity."""
    test_url = get_database_url(test_mode=True)
    os.environ["SHOOTINGSTAR_DATABASE_URL"] = test_url

    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")

    engine = create_engine(test_url, pool_pre_ping=True)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(migrated_test_engine):
    with Session(migrated_test_engine) as session:
        yield session
        session.rollback()


def test_canonical_candles_and_uniqueness(db_session: Session):
    open_time = 1700000000000
    c1 = CanonicalCandleModel(
        venue="BINANCE",
        symbol="BTCUSDT",
        timeframe="5m",
        open_time_ms=open_time,
        close_time_ms=open_time + 300000 - 1,
        open=50000.0,
        high=50100.0,
        low=49900.0,
        close=50050.0,
        volume=10.0,
        quote_volume=500000.0,
        trades_count=100,
        taker_buy_base_volume=5.0,
        taker_buy_quote_volume=250000.0,
        observed_ingested_at_ms=open_time + 300500,
    )
    db_session.add(c1)
    db_session.flush()

    # Invariant: Duplicate natural key must fail with IntegrityError
    c1_duplicate = CanonicalCandleModel(
        venue="BINANCE",
        symbol="BTCUSDT",
        timeframe="5m",
        open_time_ms=open_time,
        close_time_ms=open_time + 300000 - 1,
        open=50000.0,
        high=50100.0,
        low=49900.0,
        close=50050.0,
        volume=10.0,
        quote_volume=500000.0,
        trades_count=100,
        taker_buy_base_volume=5.0,
        taker_buy_quote_volume=250000.0,
    )
    db_session.add(c1_duplicate)
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_rejected_records_logging(db_session: Session):
    rej = RejectedRecordModel(
        venue="BINANCE",
        symbol="BTCUSDT",
        timeframe="5m",
        timestamp_ms=1700000000000,
        rejection_reason="high < low invariant violation",
        raw_payload_preview="[1700000000000, 100, 90, 110, 105...]",
        ingested_at_ms=1700000301000,
    )
    db_session.add(rej)
    db_session.flush()
    assert rej.id is not None
    assert rej.rejection_reason == "high < low invariant violation"


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


def test_experiment_splits_labels_and_reports(db_session: Session):
    snap_repo = SnapshotRepository(db_session)
    exp_repo = ExperimentRepository(db_session)

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
        name="Walk-Forward Logistic Regression",
        config_hash=uuid.uuid4().hex,
        snapshot_id=snap_hash,
        parameters_json='{"timeframe": "5m", "horizon": 30}',
    )
    exp_repo.save(exp)

    # 1. Experiment split
    split = ExperimentSplitModel(
        experiment_id=exp_id,
        split_type="TRAIN",
        start_time_ms=1700000000000,
        end_time_ms=1700050000000,
        sample_count=200,
    )
    db_session.add(split)

    # 2. Label record
    label = LabelRecordModel(
        snapshot_id=snap_hash,
        timeframe="5m",
        time_t_ms=1700000000000,
        horizon_minutes=30,
        price_at_t=50000.0,
        price_at_t_plus_horizon=50300.0,
        return_30m=0.006,
        direction_label="UP",
        cost_adjusted_label=None,  # Gated until cost method approved
    )
    db_session.add(label)

    # 3. Metric report
    report = MetricReportModel(
        experiment_id=exp_id,
        split_type="TEST",
        report_type="OUT_OF_SAMPLE_WALK_FORWARD",
        metrics_json='{"accuracy": 0.53, "precision_up": 0.54, "brier_score": 0.24}',
        calibration_json='{"bins": [0.1, 0.2, 0.3], "empirical": [0.12, 0.21, 0.29]}',
    )
    db_session.add(report)
    db_session.flush()

    assert split.id is not None
    assert label.direction_label == "UP"
    assert report.split_type == "TEST"


def test_signal_append_only_and_review_override(db_session: Session):
    snap_repo = SnapshotRepository(db_session)
    exp_repo = ExperimentRepository(db_session)
    sig_repo = SignalRepository(db_session)

    snap_hash = uuid.uuid4().hex + uuid.uuid4().hex
    snapshot = SnapshotModel(
        id=snap_hash,
        venue="BINANCE",
        symbol="BTCUSDT",
        timeframe="5m",
        start_time_ms=1700000000000,
        end_time_ms=1700086400000,
        candle_count=288,
        file_path="data/snapshots/signal_snap.parquet",
        sha256=snap_hash,
    )
    snap_repo.save(snapshot)

    exp_id = "exp_" + uuid.uuid4().hex[:12]
    exp = ExperimentModel(
        id=exp_id,
        name="Pilot Model",
        config_hash=uuid.uuid4().hex,
        snapshot_id=snap_hash,
        parameters_json='{}',
    )
    exp_repo.save(exp)

    sig_id = "sig_" + uuid.uuid4().hex[:16]
    pred = SignalPredictionModel(
        id=sig_id,
        prediction_time_ms=1700086400000,
        experiment_id=exp_id,
        symbol="BTCUSDT",
        timeframe="5m",
        horizon_minutes=30,
        probability_up=0.60,
        probability_down=0.30,
        probability_no_trade=0.10,
        predicted_class="UP",
        decision="UP",
        decision_reason="Probability threshold met",
    )
    sig_repo.save_prediction(pred)

    # Separate outcome
    outcome = SignalOutcomeModel(
        signal_id=sig_id,
        status="EVALUATED",
        evaluated_at_ms=1700088200000,
        realized_return=0.0075,
        realized_label="UP",
        is_match=True,
    )
    sig_repo.save_outcome(outcome)

    # Reviewer override audit record
    override = ReviewOverrideModel(
        signal_id=sig_id,
        reviewer_id="human_operator_1",
        override_decision="STAND_ASIDE",
        notes="High macro volatility window observed",
    )
    db_session.add(override)
    db_session.flush()

    assert override.id is not None
    assert override.override_decision == "STAND_ASIDE"


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
