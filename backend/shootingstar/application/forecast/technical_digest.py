"""Deterministic causal multi-timeframe digest.

EMA slopes are one-bar percentage changes. Swing levels are extrema of the
last 24 completed hourly bars; range position uses completed hourly bars.
EMA warm-up uses at least 207 hourly bars, including history before the lookback.
"""

import hashlib
import json
import math
from typing import TypedDict

import numpy as np

from shootingstar.application.forecast.errors import InsufficientHistoryError
from shootingstar.application.forecast.indicators import atr, ema, macd, rsi, volume_ratio
from shootingstar.application.forecast.resample import resample
from shootingstar.domain.models import Candle


class Feature(TypedDict):
    feature_id: str
    timeframe: str
    name: str
    value: float | None
    unit: str


class TechnicalDigest(TypedDict):
    features: list[Feature]
    digest_hash: str


def _continuous(bars: list[Candle], count: int, duration: int) -> list[Candle]:
    bars = bars[-count:]
    if len(bars) < count or any(b.open_time_ms - a.open_time_ms != duration for a, b in zip(bars, bars[1:])):
        raise InsufficientHistoryError("Insufficient continuous completed candle history")
    return bars


def build_technical_digest(candles: list[Candle], t_ms: int, lookback_days: int = 14) -> TechnicalDigest:
    """Build bounded JSON-compatible features from candles closed by t_ms only."""
    if not isinstance(lookback_days, int) or lookback_days < 1:
        raise ValueError("lookback_days must be a positive integer")
    hourly = resample(candles, "1h", t_ms)
    quarter = resample(candles, "15m", t_ms)
    hours = lookback_days * 24
    hourly = _continuous(hourly, max(hours + 1, 168, 207), 3_600_000)
    quarter = _continuous(quarter, 96, 900_000)
    if t_ms - hourly[-1].close_time_ms >= 3_600_000 or t_ms - quarter[-1].close_time_ms >= 900_000:
        raise InsufficientHistoryError("Latest completed candle bucket is stale")
    four = resample(hourly, "4h", t_ms)
    four = _continuous(four, len(four), 14_400_000)
    if len(four) < 51:
        raise InsufficientHistoryError("EMA50 4h slope requires 51 complete 4h bars")
    features: list[Feature] = []

    def add(timeframe: str, name: str, value: float | None, unit: str) -> None:
        if value is not None:
            value = float(value)
            if not math.isfinite(value):
                raise InsufficientHistoryError(f"Indicator {name} lacks warm-up")
            value = round(value, 8)
        features.append({"feature_id": f"{timeframe}_{name}", "timeframe": timeframe,
                         "name": name, "value": value, "unit": unit})

    close = np.array([c.close for c in hourly])
    for timeframe, bars in (("1h", hourly), ("4h", four)):
        prices = np.array([c.close for c in bars])
        for period in (20, 50):
            values = ema(prices, period)
            add(timeframe, f"ema{period}_slope", (values[-1] / values[-2] - 1) * 100, "%")
    add("1h", "rsi14", rsi(close)[-1], "index")
    add("15m", "rsi14", rsi([c.close for c in quarter])[-1], "index")
    add("1h", "macd_hist", macd(close)[2][-1], "price")
    add("1h", "atr14_pct", atr([c.high for c in hourly], [c.low for c in hourly], close)[-1] / close[-1] * 100, "%")
    add("1h", "volume_ratio20", volume_ratio([c.volume for c in hourly]), "ratio")
    for count, label in dict.fromkeys(((24, "24h"), (168, "7d"), (hours, f"{lookback_days}d"))):
        bars = hourly[-count:]
        low, high = min(c.low for c in bars), max(c.high for c in bars)
        add("1h", f"range_position_{label}", (close[-1] - low) / (high - low) if high > low else None, "ratio")
    add("1h", "swing_high_24h", max(c.high for c in hourly[-24:]), "price")
    add("1h", "swing_low_24h", min(c.low for c in hourly[-24:]), "price")
    for count in (6, 24):
        add("1h", f"return_{count}h", (close[-1] / close[-count - 1] - 1) * 100, "%")
    add("1h", f"return_{lookback_days}d", (close[-1] / close[-hours - 1] - 1) * 100, "%")
    encoded = json.dumps(features, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return {"features": features, "digest_hash": hashlib.sha256(encoded).hexdigest()}
