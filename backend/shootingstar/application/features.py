"""Causal feature engineering service for 30-minute prediction research.

STRICT INVARIANT: Leakage-free. For prediction time t, strictly consumes candles
where available_at <= t.
"""

from dataclasses import dataclass
import math
from typing import Dict, List, Optional, Tuple
import numpy as np

from shootingstar.domain.models import Candle


@dataclass(frozen=True)
class FeatureMatrix:
    feature_names: List[str]
    timestamps_ms: List[int]  # Effective availability timestamps (effective_available_at_ms)
    candle_open_times_ms: List[int]  # Originating candle open times
    values: np.ndarray  # Shape: (N, num_features)

class FeatureExtractionService:
    """Computes technical, structural, and momentum features strictly causally."""

    FEATURE_NAMES = [
        "ret_1",
        "ret_2",
        "ret_3",
        "ret_6",
        "ret_12",
        "volume_ratio_20",
        "volatility_12",
        "volatility_24",
        "sma_ratio_10_30",
        "sma_ratio_20_60",
        "rsi_14",
        "body_ratio",
        "upper_wick_ratio",
        "lower_wick_ratio",
    ]

    WARMUP_PERIODS = 65  # Requires at least 65 bars for SMA(60) and 24-bar volatility

    def __init__(self, assumed_latency_ms: Optional[int] = 1000):
        self.assumed_latency_ms = assumed_latency_ms

    @classmethod
    def compute_features_at_index(cls, candles: List[Candle], index: int) -> Optional[List[float]]:
        """Computes feature vector for the single candle at `index` using only candles[:index+1].
        
        Guarantees zero future leakage by slicing up to `index+1` strictly.
        """
        if index < cls.WARMUP_PERIODS:
            return None

        history = candles[: index + 1]
        closes = np.array([c.close for c in history], dtype=np.float64)
        opens = np.array([c.open for c in history], dtype=np.float64)
        highs = np.array([c.high for c in history], dtype=np.float64)
        lows = np.array([c.low for c in history], dtype=np.float64)
        volumes = np.array([c.volume for c in history], dtype=np.float64)

        # 1. Lagged returns
        c_curr = closes[-1]
        ret_1 = (c_curr - closes[-2]) / closes[-2]
        ret_2 = (c_curr - closes[-3]) / closes[-3]
        ret_3 = (c_curr - closes[-4]) / closes[-4]
        ret_6 = (c_curr - closes[-7]) / closes[-7]
        ret_12 = (c_curr - closes[-13]) / closes[-13]

        # 2. Volume ratio
        vol_mean_20 = np.mean(volumes[-20:])
        volume_ratio_20 = volumes[-1] / (vol_mean_20 + 1e-9)

        # 3. Volatility (std of 1-bar returns)
        bar_returns = np.diff(closes) / closes[:-1]
        volatility_12 = float(np.std(bar_returns[-12:]))
        volatility_24 = float(np.std(bar_returns[-24:]))

        # 4. Moving average ratios
        sma_10 = np.mean(closes[-10:])
        sma_30 = np.mean(closes[-30:])
        sma_ratio_10_30 = (sma_10 / sma_30) - 1.0

        sma_20 = np.mean(closes[-20:])
        sma_60 = np.mean(closes[-60:])
        sma_ratio_20_60 = (sma_20 / sma_60) - 1.0

        # 5. RSI 14
        deltas = np.diff(closes[-15:])
        gains = np.where(deltas > 0, deltas, 0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)
        avg_gain = np.mean(gains[-14:])
        avg_loss = np.mean(losses[-14:])
        if avg_loss == 0:
            rsi_14 = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi_14 = 100.0 - (100.0 / (1.0 + rs))

        # 6. Candle morphology
        c_last = closes[-1]
        o_last = opens[-1]
        h_last = highs[-1]
        l_last = lows[-1]
        rng = h_last - l_last + 1e-9
        body_ratio = abs(c_last - o_last) / rng
        upper_wick_ratio = (h_last - max(o_last, c_last)) / rng
        lower_wick_ratio = (min(o_last, c_last) - l_last) / rng

        return [
            float(ret_1),
            float(ret_2),
            float(ret_3),
            float(ret_6),
            float(ret_12),
            float(volume_ratio_20),
            float(volatility_12),
            float(volatility_24),
            float(sma_ratio_10_30),
            float(sma_ratio_20_60),
            float(rsi_14),
            float(body_ratio),
            float(upper_wick_ratio),
            float(lower_wick_ratio),
        ]

    def extract_matrix(self, candles: List[Candle]) -> FeatureMatrix:
        sorted_candles = sorted(candles, key=lambda c: c.open_time_ms)
        rows: List[List[float]] = []
        avail_timestamps: List[int] = []
        open_timestamps: List[int] = []

        for i in range(len(sorted_candles)):
            vec = self.compute_features_at_index(sorted_candles, i)
            if vec is not None:
                # Causal contract: determine effective availability
                avail_ms = sorted_candles[i].effective_available_at_ms(assumed_latency_ms=self.assumed_latency_ms)
                if avail_ms is None:
                    # Invariant: drop unknown availability rows (never fall back to open_time_ms!)
                    continue
                rows.append(vec)
                avail_timestamps.append(avail_ms)
                open_timestamps.append(sorted_candles[i].open_time_ms)

        if not rows:
            return FeatureMatrix(
                feature_names=self.FEATURE_NAMES,
                timestamps_ms=[],
                candle_open_times_ms=[],
                values=np.empty((0, len(self.FEATURE_NAMES)), dtype=np.float64),
            )

        return FeatureMatrix(
            feature_names=self.FEATURE_NAMES,
            timestamps_ms=avail_timestamps,
            candle_open_times_ms=open_timestamps,
            values=np.array(rows, dtype=np.float64),
        )
