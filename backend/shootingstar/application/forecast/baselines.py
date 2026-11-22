"""Cost-free direction baselines."""

from shootingstar.domain.models import Candle, Timeframe


def always_up() -> str:
    return "UP"


def momentum_6h(candles: list[Candle], t_ms: int) -> str | None:
    """Compare latest closed prices at t and t-6h; gaps and ties have no direction."""
    def close_at(timestamp: int) -> Candle | None:
        eligible = [c for c in candles if c.close_time_ms <= timestamp]
        if not eligible:
            return None
        latest = max(eligible, key=lambda c: c.close_time_ms)
        return latest if timestamp - latest.close_time_ms <= Timeframe(latest.timeframe).duration_ms else None

    current = close_at(t_ms)
    previous = close_at(t_ms - 6 * 3_600_000)
    if current is None or previous is None or current.close == previous.close:
        return None
    return "UP" if current.close > previous.close else "DOWN"
