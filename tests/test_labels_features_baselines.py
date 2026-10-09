"""Tests for labels, causal feature extraction, leakage boundaries, and baselines."""

import numpy as np
import pytest
from shootingstar.application.baselines import (
    AlwaysDownBaseline,
    AlwaysUpBaseline,
    BaselineEvaluator,
    MajorityClassBaseline,
    SimpleMomentumBaseline,
)
from shootingstar.application.features import FeatureExtractionService
from shootingstar.application.labels import LabelGenerationService
from shootingstar.domain.models import Candle


def create_synthetic_candles(count: int, start_time: int = 1700000000000, tf_ms: int = 300000) -> list[Candle]:
    """Generates synthetic 5m candles for deterministic testing."""
    candles = []
    base_price = 50000.0
    for i in range(count):
        open_time = start_time + (i * tf_ms)
        close_time = open_time + tf_ms - 1
        # Oscillating synthetic price path
        drift = (i % 7) * 10.0
        p_open = base_price + drift
        p_high = p_open + 25.0
        p_low = p_open - 20.0
        p_close = p_open + 5.0
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
                volume=10.0 + (i % 5),
                quote_volume=(10.0 + (i % 5)) * p_close,
                trades_count=100,
                taker_buy_base_volume=5.0,
                taker_buy_quote_volume=250000.0,
            )
        )
    return candles


def test_label_generation_30m_horizon_and_direction():
    candles = create_synthetic_candles(30)  # 30 candles of 5m = 150 minutes
    service = LabelGenerationService(horizon_minutes=30, execution_price_mode="open_next")

    labels = service.generate_labels(candles)

    # 30 minutes in 5m timeframe = 6 steps.
    # Total labels should be 30 - 6 = 24
    assert len(labels) == 24

    for lbl in labels:
        assert lbl.horizon_minutes == 30
        assert lbl.direction_label in ("UP", "DOWN", "FLAT")
        # Invariant: cost_adjusted_label must be None until slippage method is approved
        assert lbl.cost_adjusted_label is None


def test_feature_extraction_zero_future_leakage_boundary():
    """CRITICAL TEST: Perturbing future candles past index t must NEVER change features at t."""
    candles = create_synthetic_candles(100)
    service = FeatureExtractionService()

    eval_idx = 75  # Candle index to evaluate
    features_before = service.compute_features_at_index(candles, eval_idx)
    assert features_before is not None

    # Severely perturb all future candles from index 76 to 99 (10x prices and volume)
    perturbed_candles = list(candles[: eval_idx + 1])
    for i in range(eval_idx + 1, len(candles)):
        c = candles[i]
        perturbed_candles.append(
            Candle(
                venue=c.venue,
                symbol=c.symbol,
                timeframe=c.timeframe,
                open_time_ms=c.open_time_ms,
                close_time_ms=c.close_time_ms,
                open=c.open * 10.0,
                high=c.high * 15.0,
                low=c.low * 8.0,
                close=c.close * 12.0,
                volume=c.volume * 100.0,
                quote_volume=c.quote_volume * 1000.0,
                trades_count=c.trades_count * 10,
                taker_buy_base_volume=c.taker_buy_base_volume * 100.0,
                taker_buy_quote_volume=c.taker_buy_quote_volume * 1000.0,
            )
        )

    features_after = service.compute_features_at_index(perturbed_candles, eval_idx)
    assert features_after is not None

    # Assert 100% bit-for-bit exact identity: zero leakage from future data
    assert np.array_equal(features_before, features_after)


def test_feature_matrix_determinism():
    candles = create_synthetic_candles(80)
    service = FeatureExtractionService()

    mat1 = service.extract_matrix(candles)
    mat2 = service.extract_matrix(candles)

    assert mat1.feature_names == mat2.feature_names
    assert mat1.timestamps_ms == mat2.timestamps_ms
    assert np.array_equal(mat1.values, mat2.values)


def test_baselines_and_spot_trade_accounting():
    X_test = np.array([[0.01], [-0.01], [0.02], [-0.02]])
    y_test = np.array([1, 0, 1, 0])
    returns_test = np.array([0.015, -0.012, 0.025, -0.018])

    # 1. Always UP
    up_model = AlwaysUpBaseline()
    up_metrics = BaselineEvaluator.evaluate(up_model, X_test, y_test, returns_test)
    assert up_metrics.accuracy == 0.50
    assert up_metrics.up_predictions_count == 4
    # Realized returns when UP always bought: sum of all returns
    assert pytest.approx(up_metrics.spot_cumulative_return, rel=1e-5) == sum(returns_test)

    # 2. Always DOWN
    down_model = AlwaysDownBaseline()
    down_metrics = BaselineEvaluator.evaluate(down_model, X_test, y_test, returns_test)
    assert down_metrics.accuracy == 0.50
    assert down_metrics.up_predictions_count == 0
    # Spot invariant: DOWN prediction stands aside in cash, realizing 0.0 return!
    assert down_metrics.spot_cumulative_return == 0.0
    assert down_metrics.spot_mean_return_per_signal == 0.0

    # 3. Simple Momentum
    mom_model = SimpleMomentumBaseline()
    mom_metrics = BaselineEvaluator.evaluate(mom_model, X_test, y_test, returns_test)
    assert mom_metrics.accuracy == 1.0  # Perfectly matches signs in this test set
    assert mom_metrics.spot_cumulative_return == 0.015 + 0.025  # Only positive trades entered


def test_target_label_entry_time_causality():
    candles = create_synthetic_candles(10)
    service = LabelGenerationService(horizon_minutes=30, execution_price_mode="open_next")
    labels = service.generate_labels(candles)

    assert len(labels) > 0
    for lbl in labels:
        # Invariant: open_next enters strictly at candle i+1's open, which is after close of candle i
        assert lbl.entry_time_ms > lbl.close_time_t_ms
        assert lbl.entry_time_ms == lbl.close_time_t_ms + 1


def test_feature_extraction_drops_unknown_availability():
    candles = create_synthetic_candles(10)
    # Candles without observed_ingested_at_ms and assumed_latency_ms=None
    service = FeatureExtractionService(assumed_latency_ms=None)
    mat = service.extract_matrix(candles)

    # Invariant: rows without verified availability timestamp MUST be dropped
    assert len(mat.values) == 0
    assert len(mat.timestamps_ms) == 0
    assert len(mat.candle_open_times_ms) == 0


def test_experiment_drops_trades_when_latency_exceeds_entry_time():
    # If assumed_latency_ms exceeds the gap to next candle open (e.g. latency = 5000ms),
    # entering at candle i+1 open is impossible without lookahead.
    # The runner must drop these causally invalid samples.
    candles = create_synthetic_candles(150)
    feat_service = FeatureExtractionService(assumed_latency_ms=5000)
    feat_mat = feat_service.extract_matrix(candles)

    label_service = LabelGenerationService(horizon_minutes=30, execution_price_mode="open_next")
    labels = label_service.generate_labels(candles)
    label_map = {lbl.open_time_t_ms: lbl for lbl in labels}

    valid_aligned_count = 0
    for i, open_t in enumerate(feat_mat.candle_open_times_ms):
        if open_t in label_map:
            lbl = label_map[open_t]
            avail_t = feat_mat.timestamps_ms[i]
            if lbl.entry_time_ms >= avail_t:
                valid_aligned_count += 1

    # With 5000ms latency, avail_t is close_time + 5000ms, which is > next open (close + 1ms).
    # All such samples must be rejected!
    assert valid_aligned_count == 0
