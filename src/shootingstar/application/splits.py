"""Chronological split generator for time-series walk-forward evaluation.

STRICT INVARIANT: No lookahead leakage across split boundaries.
Enforces a purging gap between splits at least equal to prediction horizon (30 minutes).
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass(frozen=True)
class SplitWindow:
    split_type: str  # "TRAIN", "CALIBRATION", "VALIDATION", "TEST"
    start_idx: int
    end_idx: int  # inclusive
    start_time_ms: int
    end_time_ms: int
    sample_count: int


@dataclass(frozen=True)
class ExperimentSplits:
    train: SplitWindow
    calibration: SplitWindow
    validation: SplitWindow
    test: SplitWindow


class WalkForwardSplitter:
    """Splits chronological samples into strictly ordered Train, Calibration, Validation, and Test windows."""

    def __init__(
        self,
        train_ratio: float = 0.50,
        calibration_ratio: float = 0.15,
        validation_ratio: float = 0.15,
        test_ratio: float = 0.20,
        purge_gap_samples: int = 6,  # 6 * 5m = 30m horizon gap between splits
    ):
        total = train_ratio + calibration_ratio + validation_ratio + test_ratio
        if abs(total - 1.0) > 1e-5:
            raise ValueError(f"Split ratios must sum to 1.0 (got {total})")

        self.train_ratio = train_ratio
        self.calibration_ratio = calibration_ratio
        self.validation_ratio = validation_ratio
        self.test_ratio = test_ratio
        self.purge_gap_samples = purge_gap_samples

    def split(self, timestamps_ms: List[int]) -> ExperimentSplits:
        n = len(timestamps_ms)
        min_required = (self.purge_gap_samples * 3) + 40
        if n < min_required:
            raise ValueError(f"Sample count {n} is too small for 4-way purged split (minimum {min_required})")

        n_usable = n - (self.purge_gap_samples * 3)
        n_train = int(n_usable * self.train_ratio)
        n_calib = int(n_usable * self.calibration_ratio)
        n_val = int(n_usable * self.validation_ratio)
        n_test = n_usable - (n_train + n_calib + n_val)

        # 1. Train window
        t_start = 0
        t_end = t_start + n_train - 1
        train = SplitWindow("TRAIN", t_start, t_end, timestamps_ms[t_start], timestamps_ms[t_end], n_train)

        # 2. Calibration window (after gap)
        c_start = t_end + 1 + self.purge_gap_samples
        c_end = c_start + n_calib - 1
        calib = SplitWindow("CALIBRATION", c_start, c_end, timestamps_ms[c_start], timestamps_ms[c_end], n_calib)

        # 3. Validation window (after gap)
        v_start = c_end + 1 + self.purge_gap_samples
        v_end = v_start + n_val - 1
        val = SplitWindow("VALIDATION", v_start, v_end, timestamps_ms[v_start], timestamps_ms[v_end], n_val)

        # 4. Test window (after gap)
        test_start = v_end + 1 + self.purge_gap_samples
        test_end = n - 1
        n_test_actual = test_end - test_start + 1
        test = SplitWindow("TEST", test_start, test_end, timestamps_ms[test_start], timestamps_ms[test_end], n_test_actual)

        return ExperimentSplits(
            train=train,
            calibration=calib,
            validation=val,
            test=test,
        )
