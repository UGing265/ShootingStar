"""Signal lifecycle management, append-only predictions, maturation, and review services.

STRICT INVARIANTS:
1. Predictions are append-only and strictly immutable.
2. Maturation creates a separate SignalOutcome record.
3. Status transitions strictly: PENDING -> EVALUATED or UNSCORABLE.
4. Future data or late arrivals NEVER mutate past prediction records.
"""

import time
import uuid
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import numpy as np

from shootingstar.adapters.db.models import (
    ReviewOverrideModel,
    SignalOutcomeModel,
    SignalPredictionModel,
)
from shootingstar.adapters.db.repository import ReviewOverrideRepository, SignalRepository
from shootingstar.domain.models import Candle


@dataclass(frozen=True)
class SignalCreationRequest:
    prediction_time_ms: int
    experiment_id: str
    symbol: str
    timeframe: str
    horizon_minutes: int
    probability_up: float
    probability_down: float
    probability_no_trade: float
    predicted_class: str
    decision: str
    decision_reason: str


class SignalLifecycleService:
    """Manages creation, maturation, and review of signals."""

    def __init__(
        self,
        signal_repo: SignalRepository,
        review_repo: Optional[ReviewOverrideRepository] = None,
    ):
        self.signal_repo = signal_repo
        self.review_repo = review_repo

    def create_prediction(self, req: SignalCreationRequest) -> SignalPredictionModel:
        """Creates an immutable append-only prediction record."""
        # Validate probability distribution sums to 1.0
        total_p = req.probability_up + req.probability_down + req.probability_no_trade
        if abs(total_p - 1.0) > 1e-4:
            raise ValueError(f"Probabilities must sum to 1.0 (got {total_p})")

        pred = SignalPredictionModel(
            id="sig_" + uuid.uuid4().hex[:16],
            prediction_time_ms=req.prediction_time_ms,
            experiment_id=req.experiment_id,
            symbol=req.symbol,
            timeframe=req.timeframe,
            horizon_minutes=req.horizon_minutes,
            probability_up=req.probability_up,
            probability_down=req.probability_down,
            probability_no_trade=req.probability_no_trade,
            predicted_class=req.predicted_class,
            decision=req.decision,
            decision_reason=req.decision_reason,
        )
        return self.signal_repo.save_prediction(pred)

    def mature_signal(
        self,
        signal: SignalPredictionModel,
        candles_by_open_time: Dict[int, Candle],
        now_ms: int,
    ) -> Optional[SignalOutcomeModel]:
        """Evaluates whether target horizon candle has closed and creates outcome record.
        
        INVARIANT: Does NOT modify `signal`. Creates a separate SignalOutcomeModel.
        """
        # If already matured, return existing outcome
        existing = self.signal_repo.get_outcome_by_signal_id(signal.id)
        if existing:
            return existing

        horizon_ms = signal.horizon_minutes * 60 * 1000
        target_time_ms = signal.prediction_time_ms + horizon_ms

        if not candles_by_open_time:
            return None

        max_available_time = max(candles_by_open_time.keys())
        min_available_time = min(candles_by_open_time.keys())

        c_t = candles_by_open_time.get(signal.prediction_time_ms)
        if not c_t:
            if min_available_time <= signal.prediction_time_ms <= max_available_time:
                # Entry candle is missing inside the covered window: confirmed gap
                outcome = SignalOutcomeModel(
                    signal_id=signal.id,
                    status="UNSCORABLE",
                    evaluated_at_ms=now_ms,
                    unscorable_reason="Entry candle at prediction time is missing (gap detected in covered history)",
                )
                return self.signal_repo.save_outcome(outcome)
            else:
                # Window does not cover prediction time yet/anymore
                return None

        c_target = candles_by_open_time.get(target_time_ms)
        if not c_target:
            if max_available_time < target_time_ms:
                # Stream has not ingested up to target_time_ms yet: still legitimately PENDING
                return None
            else:
                # Covered stream extends beyond target_time_ms but target candle is absent: permanent gap
                outcome = SignalOutcomeModel(
                    signal_id=signal.id,
                    status="UNSCORABLE",
                    evaluated_at_ms=now_ms,
                    unscorable_reason="Target candle is missing (gap detected in history beyond target time)",
                )
                return self.signal_repo.save_outcome(outcome)
        # Target candle is available and closed!
        entry_price = c_t.close
        target_price = c_target.close
        ret = (target_price - entry_price) / entry_price

        if ret > 0:
            realized_lbl = "UP"
        elif ret < 0:
            realized_lbl = "DOWN"
        else:
            realized_lbl = "FLAT"

        is_match = (signal.predicted_class == realized_lbl)

        outcome = SignalOutcomeModel(
            signal_id=signal.id,
            status="EVALUATED",
            evaluated_at_ms=now_ms,
            realized_return=float(ret),
            realized_label=realized_lbl,
            is_match=is_match,
        )
        return self.signal_repo.save_outcome(outcome)

    def record_review_override(
        self,
        signal_id: str,
        reviewer_id: str,
        override_decision: str,
        notes: str,
    ) -> Optional[ReviewOverrideModel]:
        """Records human or rule-based review override without altering prediction."""
        if self.review_repo is None:
            raise RuntimeError("ReviewOverrideRepository is not configured.")

        # Ensure signal exists
        sig = self.signal_repo.get_prediction_by_id(signal_id)
        if not sig:
            return None

        override = ReviewOverrideModel(
            signal_id=signal_id,
            reviewer_id=reviewer_id,
            override_decision=override_decision,
            notes=notes,
        )
        return self.review_repo.save(override)
