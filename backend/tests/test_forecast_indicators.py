"""Hand-computed tests for the causal forecast indicators."""

import numpy as np
import pytest

from shootingstar.application.forecast.indicators import atr, ema, macd, rsi, volume_ratio


def test_ema_matches_hand_calculation():
    # values [1, 2, 3, 4], period 3.
    # Warm-up indexes 0 and 1 are NaN.
    # Seed at index 2: mean(1, 2, 3) = 2.0; alpha = 2/(3+1) = 0.5.
    # Index 3: 0.5*4 + 0.5*2.0 = 3.0.
    result = ema([1, 2, 3, 4], 3)
    assert np.isnan(result[0]) and np.isnan(result[1])
    assert result[2] == pytest.approx(2.0)
    assert result[3] == pytest.approx(3.0)


def test_ema_short_series_is_all_nan():
    result = ema([1, 2], 3)
    assert np.all(np.isnan(result))


def test_rsi_matches_hand_calculation():
    # values [1, 3, 2, 4], period 2.
    # deltas [2, -1, 2], gains [2, 0, 2], losses [0, 1, 0].
    # Seed gain = mean(2, 0) = 1.0, loss = mean(0, 1) = 0.5.
    # Index 2 = 100 - 100/(1 + 1.0/0.5) = 66.6666667.
    # Index 3: gain = (1.0*1 + 2)/2 = 1.5, loss = (0.5*1 + 0)/2 = 0.25,
    # so RSI = 100 - 100/(1 + 1.5/0.25) = 85.7142857.
    result = rsi([1, 3, 2, 4], 2)
    assert np.isnan(result[0]) and np.isnan(result[1])
    assert result[2] == pytest.approx(100 - 100 / 3)
    assert result[3] == pytest.approx(100 - 100 / 7)


def test_rsi_zero_loss_is_100():
    result = rsi([1, 2, 3, 4], 2)
    assert result[-1] == pytest.approx(100.0)


def test_rsi_flat_series_is_50():
    result = rsi([5, 5, 5], 2)
    assert result[-1] == pytest.approx(50.0)


def test_rsi_short_series_is_all_nan():
    result = rsi([1, 2], 2)
    assert np.all(np.isnan(result))


def test_macd_matches_hand_calculation():
    # fast EMA(2), slow EMA(3), signal EMA(2) on [1, 2, 3, 4, 5, 6].
    # ema2 = [nan, 1.5, 2.5, 3.5, 4.5, 5.5]
    # ema3 = [nan, nan, 2.0, 3.0, 4.0, 5.0]
    # line = [nan, nan, 0.5, 0.5, 0.5, 0.5]
    # signal is seeded on line[2:] = [nan, 0.5, 0.5, 0.5]
    # histogram = line - signal = [nan, nan, nan, 0, 0, 0]
    line, signal, hist = macd([1, 2, 3, 4, 5, 6], fast=2, slow=3, signal=2)
    assert np.all(np.isnan(line[:2]))
    assert np.allclose(line[2:], 0.5)
    assert np.all(np.isnan(signal[:3]))
    assert np.allclose(signal[3:], 0.5)
    assert np.all(np.isnan(hist[:3]))
    assert np.allclose(hist[3:], 0.0)


def test_atr_matches_hand_calculation():
    # high [10, 12, 11, 13], low [8, 9, 8, 9], close [9, 11, 9, 12], period 3.
    # TR = [2, max(3, 3, 0), max(3, 0, 3), max(4, 4, 0)] = [2, 3, 3, 4].
    # Seed at index 2 = mean([2, 3, 3]) = 8/3.
    # Index 3 = (8/3 * 2 + 4) / 3 = 28/9.
    result = atr([10, 12, 11, 13], [8, 9, 8, 9], [9, 11, 9, 12], 3)
    assert np.isnan(result[0]) and np.isnan(result[1])
    assert result[2] == pytest.approx(8 / 3)
    assert result[3] == pytest.approx(28 / 9)


def test_atr_short_series_is_all_nan():
    result = atr([10, 12], [8, 9], [9, 11], 3)
    assert np.all(np.isnan(result))


def test_volume_ratio_matches_hand_calculation():
    # Last volume 3 divided by mean([1, 2, 3]) = 2 gives 1.5.
    assert volume_ratio([1, 2, 3], period=3) == pytest.approx(1.5)


def test_volume_ratio_zero_mean_is_none():
    assert volume_ratio([0, 0, 0], period=3) is None


def test_volume_ratio_short_series_is_none():
    assert volume_ratio([1, 2], period=3) is None
