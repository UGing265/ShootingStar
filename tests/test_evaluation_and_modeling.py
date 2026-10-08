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

    runner = ExperimentRunner(
        snapshot_storage=snap_storage,
        models_dir=models_dir,
        reports_dir=reports_dir,
    )

    # First run
    rep1, art_path1, art_hash1 = runner.run_experiment(snap_path, "exp_rep_1")

    # Second run with identical config
    rep2, art_path2, art_hash2 = runner.run_experiment(snap_path, "exp_rep_2")

    # Gate verification: Identical metric reproduction
    assert rep1.directional_metrics.accuracy == rep2.directional_metrics.accuracy
    assert rep1.directional_metrics.brier_score == rep2.directional_metrics.brier_score
    assert rep1.directional_metrics.up_count == rep2.directional_metrics.up_count
