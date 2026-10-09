"""Label generation service for 30-minute forward prediction research."""

from dataclasses import dataclass
from typing import List, Optional
from shootingstar.domain.exceptions import DomainError
from shootingstar.domain.models import Candle, Timeframe


@dataclass(frozen=True)
class TargetLabel:
    candle_index: int
    open_time_t_ms: int
    close_time_t_ms: int
    entry_time_ms: int
    horizon_minutes: int
    entry_price: float
    target_price: float
    return_30m: float
    direction_label: str  # "UP" or "DOWN" or "FLAT"
    cost_adjusted_label: Optional[str]  # None until slippage methodology is approved

class LabelGenerationService:
    """Generates directional forward target returns for 30-minute research."""

    def __init__(
        self,
        horizon_minutes: int = 30,
        assumed_latency_ms: int = 1000,
        execution_price_mode: str = "open_next",  # "open_next" (conservative) or "close_t"
    ):
        self.horizon_minutes = horizon_minutes
        self.assumed_latency_ms = assumed_latency_ms
        self.execution_price_mode = execution_price_mode

    def generate_labels(self, candles: List[Candle]) -> List[TargetLabel]:
        if not candles:
            return []

        # Sort strictly by open_time_ms
        sorted_candles = sorted(candles, key=lambda c: c.open_time_ms)
        tf = Timeframe(sorted_candles[0].timeframe)
        horizon_ms = self.horizon_minutes * 60 * 1000
        steps_forward = horizon_ms // tf.duration_ms

        if steps_forward <= 0:
            raise DomainError(f"Horizon {self.horizon_minutes}m is smaller than candle timeframe {tf.value}")

        labels: List[TargetLabel] = []

        for i in range(len(sorted_candles) - steps_forward):
            c_t = sorted_candles[i]
            target_idx = i + steps_forward
            c_target = sorted_candles[target_idx]

            # Invariant check on time continuity
            expected_target_time = c_t.open_time_ms + horizon_ms
            if c_target.open_time_ms != expected_target_time:
                # Interval gap detected between t and t+30m; skip this sample to prevent corrupted return
                continue

            if self.execution_price_mode == "open_next":
                # Conservative: enter at open of candle (i + 1) following availability at t
                c_entry = sorted_candles[i + 1]
                entry_p = c_entry.open
                entry_time = c_entry.open_time_ms
            else:
                entry_p = c_t.close
                entry_time = c_t.close_time_ms
            target_p = c_target.close
            ret_30m = (target_p - entry_p) / entry_p

            if ret_30m > 0:
                direction = "UP"
            elif ret_30m < 0:
                direction = "DOWN"
            else:
                direction = "FLAT"

            labels.append(
                TargetLabel(
                    candle_index=i,
                    open_time_t_ms=c_t.open_time_ms,
                    close_time_t_ms=c_t.close_time_ms,
                    entry_time_ms=entry_time,
                    horizon_minutes=self.horizon_minutes,
                    entry_price=entry_p,
                    target_price=target_p,
                    return_30m=ret_30m,
                    direction_label=direction,
                    cost_adjusted_label=None,  # Strictly None pending approved slippage method
                )
            )

        return labels
