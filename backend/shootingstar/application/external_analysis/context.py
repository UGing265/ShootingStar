"""Causal 6-hour windowing and context serializers (Variants A and B)."""

import math
from typing import Any, Dict, List, Optional
from shootingstar.domain.exceptions import DomainError
from shootingstar.domain.models import Candle, Timeframe


class InsufficientHistoryError(DomainError):
    """Raised when available historical data before t is less than 6 hours or has gaps."""
    pass


def extract_causal_window(
    candles: List[Candle],
    t_ms: int,
    window_hours: float = 6.0,
    assumed_latency_ms: int = 1000,
) -> List[Candle]:
    """Extracts strictly available candles within [t - 6h, t].

    STRICT INVARIANTS:
    1. available_at <= t: No candle closing after t or within latency margin.
    2. Zero lookahead leakage: Candles with open_time_ms > t or close_time_ms > t are strictly rejected.
    3. Minimum duration: The sliced window must span at least window_hours (6.0h).
    4. Continuity: Time-series gaps greater than 2 bars trigger InsufficientHistoryError.
    """
    if not candles:
        raise InsufficientHistoryError("No candles available in snapshot.")

    # 1. Filter candles available at or before t
    available = [
        c for c in candles
        if (c.close_time_ms + assumed_latency_ms) <= t_ms and c.close_time_ms <= t_ms
    ]

    if not available:
        raise InsufficientHistoryError(f"No completed candles available at t={t_ms} with latency={assumed_latency_ms}ms.")

    # Sort chronologically
    available.sort(key=lambda c: c.open_time_ms)

    tf = Timeframe(available[0].timeframe)
    required_span_ms = int(window_hours * 3600 * 1000)

    # 2. Check if the latest available candle is reasonably close to t (within 2 bars)
    latest_candle = available[-1]
    if (t_ms - latest_candle.close_time_ms) > (2 * tf.duration_ms + assumed_latency_ms):
        raise InsufficientHistoryError(
            f"Latest available candle ended at {latest_candle.close_time_ms}, too far from target t={t_ms}."
        )

    # 3. Slice window of [t_ms - required_span_ms, t_ms]
    cutoff_start_ms = latest_candle.close_time_ms - required_span_ms
    window_candles = [c for c in available if c.open_time_ms >= cutoff_start_ms]

    if not window_candles:
        raise InsufficientHistoryError("No candles fall into the 6-hour pre-t window.")

    # Verify actual time span covered
    actual_span_ms = window_candles[-1].close_time_ms - window_candles[0].open_time_ms
    # Allow small tolerance for discrete candle durations
    if actual_span_ms < (required_span_ms - tf.duration_ms):
        raise InsufficientHistoryError(
            f"Insufficient history duration: window covers {actual_span_ms / (3600 * 1000):.2f}h, "
            f"required at least {window_hours:.1f}h."
        )

    # 4. Invariant check on time continuity (no large gaps)
    for i in range(len(window_candles) - 1):
        gap_ms = window_candles[i + 1].open_time_ms - window_candles[i].close_time_ms - 1
        if gap_ms > tf.duration_ms:
            raise InsufficientHistoryError(
                f"Time-series gap detected in 6-hour window between {window_candles[i].close_time_ms} "
                f"and {window_candles[i + 1].open_time_ms}."
            )

    return window_candles


def build_context_a(candles: List[Candle], snapshot_hash: str) -> Dict[str, Any]:
    """Builds Context Variant A: Clean ordered 6-hour OHLCV sequence."""
    return {
        "variant": "A",
        "snapshot_hash": snapshot_hash,
        "candle_count": len(candles),
        "timeframe": candles[0].timeframe if candles else "unknown",
        "start_time_ms": candles[0].open_time_ms if candles else 0,
        "end_time_ms": candles[-1].close_time_ms if candles else 0,
        "candles": [
            {
                "open_time_ms": c.open_time_ms,
                "close_time_ms": c.close_time_ms,
                "open": c.open,
                "high": c.high,
                "low": c.low,
                "close": c.close,
                "volume": c.volume,
            }
            for c in candles
        ],
    }


def build_context_b(
    candles: List[Candle],
    purchase_price_p: float,
    snapshot_hash: str,
    tail_candles_count: int = 6,
) -> Dict[str, Any]:
    """Builds Context Variant B: Deterministic summary metrics + recent tail bars."""
    if not candles:
        return {"variant": "B", "error": "No candles"}

    latest_close = candles[-1].close
    highs = [c.high for c in candles]
    lows = [c.low for c in candles]
    highest_price = max(highs)
    lowest_price = min(lows)
    total_volume = sum(c.volume for c in candles)

    # Returns for standard periods if available
    def _calc_return(lookback_bars: int) -> Optional[float]:
        if len(candles) > lookback_bars:
            p_past = candles[-1 - lookback_bars].close
            return (latest_close - p_past) / p_past if p_past > 0 else None
        return None

    tf = Timeframe(candles[0].timeframe)
    bars_15m = max(1, 15 * 60 * 1000 // tf.duration_ms)
    bars_1h = max(1, 60 * 60 * 1000 // tf.duration_ms)
    bars_3h = max(1, 180 * 60 * 1000 // tf.duration_ms)
    bars_6h = len(candles) - 1

    tail_bars = [
        {
            "open_time_ms": c.open_time_ms,
            "close_time_ms": c.close_time_ms,
            "open": c.open,
            "high": c.high,
            "low": c.low,
            "close": c.close,
            "volume": c.volume,
        }
        for c in candles[-tail_candles_count:]
    ]

    p_deviation = (latest_close - purchase_price_p) / purchase_price_p if purchase_price_p > 0 else 0.0

    return {
        "variant": "B",
        "snapshot_hash": snapshot_hash,
        "candle_count": len(candles),
        "timeframe": candles[0].timeframe,
        "latest_close": latest_close,
        "purchase_price_p": purchase_price_p,
        "price_deviation_vs_p": p_deviation,
        "highest_6h": highest_price,
        "lowest_6h": lowest_price,
        "total_volume_6h": total_volume,
        "returns": {
            "ret_15m": _calc_return(bars_15m),
            "ret_1h": _calc_return(bars_1h),
            "ret_3h": _calc_return(bars_3h),
            "ret_6h": (latest_close - candles[0].open) / candles[0].open if candles[0].open > 0 else 0.0,
        },
        "tail_candles": tail_bars,
    }
