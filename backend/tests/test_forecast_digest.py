"""Tests for candle resampling, the causal digest and agreement scoring."""

import pytest

from shootingstar.application.forecast.errors import InsufficientHistoryError
from shootingstar.application.forecast.agreement_score import agreement_score
from shootingstar.application.forecast.resample import resample
from shootingstar.application.forecast.technical_digest import build_technical_digest
from shootingstar.domain.models import Candle

MINUTE_MS = 60_000
DIGEST_MINUTES = 207 * 60  # 207 completed hourly bars, the minimum warm-up.


def make_candle(open_time_ms, close, open_=None, high=None, low=None, volume=1.0):
    open_ = close if open_ is None else open_
    high = max(open_, close) + 0.5 if high is None else high
    low = min(open_, close) - 0.5 if low is None else low
    return Candle(
        venue="BINANCE",
        symbol="BTCUSDT",
        timeframe="1m",
        open_time_ms=open_time_ms,
        close_time_ms=open_time_ms + MINUTE_MS - 1,
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
        quote_volume=volume * close,
        trades_count=10,
        taker_buy_base_volume=volume / 2,
        taker_buy_quote_volume=volume * close / 2,
    )


def make_series(start_ms, minutes, base=1000.0, step=0.01):
    return [make_candle(start_ms + i * MINUTE_MS, base + i * step) for i in range(minutes)]


def test_resample_1m_to_15m_ohlcv():
    candles = [
        make_candle(i * MINUTE_MS, 100.5 + i, open_=100 + i, high=101 + i, low=99 + i)
        for i in range(15)
    ]
    bars = resample(candles, "15m", 15 * MINUTE_MS - 1)
    assert len(bars) == 1
    bar = bars[0]
    assert bar.timeframe == "15m"
    assert bar.open_time_ms == 0
    assert bar.close_time_ms == 15 * MINUTE_MS - 1
    assert bar.open == pytest.approx(100)
    assert bar.high == pytest.approx(115)
    assert bar.low == pytest.approx(99)
    assert bar.close == pytest.approx(114.5)
    assert bar.volume == pytest.approx(15.0)
    assert bar.trades_count == 150


def test_resample_1m_to_1h_ohlcv():
    candles = [
        make_candle(i * MINUTE_MS, 1000.5 + i, open_=1000 + i, high=1001 + i, low=999 + i)
        for i in range(60)
    ]
    bars = resample(candles, "1h", 60 * MINUTE_MS - 1)
    assert len(bars) == 1
    bar = bars[0]
    assert bar.timeframe == "1h"
    assert bar.open_time_ms == 0
    assert bar.close_time_ms == 60 * MINUTE_MS - 1
    assert bar.open == pytest.approx(1000)
    assert bar.high == pytest.approx(1060)
    assert bar.low == pytest.approx(999)
    assert bar.close == pytest.approx(1059.5)
    assert bar.volume == pytest.approx(60.0)


def test_resample_excludes_bucket_not_closed_at_t():
    candles = [make_candle(i * MINUTE_MS, 100.0) for i in range(15)]
    assert resample(candles, "15m", 15 * MINUTE_MS - 2) == []


def test_resample_excludes_incomplete_bucket():
    candles = [make_candle(i * MINUTE_MS, 100.0) for i in range(15) if i != 7]
    assert resample(candles, "15m", 15 * MINUTE_MS - 1) == []


def test_digest_is_causal_when_candles_are_added_after_t():
    candles = make_series(0, DIGEST_MINUTES)
    t_ms = DIGEST_MINUTES * MINUTE_MS - 1
    baseline = build_technical_digest(candles, t_ms, lookback_days=7)

    future = make_series(t_ms + 1, 30, base=9000.0, step=10.0)
    changed = build_technical_digest(candles + future, t_ms, lookback_days=7)

    assert changed == baseline
    assert changed["digest_hash"] == baseline["digest_hash"]


def test_digest_has_lookback_features_and_hash():
    candles = make_series(0, DIGEST_MINUTES)
    t_ms = DIGEST_MINUTES * MINUTE_MS - 1
    digest = build_technical_digest(candles, t_ms, lookback_days=7)
    names = {feature["name"] for feature in digest["features"]}
    assert {"range_position_7d", "return_7d", "return_6h"} <= names
    assert len(digest["digest_hash"]) == 64


def test_digest_short_history_raises():
    # 100 hourly bars are below the 207-bar warm-up minimum.
    candles = make_series(0, 100 * 60)
    with pytest.raises(InsufficientHistoryError):
        build_technical_digest(candles, 100 * 60 * MINUTE_MS - 1, lookback_days=7)


def test_digest_empty_history_raises():
    with pytest.raises(InsufficientHistoryError):
        build_technical_digest([], 0, lookback_days=7)


def _feature(name, value):
    return {"feature_id": f"1h_{name}", "timeframe": "1h", "name": name, "value": value, "unit": "x"}


def test_agreement_score_counts_documented_votes():
    digest = {
        "features": [
            _feature("ema20_slope", 1.0),  # above 0: up
            _feature("ema50_slope", -1.0),  # below 0: down
            _feature("macd_hist", 0.0),  # equal to 0: no vote
            _feature("return_6h", None),  # missing: no vote
            _feature("rsi14", 55.0),  # above 50: up
            _feature("rsi14", 45.0),  # below 50: down
            _feature("atr14_pct", 999.0),  # not a voting feature
            _feature("range_position_7d", -5.0),  # not a voting feature
        ],
        "digest_hash": "deadbeef",
    }
    assert agreement_score(digest) == {"up": 2, "down": 2, "total": 4}
