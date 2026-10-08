"""Integration tests for Signal lifecycle, maturation transitions, immutability, and reviews."""

import pytest
import uuid
from shootingstar.adapters.db.models import ExperimentModel, SnapshotModel
from shootingstar.adapters.db.repository import (
    ExperimentRepository,
    ReviewOverrideRepository,
    SignalRepository,
    SnapshotRepository,
)
from shootingstar.application.signals import SignalCreationRequest, SignalLifecycleService
from shootingstar.domain.models import Candle


def _ensure_experiment(db_session, exp_id: str):
    exp_repo = ExperimentRepository(db_session)
    if not exp_repo.get_by_id(exp_id):
        snap_repo = SnapshotRepository(db_session)
        snap_id = "snap_" + uuid.uuid4().hex
        snap = SnapshotModel(
            id=snap_id,
            venue="BINANCE",
            symbol="BTCUSDT",
            timeframe="5m",
            start_time_ms=1000000,
            end_time_ms=5000000,
            candle_count=100,
            file_path="data/snapshots/dummy.parquet",
            sha256=snap_id,
        )
        snap_repo.save(snap)
        exp = ExperimentModel(
            id=exp_id,
            name=exp_id,
            config_hash=uuid.uuid4().hex,
            snapshot_id=snap_id,
            parameters_json="{}",
        )
        exp_repo.save(exp)
def test_signal_creation_validation_and_persistence(db_session):
    sig_repo = SignalRepository(db_session)
    _ensure_experiment(db_session, "exp_test")
    service = SignalLifecycleService(sig_repo)

    req = SignalCreationRequest(
        prediction_time_ms=1000000,
        experiment_id="exp_test",
        symbol="BTCUSDT",
        timeframe="5m",
        horizon_minutes=30,
        probability_up=0.6,
        probability_down=0.4,
        probability_no_trade=0.0,
        predicted_class="UP",
        decision="UP",
        decision_reason="Calibrated probability > 0.55",
    )

    pred = service.create_prediction(req)
    assert pred.id.startswith("sig_")
    assert pred.predicted_class == "UP"

    # Probabilities not summing to 1.0 must be rejected
    invalid_req = SignalCreationRequest(
        prediction_time_ms=1000000,
        experiment_id="exp_test",
        symbol="BTCUSDT",
        timeframe="5m",
        horizon_minutes=30,
        probability_up=0.8,
        probability_down=0.4,
        probability_no_trade=0.0,
        predicted_class="UP",
        decision="UP",
        decision_reason="Invalid",
    )
    with pytest.raises(ValueError, match="must sum to 1.0"):
        service.create_prediction(invalid_req)


def test_signal_maturation_lifecycle_and_immutability(db_session):
    _ensure_experiment(db_session, "exp_test_maturation")
    sig_repo = SignalRepository(db_session)
    review_repo = ReviewOverrideRepository(db_session)
    service = SignalLifecycleService(sig_repo, review_repo)

    t0 = 1000000
    horizon_ms = 30 * 60 * 1000  # 1800000 ms -> t_target = 2800000

    # 1. Create prediction at t0
    req = SignalCreationRequest(
        prediction_time_ms=t0,
        experiment_id="exp_test_maturation",
        symbol="BTCUSDT",
        timeframe="5m",
        horizon_minutes=30,
        probability_up=0.65,
        probability_down=0.35,
        probability_no_trade=0.0,
        predicted_class="UP",
        decision="UP",
        decision_reason="P(UP) > 0.55",
    )
    pred = service.create_prediction(req)

    c0 = Candle("BINANCE", "BTCUSDT", "5m", t0, t0 + 299999, 50000.0, 50100.0, 49900.0, 50000.0, 1.0, 50000.0, 1, 0.5, 25000.0)
    candles = {t0: c0}

    # 2. Before target time has arrived (now_ms < t_target): remains PENDING (returns None)
    outcome_pending = service.mature_signal(pred, candles, now_ms=t0 + 600000)
    assert outcome_pending is None
    assert sig_repo.get_outcome_by_signal_id(pred.id) is None

    # 3. Target time arrived but candle missing: matures to UNSCORABLE
    outcome_unscorable = service.mature_signal(pred, candles, now_ms=t0 + horizon_ms + 1000)
    assert outcome_unscorable is not None
    assert outcome_unscorable.status == "UNSCORABLE"
    # Invariant: original prediction row is strictly unchanged
    pred_refetched = sig_repo.get_prediction_by_id(pred.id)
    assert pred_refetched.predicted_class == "UP"
    assert pred_refetched.probability_up == 0.65


def test_signal_evaluated_outcome_and_review_override(db_session):
    _ensure_experiment(db_session, "exp_test_eval")
    sig_repo = SignalRepository(db_session)
    review_repo = ReviewOverrideRepository(db_session)
    service = SignalLifecycleService(sig_repo, review_repo)

    t0 = 2000000
    horizon_ms = 30 * 60 * 1000  # 1800000 -> target = 3800000

    req = SignalCreationRequest(
        prediction_time_ms=t0,
        experiment_id="exp_test_eval",
        symbol="BTCUSDT",
        timeframe="5m",
        horizon_minutes=30,
        probability_up=0.70,
        probability_down=0.30,
        probability_no_trade=0.0,
        predicted_class="UP",
        decision="UP",
        decision_reason="P(UP) > 0.55",
    )
    pred = service.create_prediction(req)

    c0 = Candle("BINANCE", "BTCUSDT", "5m", t0, t0 + 299999, 50000.0, 50100.0, 49900.0, 50000.0, 1.0, 50000.0, 1, 0.5, 25000.0)
    c_target = Candle("BINANCE", "BTCUSDT", "5m", t0 + horizon_ms, t0 + horizon_ms + 299999, 50500.0, 50600.0, 50400.0, 50500.0, 1.0, 50500.0, 1, 0.5, 25000.0)
    candles = {t0: c0, (t0 + horizon_ms): c_target}

    # Mature signal
    outcome = service.mature_signal(pred, candles, now_ms=t0 + horizon_ms + 60000)
    assert outcome is not None
    assert outcome.status == "EVALUATED"
    assert outcome.realized_label == "UP"
    assert outcome.is_match is True
    assert outcome.realized_return == pytest.approx(0.01)  # 50500 / 50000 - 1 = +0.01

    # Check Review Override
    override = service.record_review_override(
        signal_id=pred.id,
        reviewer_id="human_analyst_1",
        override_decision="NO_TRADE",
        notes="High volatility news regime detected, overriding algorithmic UP",
    )
    assert override is not None
    assert override.signal_id == pred.id
    assert override.override_decision == "NO_TRADE"

    # Prediction remains unchanged
    pred_after = sig_repo.get_prediction_by_id(pred.id)
    assert pred_after.predicted_class == "UP"
    assert pred_after.decision == "UP"
