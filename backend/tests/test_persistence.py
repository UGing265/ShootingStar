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
    PatternHitModel,
    PatternRuleModel,
    RejectedRecordModel,
    ReviewOverrideModel,
    SignalOutcomeModel,
    SignalPredictionModel,
    SnapshotModel,
)
from shootingstar.adapters.db.repository import (
    AuditLogRepository,
    CanonicalCandleRepository,
    ExperimentRepository,
    ExperimentSplitRepository,
    IngestionRunRepository,
    LabelRecordRepository,
    MetricReportRepository,
    PatternHitRepository,
    PatternRuleRepository,
    RejectedRecordRepository,
    ReviewOverrideRepository,
    SignalRepository,
    SnapshotRepository,
)
from shootingstar.adapters.db.session import get_database_url



def test_canonical_candle_repository(db_session: Session):
    repo = CanonicalCandleRepository(db_session)
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
    repo.save(c1)

    candles = repo.get_range("BINANCE", "BTCUSDT", "5m", open_time, open_time + 300000)
    assert len(candles) >= 1
    assert candles[0].close == 50050.0

    # Test uniqueness
    dup = CanonicalCandleModel(
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
    with pytest.raises(IntegrityError):
        repo.save(dup)


def test_rejected_record_repository(db_session: Session):
    repo = RejectedRecordRepository(db_session)
    rej = repo.record_rejection(
        venue="BINANCE",
        symbol="BTCUSDT",
        timeframe="5m",
        rejection_reason="high < low invariant violation",
        raw_payload_preview="[1700000000000, 100, 90, 110, 105...]",
        ingested_at_ms=1700000301000,
        timestamp_ms=1700000000000,
    )
    assert rej.id is not None
    assert rej.rejection_reason == "high < low invariant violation"


def test_ingestion_run_and_snapshot_repositories(db_session: Session):
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
    all_runs = run_repo.list_all(limit=10)
    assert any(r.id == run_id for r in all_runs)

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
    all_snaps = snap_repo.list_all(limit=10)
    assert any(s.id == snap_hash for s in all_snaps)


def test_experiment_split_label_and_metric_repositories(db_session: Session):
    snap_repo = SnapshotRepository(db_session)
    exp_repo = ExperimentRepository(db_session)
    split_repo = ExperimentSplitRepository(db_session)
    label_repo = LabelRecordRepository(db_session)
    report_repo = MetricReportRepository(db_session)

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
    assert exp_repo.get_by_id(exp_id) is not None
    assert len(exp_repo.list_all()) >= 1

    # Split
    split = ExperimentSplitModel(
        experiment_id=exp_id,
        split_type="TRAIN",
        start_time_ms=1700000000000,
        end_time_ms=1700050000000,
        sample_count=200,
    )
    split_repo.save(split)
    loaded_split = split_repo.get_by_experiment_and_type(exp_id, "TRAIN")
    assert loaded_split is not None
    assert loaded_split.sample_count == 200

    # Label
    label = LabelRecordModel(
        snapshot_id=snap_hash,
        timeframe="5m",
        time_t_ms=1700000000000,
        horizon_minutes=30,
        price_at_t=50000.0,
        price_at_t_plus_horizon=50300.0,
        return_30m=0.006,
        direction_label="UP",
        cost_adjusted_label=None,
    )
    label_repo.save(label)
    labels = label_repo.get_labels_for_snapshot(snap_hash)
    assert len(labels) == 1
    assert labels[0].direction_label == "UP"

    # Report
    report = MetricReportModel(
        experiment_id=exp_id,
        split_type="TEST",
        report_type="OUT_OF_SAMPLE_WALK_FORWARD",
        metrics_json='{"accuracy": 0.53, "precision_up": 0.54, "brier_score": 0.24}',
        calibration_json='{"bins": [0.1, 0.2, 0.3], "empirical": [0.12, 0.21, 0.29]}',
    )
    report_repo.save(report)
    reports = report_repo.get_by_experiment(exp_id)
    assert len(reports) == 1
    assert reports[0].report_type == "OUT_OF_SAMPLE_WALK_FORWARD"


def test_signal_and_review_override_repositories(db_session: Session):
    snap_repo = SnapshotRepository(db_session)
    exp_repo = ExperimentRepository(db_session)
    sig_repo = SignalRepository(db_session)
    rev_repo = ReviewOverrideRepository(db_session)

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
    assert sig_repo.get_prediction_by_id(sig_id) is not None

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
    assert sig_repo.get_outcome_by_signal_id(sig_id) is not None

    # Review override
    override = ReviewOverrideModel(
        signal_id=sig_id,
        reviewer_id="human_operator_1",
        override_decision="STAND_ASIDE",
        notes="High macro volatility window observed",
    )
    rev_repo.save(override)
    overrides = rev_repo.get_by_signal_id(sig_id)
    assert len(overrides) == 1
    assert overrides[0].override_decision == "STAND_ASIDE"


def test_pattern_rule_and_hit_repositories(db_session: Session):
    rule_repo = PatternRuleRepository(db_session)
    hit_repo = PatternHitRepository(db_session)

    rule_id = "rule_shooting_star_v1"
    rule = PatternRuleModel(
        id=rule_id,
        name="Shooting Star",
        version=1,
        description="Upper shadow >= 2x real body, small lower shadow, prior uptrend",
        definition_json='{"upper_wick_ratio": 2.0, "body_ratio_max": 0.3}',
    )
    rule_repo.save(rule)

    loaded_rule = rule_repo.get_by_id(rule_id)
    assert loaded_rule is not None
    assert loaded_rule.name == "Shooting Star"
    assert len(rule_repo.list_all()) >= 1

    # Record hit
    hit = PatternHitModel(
        rule_id=rule_id,
        detected_time_ms=1700000000000,
        symbol="BTCUSDT",
        timeframe="5m",
        outcome_return_30m=-0.008,
        outcome_label="DOWN",
    )
    hit_repo.save(hit)

    hits = hit_repo.get_hits_for_rule(rule_id)
    assert len(hits) == 1
    assert hits[0].outcome_label == "DOWN"


def test_audit_log_repository(db_session: Session):
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
