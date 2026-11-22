"""Tests for cost-free baselines and retrospective outcome scoring."""

from datetime import datetime, timezone

import pytest

from shootingstar.application.forecast.baselines import always_up, momentum_6h
from shootingstar.application.forecast.outcome import (
    evaluate_direction_outcome,
    possible_memorization,
)
from shootingstar.domain.models import Candle

SIX_HOURS_MS = 6 * 3_600_000


def make_candle(close_time_ms, close):
    return Candle(
        venue="BINANCE",
        symbol="BTCUSDT",
        timeframe="1m",
        open_time_ms=close_time_ms - 59_999,
        close_time_ms=close_time_ms,
        open=close,
        high=close,
        low=close,
        close=close,
        volume=1.0,
        quote_volume=close,
        trades_count=1,
        taker_buy_base_volume=0.5,
        taker_buy_quote_volume=close / 2,
    )


def test_always_up_returns_up():
    assert always_up() == "UP"


def test_momentum_6h_up():
    t_ms = 20 * 3_600_000
    candles = [make_candle(t_ms - SIX_HOURS_MS, 100.0), make_candle(t_ms, 110.0)]
    assert momentum_6h(candles, t_ms) == "UP"


def test_momentum_6h_down():
    t_ms = 20 * 3_600_000
    candles = [make_candle(t_ms - SIX_HOURS_MS, 110.0), make_candle(t_ms, 100.0)]
    assert momentum_6h(candles, t_ms) == "DOWN"


def test_momentum_6h_tie_is_none():
    t_ms = 20 * 3_600_000
    candles = [make_candle(t_ms - SIX_HOURS_MS, 100.0), make_candle(t_ms, 100.0)]
    assert momentum_6h(candles, t_ms) is None


def test_momentum_6h_gap_is_none():
    t_ms = 20 * 3_600_000
    # The latest candle before (t - 6h) is two minutes too old, so it is a gap.
    stale = make_candle(t_ms - SIX_HOURS_MS - 120_000, 100.0)
    candles = [stale, make_candle(t_ms, 110.0)]
    assert momentum_6h(candles, t_ms) is None


def test_outcome_up_with_half_percent_threshold():
    t_ms = 0
    target = t_ms + 360 * 60_000
    candle = make_candle(target + 59_999, 101.5)  # +1.5% against 100.
    result = evaluate_direction_outcome([candle], t_ms, 360, 100.0, flat_threshold_pct=0.5)
    assert result["outcome"] == "UP"
    assert result["move_pct"] == pytest.approx(1.5)


def test_outcome_down_with_half_percent_threshold():
    t_ms = 0
    target = t_ms + 360 * 60_000
    candle = make_candle(target + 59_999, 98.8)  # -1.2% against 100.
    result = evaluate_direction_outcome([candle], t_ms, 360, 100.0, flat_threshold_pct=0.5)
    assert result["outcome"] == "DOWN"
    assert result["move_pct"] == pytest.approx(-1.2)


def test_outcome_flat_with_half_percent_threshold():
    t_ms = 0
    target = t_ms + 360 * 60_000
    candle = make_candle(target + 59_999, 100.3)  # +0.3% against 100.
    result = evaluate_direction_outcome([candle], t_ms, 360, 100.0, flat_threshold_pct=0.5)
    assert result["outcome"] == "FLAT"
    assert result["move_pct"] == pytest.approx(0.3)


def test_outcome_missing_target_candle_is_unscorable():
    result = evaluate_direction_outcome([], 0, 360, 100.0, flat_threshold_pct=0.5)
    assert result["outcome"] == "UNSCORABLE"
    assert result["target_price"] is None
    assert result["move_pct"] is None


def _ms(year, month, day):
    return int(datetime(year, month, day, tzinfo=timezone.utc).timestamp() * 1000)


def test_possible_memorization_before_cutoff():
    assert possible_memorization(_ms(2024, 12, 15), "gemini-2.5-flash") is True


def test_possible_memorization_after_cutoff():
    assert possible_memorization(_ms(2025, 3, 15), "gemini-2.5-flash") is False


def test_possible_memorization_unknown_model_is_false():
    assert possible_memorization(_ms(2024, 12, 15), "unknown-model") is False
