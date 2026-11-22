"""Retrospective outcome and model-knowledge cutoff."""

import math

from shootingstar.domain.models import Candle

MODEL_KNOWLEDGE_CUTOFF_MS = {"gemini-2.5-flash": 1_738_368_000_000}


def possible_memorization(t_ms: int, model_id: str) -> bool:
    """Unknown models have no known cutoff and are not flagged."""
    cutoff = MODEL_KNOWLEDGE_CUTOFF_MS.get(model_id)
    return cutoff is not None and t_ms < cutoff


def evaluate_direction_outcome(candles: list[Candle], t_ms: int, horizon_minutes: int,
                               purchase_price: float, flat_threshold_pct: float = 0.5) -> dict:
    """Compare purchase price to close of the candle containing t + horizon."""
    if not math.isfinite(purchase_price) or purchase_price <= 0 or horizon_minutes <= 0:
        raise ValueError("purchase price and horizon must be positive")
    if not math.isfinite(flat_threshold_pct) or flat_threshold_pct < 0:
        raise ValueError("flat threshold must be nonnegative")
    target = t_ms + horizon_minutes * 60_000
    candle = next((c for c in candles if c.open_time_ms <= target <= c.close_time_ms), None)
    if candle is None:
        return {"outcome": "UNSCORABLE", "target_price": None, "move_pct": None}
    move = (candle.close - purchase_price) / purchase_price * 100
    direction = "FLAT" if abs(move) < flat_threshold_pct or move == 0 else "UP" if move > 0 else "DOWN"
    return {"outcome": direction, "target_price": candle.close, "move_pct": move}
