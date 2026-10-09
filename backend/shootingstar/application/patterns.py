"""Rule-based Pattern Lab: declarative candle pattern detection and forward return analysis.

STRICT INVARIANT: Separate hypothesis track. Pattern rules are NOT mixed into classifier
features without standalone ablation.
"""

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional
import numpy as np

from shootingstar.domain.models import Candle, Timeframe


@dataclass(frozen=True)
class PatternHit:
    rule_name: str
    candle_index: int
    detected_time_ms: int
    close_price: float
    forward_30m_return: Optional[float]
    outcome_label: Optional[str]  # "UP" or "DOWN"
    is_success: Optional[bool]


@dataclass(frozen=True)
class PatternAnalysisReport:
    rule_name: str
    rule_description: str
    sample_count: int
    expected_direction: str  # "UP" or "DOWN"
    success_count: int
    failure_count: int
    win_rate: float
    mean_return_30m: float
    std_return_30m: float
    min_return_30m: float
    max_return_30m: float
    statistical_power_warning: bool
    warning_message: Optional[str]
    hits: List[PatternHit]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_name": self.rule_name,
            "rule_description": self.rule_description,
            "sample_count": self.sample_count,
            "expected_direction": self.expected_direction,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "win_rate": self.win_rate,
            "mean_return_30m": self.mean_return_30m,
            "std_return_30m": self.std_return_30m,
            "min_return_30m": self.min_return_30m,
            "max_return_30m": self.max_return_30m,
            "statistical_power_warning": self.statistical_power_warning,
            "warning_message": self.warning_message,
        }


class PatternRule:
    name: str
    description: str
    expected_direction: str  # "UP" or "DOWN"

    def matches(self, candles: List[Candle], index: int) -> bool:
        raise NotImplementedError


class ShootingStarRule(PatternRule):
    """Bearish reversal: Small real body near bottom, long upper shadow (>=2x body), tiny lower shadow."""

    name = "Shooting_Star"
    description = "Small real body near low, upper shadow >= 2x body, lower shadow <= 15% range, prior uptrend"
    expected_direction = "DOWN"

    def matches(self, candles: List[Candle], index: int) -> bool:
        if index < 3:
            return False

        c = candles[index]
        rng = c.high - c.low
        if rng <= 1e-8:
            return False

        body = abs(c.close - c.open)
        upper_wick = c.high - max(c.open, c.close)
        lower_wick = min(c.open, c.close) - c.low

        body_ratio = body / rng
        upper_wick_ratio = upper_wick / rng
        lower_wick_ratio = lower_wick / rng

        # Strict rules
        is_small_body = body_ratio <= 0.35
        is_long_upper_wick = upper_wick_ratio >= 0.55 and upper_wick >= (2.0 * body)
        is_small_lower_wick = lower_wick_ratio <= 0.15

        # Prior short-term uptrend: close higher than 3 bars ago
        prior_uptrend = candles[index - 1].close > candles[index - 3].close

        return is_small_body and is_long_upper_wick and is_small_lower_wick and prior_uptrend


class HammerRule(PatternRule):
    """Bullish reversal: Small real body near top, long lower shadow (>=2x body), tiny upper shadow."""

    name = "Hammer"
    description = "Small real body near high, lower shadow >= 2x body, upper shadow <= 15% range, prior downtrend"
    expected_direction = "UP"

    def matches(self, candles: List[Candle], index: int) -> bool:
        if index < 3:
            return False

        c = candles[index]
        rng = c.high - c.low
        if rng <= 1e-8:
            return False

        body = abs(c.close - c.open)
        upper_wick = c.high - max(c.open, c.close)
        lower_wick = min(c.open, c.close) - c.low

        body_ratio = body / rng
        upper_wick_ratio = upper_wick / rng
        lower_wick_ratio = lower_wick / rng

        is_small_body = body_ratio <= 0.35
        is_long_lower_wick = lower_wick_ratio >= 0.55 and lower_wick >= (2.0 * body)
        is_small_upper_wick = upper_wick_ratio <= 0.15

        # Prior short-term downtrend
        prior_downtrend = candles[index - 1].close < candles[index - 3].close

        return is_small_body and is_long_lower_wick and is_small_upper_wick and prior_downtrend


class BearishEngulfingRule(PatternRule):
    """Bearish engulfing: Bullish candle followed by larger bearish candle completely engulfing prior body."""

    name = "Bearish_Engulfing"
    description = "Prior candle green, current candle red, current real body completely covers prior body"
    expected_direction = "DOWN"

    def matches(self, candles: List[Candle], index: int) -> bool:
        if index < 1:
            return False

        c_prev = candles[index - 1]
        c_curr = candles[index]

        is_prev_bullish = c_prev.close > c_prev.open
        is_curr_bearish = c_curr.close < c_curr.open

        if not (is_prev_bullish and is_curr_bearish):
            return False

        # Engulfing: current open >= prev close and current close <= prev open
        engulfs_body = (c_curr.open >= c_prev.close) and (c_curr.close <= c_prev.open)
        # Distinct body size
        significant_body = abs(c_curr.close - c_curr.open) > abs(c_prev.close - c_prev.open)

        return engulfs_body and significant_body


class BullishEngulfingRule(PatternRule):
    """Bullish engulfing: Bearish candle followed by larger bullish candle completely engulfing prior body."""

    name = "Bullish_Engulfing"
    description = "Prior candle red, current candle green, current real body completely covers prior body"
    expected_direction = "UP"

    def matches(self, candles: List[Candle], index: int) -> bool:
        if index < 1:
            return False

        c_prev = candles[index - 1]
        c_curr = candles[index]

        is_prev_bearish = c_prev.close < c_prev.open
        is_curr_bullish = c_curr.close > c_curr.open

        if not (is_prev_bearish and is_curr_bullish):
            return False

        engulfs_body = (c_curr.open <= c_prev.close) and (c_curr.close >= c_prev.open)
        significant_body = abs(c_curr.close - c_curr.open) > abs(c_prev.close - c_prev.open)

        return engulfs_body and significant_body


class PatternLabService:
    """Detects candle patterns and rigorously computes forward 30m return statistics."""

    RULES: List[PatternRule] = [
        ShootingStarRule(),
        HammerRule(),
        BearishEngulfingRule(),
        BullishEngulfingRule(),
    ]

    def analyze_pattern(
        self,
        candles: List[Candle],
        rule: PatternRule,
        horizon_minutes: int = 30,
    ) -> PatternAnalysisReport:
        if not candles:
            return PatternAnalysisReport(
                rule_name=rule.name,
                rule_description=rule.description,
                sample_count=0,
                expected_direction=rule.expected_direction,
                success_count=0,
                failure_count=0,
                win_rate=0.0,
                mean_return_30m=0.0,
                std_return_30m=0.0,
                min_return_30m=0.0,
                max_return_30m=0.0,
                statistical_power_warning=True,
                warning_message="Zero samples detected.",
                hits=[],
            )

        sorted_candles = sorted(candles, key=lambda c: c.open_time_ms)
        tf = Timeframe(sorted_candles[0].timeframe)
        steps_forward = (horizon_minutes * 60 * 1000) // tf.duration_ms

        hits: List[PatternHit] = []
        returns: List[float] = []
        successes = 0
        failures = 0

        for i in range(len(sorted_candles) - steps_forward):
            if rule.matches(sorted_candles, i):
                c_hit = sorted_candles[i]
                c_future = sorted_candles[i + steps_forward]

                # Ensure time continuity
                expected_time = c_hit.open_time_ms + (steps_forward * tf.duration_ms)
                if c_future.open_time_ms != expected_time:
                    continue

                ret_30m = (c_future.close - c_hit.close) / c_hit.close
                returns.append(ret_30m)

                direction = "UP" if ret_30m > 0 else "DOWN" if ret_30m < 0 else "FLAT"

                is_success = (direction == rule.expected_direction)
                if is_success:
                    successes += 1
                else:
                    failures += 1

                hits.append(
                    PatternHit(
                        rule_name=rule.name,
                        candle_index=i,
                        detected_time_ms=c_hit.open_time_ms,
                        close_price=c_hit.close,
                        forward_30m_return=ret_30m,
                        outcome_label=direction,
                        is_success=is_success,
                    )
                )

        n = len(hits)
        has_warning = n < 30
        warning_msg = (
            f"LOW SAMPLE SIZE WARNING (N={n} < 30): Statistical power is insufficient to claim pattern predictive efficacy."
            if has_warning else None
        )

        win_rate = (successes / n) if n > 0 else 0.0
        mean_ret = float(np.mean(returns)) if returns else 0.0
        std_ret = float(np.std(returns)) if returns else 0.0
        min_ret = float(np.min(returns)) if returns else 0.0
        max_ret = float(np.max(returns)) if returns else 0.0

        return PatternAnalysisReport(
            rule_name=rule.name,
            rule_description=rule.description,
            sample_count=n,
            expected_direction=rule.expected_direction,
            success_count=successes,
            failure_count=failures,
            win_rate=win_rate,
            mean_return_30m=mean_ret,
            std_return_30m=std_ret,
            min_return_30m=min_ret,
            max_return_30m=max_ret,
            statistical_power_warning=has_warning,
            warning_message=warning_msg,
            hits=hits,
        )

    def analyze_all(
        self,
        candles: List[Candle],
        horizon_minutes: int = 30,
    ) -> List[PatternAnalysisReport]:
        return [self.analyze_pattern(candles, rule, horizon_minutes) for rule in self.RULES]
