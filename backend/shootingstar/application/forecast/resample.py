"""Aggregate complete UTC-aligned candle buckets without looking ahead."""

from collections import defaultdict
from dataclasses import replace

from shootingstar.domain.models import Candle

_DURATIONS = {"1m": 60_000, "5m": 300_000, "15m": 900_000, "1h": 3_600_000, "4h": 14_400_000}


def resample(candles: list[Candle], timeframe: str, t_ms: int) -> list[Candle]:
    """Return complete buckets, omitting incomplete, duplicate and unclosed buckets."""
    if timeframe not in ("15m", "1h", "4h"):
        raise ValueError("Unsupported target timeframe")
    available = [c for c in candles if c.close_time_ms <= t_ms]
    if not available:
        return []
    source = available[0].timeframe
    if source not in _DURATIONS or _DURATIONS[source] >= _DURATIONS[timeframe]:
        raise ValueError("Unsupported source timeframe")
    step, duration = _DURATIONS[source], _DURATIONS[timeframe]
    groups: dict[int, list[Candle]] = defaultdict(list)
    for candle in available:
        if (candle.timeframe, candle.venue, candle.symbol) != (source, available[0].venue, available[0].symbol):
            raise ValueError("Candles must have the same timeframe, venue and symbol")
        start = candle.open_time_ms // duration * duration
        if start + duration - 1 <= t_ms:
            groups[start].append(candle)
    result = []
    for start, group in sorted(groups.items()):
        group.sort(key=lambda c: c.open_time_ms)
        if len(group) != duration // step or any(
            c.open_time_ms != start + i * step or c.close_time_ms != c.open_time_ms + step - 1
            for i, c in enumerate(group)
        ):
            continue
        first, last = group[0], group[-1]
        result.append(replace(first, timeframe=timeframe, close_time_ms=last.close_time_ms,
            high=max(c.high for c in group), low=min(c.low for c in group), close=last.close,
            volume=sum(c.volume for c in group), quote_volume=sum(c.quote_volume for c in group),
            trades_count=sum(c.trades_count for c in group),
            taker_buy_base_volume=sum(c.taker_buy_base_volume for c in group),
            taker_buy_quote_volume=sum(c.taker_buy_quote_volume for c in group),
            observed_ingested_at_ms=None, is_backfill=any(c.is_backfill for c in group)))
    return result
