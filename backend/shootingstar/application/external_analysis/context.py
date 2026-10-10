"""Causal 6-hour windowing and context serializers (Variants A and B)."""

import hashlib
import json
import math
from typing import Any, Dict, List, Optional
from shootingstar.application.external_analysis.contracts import (
    FeedCandle,
    FeedContract,
    FeedCoverage,
    FeedFeature,
)
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

def build_feed_contract(
    candles: List[Candle],
    snapshot_id: str,
    snapshot_checksum: str,
    prediction_time_t_ms: int,
    purchase_price_p: float,
    horizon_minutes: int = 30,
    assumed_latency_ms: int = 1000,
) -> FeedContract:
    """Builds strictly validated FeedContract v1 from causal 6-hour window."""
    window_candles = extract_causal_window(
        candles=candles,
        t_ms=prediction_time_t_ms,
        window_hours=6.0,
        assumed_latency_ms=assumed_latency_ms,
    )

    timeframe = window_candles[0].timeframe
    symbol = window_candles[0].symbol
    start_ms = window_candles[0].open_time_ms
    end_ms = window_candles[-1].close_time_ms

    # Canonical feed candles
    feed_candles = [
        FeedCandle(
            candle_id=f"{snapshot_id}_{timeframe}_{c.open_time_ms}",
            open_time_ms=c.open_time_ms,
            close_time_ms=c.close_time_ms,
            open=float(c.open),
            high=float(c.high),
            low=float(c.low),
            close=float(c.close),
            volume=float(c.volume),
        )
        for c in window_candles
    ]

    required_span_ms = int(6.0 * 3600 * 1000)
    observed_span_ms = end_ms - start_ms
    coverage = FeedCoverage(
        required_span_ms=required_span_ms,
        observed_span_ms=observed_span_ms,
        gaps_count=0,
        invalid_rows_count=0,
        status="COMPLETE",
    )

    latest_close = window_candles[-1].close
    highs = [c.high for c in window_candles]
    lows = [c.low for c in window_candles]
    highest_p = max(highs)
    lowest_p = min(lows)
    total_vol = sum(c.volume for c in window_candles)
    p_dev = (latest_close - purchase_price_p) / purchase_price_p if purchase_price_p > 0 else 0.0
    volatility_pct = (highest_p - lowest_p) / lowest_p if lowest_p > 0 else 0.0

    last_c = window_candles[-1]
    last_id = feed_candles[-1].candle_id
    rng = last_c.high - last_c.low
    body = abs(last_c.close - last_c.open)
    upper_wick = last_c.high - max(last_c.open, last_c.close)
    lower_wick = min(last_c.open, last_c.close) - last_c.low

    # 1h lookback bars
    tf = Timeframe(timeframe)
    bars_1h = max(1, 60 * 60 * 1000 // tf.duration_ms)
    ret_1h = 0.0
    if len(window_candles) > bars_1h:
        past_c = window_candles[-1 - bars_1h].close
        ret_1h = (latest_close - past_c) / past_c if past_c > 0 else 0.0

    features = [
        FeedFeature(
            feature_id="latest_close_vs_p_pct",
            value=round(p_dev, 6),
            unit="ratio",
            formula_version="v1",
            source_candle_ids=[last_id],
        ),
        FeedFeature(
            feature_id="range_high_6h",
            value=round(highest_p, 4),
            unit="price",
            formula_version="v1",
            source_candle_ids=[feed_candles[highs.index(highest_p)].candle_id],
        ),
        FeedFeature(
            feature_id="range_low_6h",
            value=round(lowest_p, 4),
            unit="price",
            formula_version="v1",
            source_candle_ids=[feed_candles[lows.index(lowest_p)].candle_id],
        ),
        FeedFeature(
            feature_id="volatility_6h_pct",
            value=round(volatility_pct, 6),
            unit="ratio",
            formula_version="v1",
            source_candle_ids=[feed_candles[0].candle_id, last_id],
        ),
        FeedFeature(
            feature_id="total_volume_6h",
            value=round(total_vol, 4),
            unit="volume",
            formula_version="v1",
            source_candle_ids=[c.candle_id for c in feed_candles],
        ),
        FeedFeature(
            feature_id="return_1h",
            value=round(ret_1h, 6),
            unit="ratio",
            formula_version="v1",
            source_candle_ids=[feed_candles[-1 - min(bars_1h, len(feed_candles) - 1)].candle_id, last_id],
        ),
        FeedFeature(
            feature_id="last_candle_body_ratio",
            value=round(body / rng, 6) if rng > 1e-8 else 0.0,
            unit="ratio",
            formula_version="v1",
            source_candle_ids=[last_id],
        ),
        FeedFeature(
            feature_id="last_candle_upper_wick_ratio",
            value=round(upper_wick / rng, 6) if rng > 1e-8 else 0.0,
            unit="ratio",
            formula_version="v1",
            source_candle_ids=[last_id],
        ),
        FeedFeature(
            feature_id="last_candle_lower_wick_ratio",
            value=round(lower_wick / rng, 6) if rng > 1e-8 else 0.0,
            unit="ratio",
            formula_version="v1",
            source_candle_ids=[last_id],
        ),
    ]

    # Deterministic feed hash
    hash_material = f"feed_v1:{snapshot_id}:{snapshot_checksum}:{symbol}:{timeframe}:{prediction_time_t_ms}:{purchase_price_p}:{horizon_minutes}:{start_ms}:{end_ms}:{len(feed_candles)}"
    feed_hash = hashlib.sha256(hash_material.encode("utf-8")).hexdigest()
    feed_id = f"feed_{feed_hash[:16]}"

    return FeedContract(
        feed_id=feed_id,
        feed_version="v1",
        feed_hash=feed_hash,
        snapshot_id=snapshot_id,
        snapshot_checksum=snapshot_checksum,
        symbol=symbol,
        timeframe=timeframe,
        prediction_time_t_ms=prediction_time_t_ms,
        purchase_price_p=purchase_price_p,
        horizon_minutes=horizon_minutes,
        context_start_open_time_ms=start_ms,
        context_end_close_time_ms=end_ms,
        assumed_latency_ms=assumed_latency_ms,
        candles=feed_candles,
        coverage=coverage,
        features=features,
    )


def feed_contract_to_dict(feed: FeedContract) -> Dict[str, Any]:
    """Serializes FeedContract into dict suitable for JSON payload or storage."""
    return {
        "feed_id": feed.feed_id,
        "feed_version": feed.feed_version,
        "feed_hash": feed.feed_hash,
        "snapshot_id": feed.snapshot_id,
        "snapshot_checksum": feed.snapshot_checksum,
        "symbol": feed.symbol,
        "timeframe": feed.timeframe,
        "prediction_time_t_ms": feed.prediction_time_t_ms,
        "purchase_price_p": feed.purchase_price_p,
        "horizon_minutes": feed.horizon_minutes,
        "context_start_open_time_ms": feed.context_start_open_time_ms,
        "context_end_close_time_ms": feed.context_end_close_time_ms,
        "assumed_latency_ms": feed.assumed_latency_ms,
        "candle_count": len(feed.candles),
        "candles": [
            {
                "candle_id": c.candle_id,
                "open_time_ms": c.open_time_ms,
                "close_time_ms": c.close_time_ms,
                "open": c.open,
                "high": c.high,
                "low": c.low,
                "close": c.close,
                "volume": c.volume,
            }
            for c in feed.candles
        ],
        "coverage": {
            "required_span_ms": feed.coverage.required_span_ms,
            "observed_span_ms": feed.coverage.observed_span_ms,
            "gaps_count": feed.coverage.gaps_count,
            "invalid_rows_count": feed.coverage.invalid_rows_count,
            "status": feed.coverage.status,
        },
        "features": [
            {
                "feature_id": f.feature_id,
                "value": f.value,
                "unit": f.unit,
                "formula_version": f.formula_version,
                "source_candle_ids": f.source_candle_ids,
            }
            for f in feed.features
        ],
    }
