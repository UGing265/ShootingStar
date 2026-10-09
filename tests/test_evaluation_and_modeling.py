"""Tests for walk-forward splits, calibrated modeling, evaluation reports, and reproducibility."""

from pathlib import Path
import numpy as np
import pytest

from shootingstar.adapters.storage import SnapshotStorage
from shootingstar.application.evaluation import EvaluationReportGenerator
from shootingstar.application.experiment import ExperimentRunner
from shootingstar.application.modeling import CalibratedLogisticRegressionModel
from shootingstar.application.splits import WalkForwardSplitter
from shootingstar.domain.models import Candle


def create_synthetic_candle_series(count: int, start_time: int = 1700000000000, tf_ms: int = 300000) -> list[Candle]:
    candles = []
    base_price = 50000.0
    for i in range(count):
        open_time = start_time + (i * tf_ms)
        close_time = open_time + tf_ms - 1
        drift = float(np.sin(i / 15.0) * 150.0 + np.cos(i / 5.0) * 50.0)
        p_open = base_price + drift
        p_high = p_open + 25.0
        p_low = p_open - 25.0
        p_close = p_open + float(np.sin(i) * 10.0)
        candles.append(
            Candle(
                venue="BINANCE",
                symbol="BTCUSDT",
                timeframe="5m",
                open_time_ms=open_time,
                close_time_ms=close_time,
                open=p_open,
                high=p_high,
                low=p_low,
                close=p_close,
                volume=10.0 + (i % 3),
                quote_volume=(10.0 + (i % 3)) * p_close,
                trades_count=50,
                taker_buy_base_volume=5.0,
                taker_buy_quote_volume=125000.0,
            )
        )
    return candles


def test_walk_forward_splitter_purging_gap():
    timestamps = [1700000000000 + (i * 300000) for i in range(200)]
    splitter = WalkForwardSplitter(purge_gap_samples=6)
    splits = splitter.split(timestamps)

    # 1. No overlap
    assert splits.train.end_idx < splits.calibration.start_idx
    assert splits.calibration.end_idx < splits.validation.start_idx
    assert splits.validation.end_idx < splits.test.start_idx

    # 2. Minimum purge gap strictly enforced (>= 6 samples = 30m)
    assert (splits.calibration.start_idx - splits.train.end_idx) >= 7
    assert (splits.validation.start_idx - splits.calibration.end_idx) >= 7
    assert (splits.test.start_idx - splits.validation.end_idx) >= 7


def test_calibrated_logistic_regression_fit_and_save(tmp_path: Path):
    np.random.seed(42)
    X_train = np.random.randn(100, 5)
    y_train = (X_train[:, 0] > 0).astype(int)

    X_calib = np.random.randn(50, 5)
    y_calib = (X_calib[:, 0] > 0).astype(int)

    X_test = np.random.randn(30, 5)

    model = CalibratedLogisticRegressionModel()
    model.fit_and_calibrate(X_train, y_train, X_calib, y_calib)

    proba = model.predict_proba(X_test)
    assert proba.shape == (30, 2)
    # Probabilities must sum to 1.0
    assert np.allclose(np.sum(proba, axis=1), 1.0)

    # Test artifact save and reload
    art_path, art_hash = model.save_artifact(tmp_path, "exp_test_01")
    assert art_path.exists()
    assert len(art_hash) == 64

    loaded_model = CalibratedLogisticRegressionModel.load_artifact(art_path)
    loaded_proba = loaded_model.predict_proba(X_test)
    assert np.allclose(proba, loaded_proba)


def test_evaluation_report_generator_and_cost_gating():
    np.random.seed(42)
    X_test = np.random.randn(50, 4)
    y_test = (X_test[:, 0] > 0).astype(int)
    returns_test = np.where(y_test == 1, 0.005, -0.005)

    model = CalibratedLogisticRegressionModel()
    model.fit_and_calibrate(X_test, y_test, X_test, y_test)

    y_train = np.ones(50, dtype=int)  # 100% UP in train
    report = EvaluationReportGenerator.generate_report(
        model=model,
        X_test=X_test,
        y_test=y_test,
        returns_test=returns_test,
        experiment_id="exp_eval_01",
        snapshot_sha256="abc123sha",
        symbol="BTCUSDT",
        timeframe="5m",
        horizon_minutes=30,
        test_start_time_ms=1700000000000,
        test_end_time_ms=1700015000000,
        y_train=y_train,
    )
    assert report.directional_metrics.sample_count == 50
    assert 0.0 <= report.directional_metrics.accuracy <= 1.0
    assert 0.0 <= report.directional_metrics.brier_score <= 1.0
    assert len(report.calibration_bins) == 5

    # Strictly check cost-adjusted fields status
    for field, status in report.cost_adjusted_fields_status.items():
        assert status == "UNAVAILABLE_PENDING_SLIPPAGE_METHOD"

    md = report.to_markdown()
    assert "# Research Report: exp_eval_01" in md
    assert "UNAVAILABLE_PENDING_SLIPPAGE_METHOD" in md


def test_experiment_runner_deterministic_reproducibility(tmp_path: Path):
    snap_dir = tmp_path / "snapshots"
    models_dir = tmp_path / "models"
    reports_dir = tmp_path / "reports"

    # Create synthetic snapshot with 250 candles
    candles = create_synthetic_candle_series(250)
    snap_storage = SnapshotStorage(snapshots_dir=snap_dir)
    snap_path, snap_hash = snap_storage.save_snapshot(candles, "BINANCE", "BTCUSDT", "5m")

    from shootingstar.adapters.db.session import get_db_session
    from shootingstar.adapters.db.models import SnapshotModel, ExperimentModel
    from shootingstar.adapters.db.repository import SnapshotRepository
    import uuid
    exp_id_1 = f"exp_rep_{uuid.uuid4().hex[:10]}"
    exp_id_2 = f"exp_rep_{uuid.uuid4().hex[:10]}"
    created_snapshot = False

    with get_db_session() as s:
        s_repo = SnapshotRepository(s)
        existing_snap = s.get(SnapshotModel, snap_hash)
        if not existing_snap:
            snap_rec = SnapshotModel(
                id=snap_hash,
                venue="BINANCE",
                symbol="BTCUSDT",
                timeframe="5m",
                start_time_ms=candles[0].open_time_ms,
                end_time_ms=candles[-1].close_time_ms,
                candle_count=len(candles),
                file_path=str(snap_path),
                sha256=snap_hash,
            )
            s_repo.save(snap_rec)
            s.commit()
            created_snapshot = True
    try:
        runner = ExperimentRunner(
            snapshot_storage=snap_storage,
            models_dir=models_dir,
            reports_dir=reports_dir,
        )

        # First run
        rep1, art_path1, art_hash1 = runner.run_experiment(snap_path, exp_id_1)

        # Second run with identical config
        rep2, art_path2, art_hash2 = runner.run_experiment(snap_path, exp_id_2)
        # Gate verification: Identical metric reproduction
        assert rep1.directional_metrics.accuracy == rep2.directional_metrics.accuracy
        assert rep1.directional_metrics.brier_score == rep2.directional_metrics.brier_score
        assert rep1.directional_metrics.up_count == rep2.directional_metrics.up_count
    finally:
        with get_db_session() as s:
            from shootingstar.adapters.db.models import (
                ExperimentSplitModel,
                MetricReportModel,
                ModelArtifactModel,
            )
            from sqlalchemy import delete
            s.execute(delete(ExperimentSplitModel).where(ExperimentSplitModel.experiment_id.in_([exp_id_1, exp_id_2])))
            s.execute(delete(MetricReportModel).where(MetricReportModel.experiment_id.in_([exp_id_1, exp_id_2])))
            s.execute(delete(ModelArtifactModel).where(ModelArtifactModel.experiment_id.in_([exp_id_1, exp_id_2])))
            s.execute(delete(ExperimentModel).where(ExperimentModel.id.in_([exp_id_1, exp_id_2])))
            if created_snapshot:
                s.execute(delete(SnapshotModel).where(SnapshotModel.id == snap_hash))
            s.commit()

def test_baseline_train_only_fitting_no_test_leakage():
    """Proves majority class baseline depends strictly on y_train, not held-out y_test."""
    X_test = np.random.randn(20, 4)
    # Test set is 95% DOWN (19 DOWN, 1 UP to satisfy log_loss multi-class requirements)
    y_test = np.array([0] * 19 + [1], dtype=int)
    # Train set is 100% UP
    y_train_up = np.ones(40, dtype=int)

    model = CalibratedLogisticRegressionModel()
    X_dummy = np.random.randn(20, 4)
    y_dummy = np.array([0, 1] * 10)
    model.fit_and_calibrate(X_dummy, y_dummy, X_dummy, y_dummy)

    report = EvaluationReportGenerator.generate_report(
        model=model,
        X_test=X_test,
        y_test=y_test,
        returns_test=np.zeros(20),
        experiment_id="exp_leak_check",
        snapshot_sha256="hash123",
        symbol="BTCUSDT",
        timeframe="5m",
        horizon_minutes=30,
        test_start_time_ms=1000,
        test_end_time_ms=2000,
        y_train=y_train_up,
    )

    maj_baseline = next(b for b in report.baseline_comparisons if b["name"] == "Majority_Class")
    # If baseline fit y_test (95% DOWN), accuracy would be 0.95.
    # Since it strictly fit y_train (100% UP), it predicts all UP, matching only 1/20 (accuracy 0.05)!
    assert maj_baseline["accuracy"] == 0.05


def test_walk_forward_splitter_timeframes_anti_leakage():
    """Verifies purge gaps are dynamically derived to prevent lookahead leakage."""
    from shootingstar.application.splits import WalkForwardSplitter

    # 5m candles -> 30m horizon is 6 samples
    splitter_5m = WalkForwardSplitter.for_timeframe("5m", horizon_minutes=30)
    assert splitter_5m.purge_gap_samples == 6

    # 1m candles -> 30m horizon is 30 samples
    splitter_1m = WalkForwardSplitter.for_timeframe("1m", horizon_minutes=30)
    assert splitter_1m.purge_gap_samples == 30

    # Verify split boundaries have zero overlap and exact gap
    timestamps = list(range(0, 300 * 60000, 60000))  # 300 1m timestamps
    splits = splitter_1m.split(timestamps)
    assert splits.train.end_idx + 30 < splits.calibration.start_idx
    assert splits.calibration.end_idx + 30 < splits.validation.start_idx
    assert splits.validation.end_idx + 30 < splits.test.start_idx
