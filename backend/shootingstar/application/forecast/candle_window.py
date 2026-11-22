"""Bound forecast input without scanning a sorted snapshot."""

from bisect import bisect_left, bisect_right
from operator import attrgetter

from shootingstar.domain.models import Candle, Timeframe


def candle_window(candles: list[Candle], t_ms: int, lookback_days: int = 14,
                  horizon_minutes: int = 360) -> list[Candle]:
    """Slice sorted candles, retaining warm-up and the target-containing bar."""
    if not candles:
        return []
    if lookback_days < 1 or horizon_minutes < 1:
        raise ValueError("lookback and horizon must be positive")
    bar_ms = Timeframe(candles[0].timeframe).duration_ms
    start = t_ms - (max(lookback_days, 9) + 1) * 86_400_000
    end = t_ms + horizon_minutes * 60_000 + bar_ms
    key = attrgetter("open_time_ms")
    return candles[bisect_left(candles, start, key=key):bisect_right(candles, end, key=key)]
