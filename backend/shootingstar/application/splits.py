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

    @classmethod
    def for_timeframe(
        cls,
        timeframe: str,
        horizon_minutes: int = 30,
        train_ratio: float = 0.50,
        calibration_ratio: float = 0.15,
        validation_ratio: float = 0.15,
        test_ratio: float = 0.20,
    ) -> "WalkForwardSplitter":
        """Calculates exact purge_gap_samples to prevent label lookahead leakage."""
        tf_mins = 1 if timeframe == "1m" else 5
        gap = max(1, horizon_minutes // tf_mins)
        return cls(
            train_ratio=train_ratio,
            calibration_ratio=calibration_ratio,
            validation_ratio=validation_ratio,
            test_ratio=test_ratio,
            purge_gap_samples=gap,
        )

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


@dataclass(frozen=True)
class CandidateWindowSplit:
    window_name: str  # e.g. "30d", "60d", "90d"
    window_duration_ms: int
    train: Optional[SplitWindow]
    calibration: Optional[SplitWindow]
    validation: Optional[SplitWindow]
    test: SplitWindow
    is_eligible: bool
    ineligibility_reason: Optional[str] = None


@dataclass(frozen=True)
class RollingEvaluationPeriod:
    period_id: str
    test_start_ms: int
    test_end_ms: int
    candidate_splits: List[CandidateWindowSplit]


class RollingWindowSplitter:
    """Generates multi-period rolling evaluation windows to compare candidate training history lengths.
    
    STRICT INVARIANT:
    - All candidate windows for a given period are tested on the EXACT same test samples.
    - Purge gap is strictly enforced at every boundary.
    - If a candidate window lacks sufficient historical data prior to the cutoff, it is marked
      ineligible rather than silently altered.
    """

    def __init__(
        self,
        candidate_window_days: List[int],
        test_period_days: int = 7,
        calib_days: int = 3,
        val_days: int = 4,
        timeframe: str = "1m",
        horizon_minutes: int = 30,
    ):
        self.candidate_window_days = sorted(candidate_window_days)
        self.test_period_days = test_period_days
        self.calib_days = calib_days
        self.val_days = val_days
        self.timeframe = timeframe
        self.horizon_minutes = horizon_minutes

        tf_mins = 1 if timeframe == "1m" else 5
        self.purge_gap_samples = max(1, horizon_minutes // tf_mins)

    def generate_periods(
        self,
        timestamps_ms: List[int],
        num_periods: int = 3,
    ) -> List[RollingEvaluationPeriod]:
        if not timestamps_ms:
            return []

        n = len(timestamps_ms)
        day_ms = 86400 * 1000
        test_dur_ms = self.test_period_days * day_ms
        calib_dur_ms = self.calib_days * day_ms
        val_dur_ms = self.val_days * day_ms

        total_span_ms = timestamps_ms[-1] - timestamps_ms[0]
        min_required_window_ms = (min(self.candidate_window_days) * day_ms) + calib_dur_ms + val_dur_ms + test_dur_ms
        if total_span_ms < min_required_window_ms:
            return []

        periods: List[RollingEvaluationPeriod] = []

        # Build evaluation periods moving backward from latest data
        for p_idx in range(num_periods):
            # Target test end
            offset_ms = p_idx * test_dur_ms
            target_test_end_ms = timestamps_ms[-1] - offset_ms
            target_test_start_ms = target_test_end_ms - test_dur_ms

            # Find indices for test window
            test_indices = [i for i, ts in enumerate(timestamps_ms) if target_test_start_ms <= ts <= target_test_end_ms]
            if len(test_indices) < 20:
                continue

            test_start_idx = test_indices[0]
            test_end_idx = test_indices[-1]
            test_window = SplitWindow(
                split_type="TEST",
                start_idx=test_start_idx,
                end_idx=test_end_idx,
                start_time_ms=timestamps_ms[test_start_idx],
                end_time_ms=timestamps_ms[test_end_idx],
                sample_count=len(test_indices),
            )

            # Validation window precedes test (separated by purge gap)
            val_end_idx = test_start_idx - 1 - self.purge_gap_samples
            if val_end_idx < 0:
                continue
            val_cutoff_ms = timestamps_ms[val_end_idx]
            target_val_start_ms = val_cutoff_ms - val_dur_ms
            val_indices = [i for i in range(val_end_idx + 1) if timestamps_ms[i] >= target_val_start_ms]
            if len(val_indices) < 10:
                continue
            val_start_idx = val_indices[0]
            val_window = SplitWindow(
                split_type="VALIDATION",
                start_idx=val_start_idx,
                end_idx=val_end_idx,
                start_time_ms=timestamps_ms[val_start_idx],
                end_time_ms=timestamps_ms[val_end_idx],
                sample_count=len(val_indices),
            )

            # Calibration window precedes validation (separated by purge gap)
            calib_end_idx = val_start_idx - 1 - self.purge_gap_samples
            if calib_end_idx < 0:
                continue
            calib_cutoff_ms = timestamps_ms[calib_end_idx]
            target_calib_start_ms = calib_cutoff_ms - calib_dur_ms
            calib_indices = [i for i in range(calib_end_idx + 1) if timestamps_ms[i] >= target_calib_start_ms]
            if len(calib_indices) < 10:
                continue
            calib_start_idx = calib_indices[0]
            calib_window = SplitWindow(
                split_type="CALIBRATION",
                start_idx=calib_start_idx,
                end_idx=calib_end_idx,
                start_time_ms=timestamps_ms[calib_start_idx],
                end_time_ms=timestamps_ms[calib_end_idx],
                sample_count=len(calib_indices),
            )

            # Effective cutoff for all training: before calibration (separated by purge gap)
            train_end_idx = calib_start_idx - 1 - self.purge_gap_samples
            if train_end_idx < 0:
                continue
            train_cutoff_ms = timestamps_ms[train_end_idx]

            candidate_splits: List[CandidateWindowSplit] = []
            for days in self.candidate_window_days:
                window_name = f"{days}d"
                win_dur_ms = days * day_ms
                target_train_start_ms = train_cutoff_ms - win_dur_ms

                train_indices = [i for i in range(train_end_idx + 1) if timestamps_ms[i] >= target_train_start_ms]
                if not train_indices:
                    candidate_splits.append(
                        CandidateWindowSplit(
                            window_name=window_name,
                            window_duration_ms=win_dur_ms,
                            train=None,
                            calibration=None,
                            validation=None,
                            test=test_window,
                            is_eligible=False,
                            ineligibility_reason=f"Insufficient history before cutoff: required {days}d.",
                        )
                    )
                    continue

                actual_history_ms = train_cutoff_ms - timestamps_ms[train_indices[0]]
                # Check if we have at least 85% of requested window history
                if actual_history_ms < (win_dur_ms * 0.85):
                    candidate_splits.append(
                        CandidateWindowSplit(
                            window_name=window_name,
                            window_duration_ms=win_dur_ms,
                            train=None,
                            calibration=None,
                            validation=None,
                            test=test_window,
                            is_eligible=False,
                            ineligibility_reason=f"Only {actual_history_ms / day_ms:.1f}d available before cutoff; required {days}d.",
                        )
                    )
                    continue

                train_start_idx = train_indices[0]
                train_window = SplitWindow(
                    split_type="TRAIN",
                    start_idx=train_start_idx,
                    end_idx=train_end_idx,
                    start_time_ms=timestamps_ms[train_start_idx],
                    end_time_ms=timestamps_ms[train_end_idx],
                    sample_count=len(train_indices),
                )

                candidate_splits.append(
                    CandidateWindowSplit(
                        window_name=window_name,
                        window_duration_ms=win_dur_ms,
                        train=train_window,
                        calibration=calib_window,
                        validation=val_window,
                        test=test_window,
                        is_eligible=True,
                    )
                )

            period = RollingEvaluationPeriod(
                period_id=f"period_{p_idx + 1}",
                test_start_ms=test_window.start_time_ms,
                test_end_ms=test_window.end_time_ms,
                candidate_splits=candidate_splits,
            )
            periods.append(period)

        return periods
