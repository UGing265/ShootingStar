"""Unit and boundary tests for Phase 03: Causal Replay Engine with Zero-Lookahead Guarantees."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch
import numpy as np
import pytest
from fastapi.testclient import TestClient

from shootingstar.adapters.storage import SnapshotStorage
from shootingstar.application.replay import ReplaySessionManager
from shootingstar.domain.exceptions import DomainError
from shootingstar.domain.models import Candle
from shootingstar.api.app import app


@pytest.fixture
def sample_snapshot_and_models():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        storage = SnapshotStorage(snapshots_dir=tmp_path / "snapshots")
        models_dir = tmp_path / "models"
        models_dir.mkdir(parents=True, exist_ok=True)

        # 100 5-minute candles
        candles = []
        base_time = 1704067200000  # 2024-01-01 00:00:00
        price = 42000.0
        for i in range(200):
            open_t = base_time + (i * 300000)
            close_t = open_t + 299999
            ret = 0.001 if i % 2 == 0 else -0.001
            c_open = price
            c_close = price * (1.0 + ret)
            c_high = max(c_open, c_close) * 1.0005
            c_low = min(c_open, c_close) * 0.9995
            candles.append(
                Candle(
                    venue="BINANCE",
                    symbol="BTCUSDT",
                    timeframe="5m",
                    open_time_ms=open_t,
                    close_time_ms=close_t,
                    open=c_open,
                    high=c_high,
                    low=c_low,
                    close=c_close,
                    volume=10.0,
                    quote_volume=10.0 * c_close,
                    trades_count=50,
                    taker_buy_base_volume=5.0,
                    taker_buy_quote_volume=5.0 * c_close,
                )
            )
            price = c_close

        snap_path, snap_sha = storage.save_snapshot(candles, venue="BINANCE", symbol="BTCUSDT", timeframe="5m")

        yield {
            "tmp_path": tmp_path,
            "storage": storage,
            "models_dir": models_dir,
            "candles": candles,
            "snap_path": snap_path,
            "snap_sha": snap_sha,
            "base_time": base_time,
        }


def test_zero_lookahead_and_forward_stepping(sample_snapshot_and_models):
    ctx = sample_snapshot_and_models
    manager = ReplaySessionManager(snapshot_storage=ctx["storage"], models_dir=ctx["models_dir"])

    # t0 at candle index 30
    c30 = ctx["candles"][30]
    t0 = c30.close_time_ms

    session = manager.create_session(snapshot_path=ctx["snap_path"], start_time_ms=t0)
    view = manager.get_view(session.session_id)

    # STRICT INVARIANT: Visible candles count must equal exactly 31 (indices 0..30)
    assert view.visible_candles_count == 31
    assert view.current_time_ms == t0
    # The newest visible candle must be exactly candle 30
    assert view.recent_candles[-1].close_time_ms == t0

    # ZERO LOOKAHEAD: No candle past t0 is visible
    for c in view.recent_candles:
        assert c.close_time_ms <= t0

    # Step forward by 5 candles
    view_step = manager.step(session.session_id, steps=5)
    c35 = ctx["candles"][35]
    assert view_step.current_time_ms == c35.close_time_ms
    assert view_step.visible_candles_count == 36
    assert view_step.recent_candles[-1].close_time_ms == c35.close_time_ms


def test_model_cutoff_equality_boundary_and_winner_rejection(sample_snapshot_and_models):
    ctx = sample_snapshot_and_models
    manager = ReplaySessionManager(snapshot_storage=ctx["storage"], models_dir=ctx["models_dir"])

    c40 = ctx["candles"][40]
    t0 = c40.close_time_ms

    # 1. Test equality boundary: train_end_ms == t0 must be REJECTED (train_end_ms must be strictly < t0)
    leak_sha = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    manifest_equal = {
        "artifact_hash": leak_sha,
        "train_end_ms": t0,  # Exact equality boundary!
        "is_selected_winner": True,
    }
    (ctx["models_dir"] / f"{leak_sha}.manifest.json").write_text(json.dumps(manifest_equal), encoding="utf-8")

    with pytest.raises(DomainError) as exc_equal:
        manager.create_session(snapshot_path=ctx["snap_path"], start_time_ms=t0, model_artifact_hash=leak_sha)
    assert "leaks into or overlaps replay start time" in str(exc_equal.value)

    # 2. Test future cutoff: train_end_ms > t0 must be REJECTED
    future_sha = "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789"
    manifest_future = {
        "artifact_hash": future_sha,
        "train_end_ms": t0 + 60000,
        "is_selected_winner": True,
    }
    (ctx["models_dir"] / f"{future_sha}.manifest.json").write_text(json.dumps(manifest_future), encoding="utf-8")

    with pytest.raises(DomainError) as exc_future:
        manager.create_session(snapshot_path=ctx["snap_path"], start_time_ms=t0, model_artifact_hash=future_sha)
    assert "leaks into or overlaps replay start time" in str(exc_future.value)

    # 3. Test non-winner rejection: is_selected_winner is False must be REJECTED
    non_winner_sha = "1111111111222222222233333333334444444444555555555566666666667777"
    manifest_non_winner = {
        "artifact_hash": non_winner_sha,
        "train_end_ms": t0 - 300000,
        "is_selected_winner": False,  # Not a winner!
    }
    (ctx["models_dir"] / f"{non_winner_sha}.manifest.json").write_text(json.dumps(manifest_non_winner), encoding="utf-8")

    with pytest.raises(DomainError) as exc_winner:
        manager.create_session(snapshot_path=ctx["snap_path"], start_time_ms=t0, model_artifact_hash=non_winner_sha)
    assert "was not selected as validation winner" in str(exc_winner.value)


def test_replay_prediction_maturation_horizon(sample_snapshot_and_models):
    ctx = sample_snapshot_and_models
    manager = ReplaySessionManager(snapshot_storage=ctx["storage"], models_dir=ctx["models_dir"])

    c35 = ctx["candles"][35]
    t0 = c35.close_time_ms

    session = manager.create_session(snapshot_path=ctx["snap_path"], start_time_ms=t0)

    # Add a mock pending prediction at candle 35 (horizon is 30m = 6 5m candles later -> candle 41)
    from shootingstar.application.replay import ReplayPrediction
    pred = ReplayPrediction(
        prediction_id="test_p1",
        candle_time_ms=c35.close_time_ms,
        horizon_time_ms=c35.close_time_ms + (30 * 60 * 1000),
        probability_up=0.65,
        probability_down=0.35,
        predicted_direction="UP",
        status="PENDING",
    )
    session.predictions.append(pred)

    # Step forward 3 candles (15m): horizon not yet reached -> stays PENDING
    manager.step(session.session_id, steps=3)
    assert session.predictions[0].status == "PENDING"

    # Step forward 3 more candles (total 30m reached): prediction MATURES to EVALUATED!
    manager.step(session.session_id, steps=3)
    p_mature = session.predictions[0]
    assert p_mature.status == "EVALUATED"
    assert p_mature.realized_label in ("UP", "DOWN")
    assert p_mature.realized_return is not None


def test_replay_api_routes_end_to_end(sample_snapshot_and_models):
    ctx = sample_snapshot_and_models
    client = TestClient(app)

    # Mock DB snapshot lookup
    with patch("shootingstar.adapters.db.repository.SnapshotRepository.get_by_id") as mock_get_by_id:
        from unittest.mock import MagicMock
        mock_snap = MagicMock()
        mock_snap.id = ctx["snap_sha"]
        mock_snap.file_path = str(ctx["snap_path"])
        mock_get_by_id.return_value = mock_snap

        c20 = ctx["candles"][20]
        buy_t = c20.close_time_ms

        # 1. Create simulation job via POST /replay/jobs
        res_create = client.post("/replay/jobs", json={
            "snapshot_id": ctx["snap_sha"],
            "buy_time_ms": buy_t,
            "buy_price": c20.close,
            "horizon_minutes": 30,
        })
        assert res_create.status_code == 201
        data = res_create.json()
        job_id = data["job_id"]
        assert data["status"] == "AI_PREDICTED"
        assert data["ai_prediction"]["predicted_direction"] == "NO_MODEL"
        assert data["outcome"] is None

        # 2. Get job view via GET /replay/jobs/{id}
        res_get = client.get(f"/replay/jobs/{job_id}")
        assert res_get.status_code == 200
        assert res_get.json()["job_id"] == job_id
        assert res_get.json()["outcome"] is None

        # 3. Vote via POST /replay/jobs/{id}/vote
        res_vote = client.post(f"/replay/jobs/{job_id}/vote", json={"user_direction": "UP"})
        assert res_vote.status_code == 200
        assert res_vote.json()["status"] == "VOTED"
        assert res_vote.json()["user_vote"]["user_direction"] == "UP"

        # 4. Reveal outcome via POST /replay/jobs/{id}/reveal
        res_reveal = client.post(f"/replay/jobs/{job_id}/reveal")
        assert res_reveal.status_code == 200
        assert res_reveal.json()["status"] == "REVEALED"
        assert res_reveal.json()["outcome"]["status"] == "EVALUATED"

def test_tampered_artifact_checksum_rejection(sample_snapshot_and_models):
    ctx = sample_snapshot_and_models
    manager = ReplaySessionManager(snapshot_storage=ctx["storage"], models_dir=ctx["models_dir"])
    c40 = ctx["candles"][40]
    t0 = c40.close_time_ms

    tampered_sha = "9999999999999999999999999999999999999999999999999999999999999999"
    manifest = {
        "artifact_hash": tampered_sha,
        "train_end_ms": t0 - 60000,
        "is_selected_winner": True,
    }
    (ctx["models_dir"] / f"{tampered_sha}.manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    # Create artifact file with different content
    fake_file = ctx["models_dir"] / f"model_{tampered_sha[:10]}.joblib"
    fake_file.write_bytes(b"tampered content")

    with pytest.raises(DomainError) as exc_tamper:
        manager.create_session(snapshot_path=ctx["snap_path"], start_time_ms=t0, model_artifact_hash=tampered_sha)
    assert "Model artifact SHA-256 mismatch" in str(exc_tamper.value)


def test_feature_availability_latency_filtering_with_model(sample_snapshot_and_models):
    ctx = sample_snapshot_and_models
    from shootingstar.application.training.modeling import CalibratedLogisticRegressionModel
    from shootingstar.application.features import FeatureExtractionService

    c95 = ctx["candles"][95]
    t_cutoff = c95.close_time_ms

    # Train a minimal model on initial 95 candles (needs >=65 candles for WARMUP_PERIODS)
    feat_service = FeatureExtractionService(assumed_latency_ms=1)
    train_candles = ctx["candles"][:95]
    feat_mat = feat_service.extract_matrix(train_candles)
    X_train = feat_mat.values
    assert len(X_train) >= 15
    half = len(X_train) // 2
    y_train = np.array([1 if i % 2 == 0 else 0 for i in range(len(X_train))])

    model = CalibratedLogisticRegressionModel()
    model.fit_and_calibrate(X_train[:half], y_train[:half], X_train[half:], y_train[half:])
    art_path, art_sha = model.save_artifact(ctx["models_dir"], "test_winner_model")

    # Create valid winner manifest with cutoff t_cutoff
    manifest = {
        "artifact_hash": art_sha,
        "train_end_ms": t_cutoff,
        "is_selected_winner": True,
    }
    (ctx["models_dir"] / f"{art_sha}.manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    # Replay session starts at candle 120 (> t_cutoff)
    c120 = ctx["candles"][120]
    t0 = c120.close_time_ms
    # 1. Normal latency: features available -> prediction generated
    mgr_normal = ReplaySessionManager(snapshot_storage=ctx["storage"], models_dir=ctx["models_dir"], assumed_latency_ms=1)
    session_normal = mgr_normal.create_session(snapshot_path=ctx["snap_path"], start_time_ms=t0, model_artifact_hash=art_sha)
    view_normal = mgr_normal.get_view(session_normal.session_id)
    assert len(view_normal.predictions) >= 1
    assert view_normal.predictions[0].status == "PENDING"

    # 2. Extreme latency: features NOT yet available (available_at > current_time_ms) -> zero predictions emitted
    mgr_lag = ReplaySessionManager(snapshot_storage=ctx["storage"], models_dir=ctx["models_dir"], assumed_latency_ms=999999999)
    session_lag = mgr_lag.create_session(snapshot_path=ctx["snap_path"], start_time_ms=t0, model_artifact_hash=art_sha)
    # Because all features are timestamped in the far future, no predictions can leak
    assert len(session_lag.predictions) == 0


def test_simulation_job_creation_and_no_model(sample_snapshot_and_models):
    from shootingstar.application.replay import SimulationJobManager

    ctx = sample_snapshot_and_models
    sim_dir = ctx["tmp_path"] / "simulations"
    mgr = SimulationJobManager(snapshot_storage=ctx["storage"], models_dir=ctx["models_dir"], simulations_dir=sim_dir)

    c50 = ctx["candles"][50]
    buy_time = c50.close_time_ms
    buy_price = 45000.0  # hypothetical buy price

    job = mgr.create_job(
        snapshot_path=ctx["snap_path"],
        snapshot_id=ctx["snap_sha"],
        buy_time_ms=buy_time,
        buy_price=buy_price,
        horizon_minutes=30,
        model_artifact_hash=None,
    )

    assert job.status == "AI_PREDICTED"
    assert job.buy_price == 45000.0
    assert job.candle_close_at_buy == c50.close
    assert job.ai_prediction is not None
    assert job.ai_prediction.predicted_direction == "NO_MODEL"
    assert job.user_vote is None
    assert job.outcome is None  # Outcome strictly hidden!


def test_simulation_job_model_cutoff_and_horizon_validation(sample_snapshot_and_models):
    from shootingstar.application.features import FeatureExtractionService
    from shootingstar.application.training.modeling import CalibratedLogisticRegressionModel
    from shootingstar.application.replay import SimulationJobManager

    ctx = sample_snapshot_and_models
    sim_dir = ctx["tmp_path"] / "simulations"
    mgr = SimulationJobManager(snapshot_storage=ctx["storage"], models_dir=ctx["models_dir"], simulations_dir=sim_dir)

    # Train a minimal model
    feat_service = FeatureExtractionService(assumed_latency_ms=1)
    train_candles = ctx["candles"][:90]
    feat_mat = feat_service.extract_matrix(train_candles)
    X_train = feat_mat.values
    half = len(X_train) // 2
    y_train = np.array([1 if i % 2 == 0 else 0 for i in range(len(X_train))])

    model = CalibratedLogisticRegressionModel()
    model.fit_and_calibrate(X_train[:half], y_train[:half], X_train[half:], y_train[half:])
    art_path, art_sha = model.save_artifact(ctx["models_dir"], "test_winner_sim")

    cutoff_ms = ctx["candles"][90].close_time_ms
    manifest = {
        "artifact_hash": art_sha,
        "train_end_ms": cutoff_ms,
        "is_selected_winner": True,
        "horizon_minutes": 30,
        "metrics": {"accuracy": 0.58, "brier_score": 0.24},
    }
    (ctx["models_dir"] / f"{art_sha}.manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    # 1. Leaking cutoff: buy_time <= cutoff_ms -> rejected by AI
    c80 = ctx["candles"][80]
    job_leak = mgr.create_job(
        snapshot_path=ctx["snap_path"],
        snapshot_id=ctx["snap_sha"],
        buy_time_ms=c80.close_time_ms,
        buy_price=c80.close,
        horizon_minutes=30,
        model_artifact_hash=art_sha,
    )
    assert job_leak.ai_prediction.predicted_direction == "NO_MODEL"
    assert "vi phạm zero-lookahead" in job_leak.ai_prediction.evidence_summary

    # 2. Horizon mismatch: request 60m but model trained on 30m -> rejected
    c110 = ctx["candles"][110]
    job_mismatch = mgr.create_job(
        snapshot_path=ctx["snap_path"],
        snapshot_id=ctx["snap_sha"],
        buy_time_ms=c110.close_time_ms,
        buy_price=c110.close,
        horizon_minutes=60,
        model_artifact_hash=art_sha,
    )
    assert job_mismatch.ai_prediction.predicted_direction == "NO_MODEL"
    assert "không khớp" in job_mismatch.ai_prediction.evidence_summary

    # 3. Model passes cutoff and horizon -> still returns NO_MODEL because point-price OOS pipeline is not yet validated
    job_valid = mgr.create_job(
        snapshot_path=ctx["snap_path"],
        snapshot_id=ctx["snap_sha"],
        buy_time_ms=c110.close_time_ms,
        buy_price=c110.close,
        horizon_minutes=30,
        model_artifact_hash=art_sha,
    )
    assert job_valid.ai_prediction.predicted_direction == "NO_MODEL"
    assert "chưa có mô hình được huấn luyện theo mục tiêu giá tương lai so với giá mua giả định" in job_valid.ai_prediction.evidence_summary
    assert job_valid.ai_prediction.is_calibrated is False
    assert job_valid.ai_prediction.probability_up is None
    assert job_valid.ai_prediction.probability_down is None

def test_simulation_job_user_vote_and_reveal_flow(sample_snapshot_and_models):
    from shootingstar.application.replay import SimulationJobManager
    from shootingstar.domain.exceptions import DomainError

    ctx = sample_snapshot_and_models
    sim_dir = ctx["tmp_path"] / "simulations"
    mgr = SimulationJobManager(snapshot_storage=ctx["storage"], models_dir=ctx["models_dir"], simulations_dir=sim_dir)

    c50 = ctx["candles"][50]
    buy_time = c50.close_time_ms
    buy_price = 40000.0  # Assumed buy price

    job = mgr.create_job(
        snapshot_path=ctx["snap_path"],
        snapshot_id=ctx["snap_sha"],
        buy_time_ms=buy_time,
        buy_price=buy_price,
        horizon_minutes=30,
    )

    # Attempting to reveal before voting -> DomainError
    with pytest.raises(DomainError, match="Phải khóa dự đoán"):
        mgr.reveal_outcome(job.job_id, ctx["snap_path"])

    # Record user vote
    voted_job = mgr.record_vote(job.job_id, "UP")
    assert voted_job.status == "VOTED"
    assert voted_job.user_vote.user_direction == "UP"
    assert voted_job.user_vote.is_locked is True

    # Double vote -> DomainError
    with pytest.raises(DomainError, match="đã được khóa"):
        mgr.record_vote(job.job_id, "DOWN")

    # Reveal outcome
    revealed_job = mgr.reveal_outcome(job.job_id, ctx["snap_path"])
    assert revealed_job.status == "REVEALED"
    assert revealed_job.outcome is not None
    assert revealed_job.outcome.status == "EVALUATED"
    assert revealed_job.outcome.future_price is not None
    assert revealed_job.outcome.market_direction in ("UP", "DOWN", "FLAT")
    assert isinstance(revealed_job.outcome.user_is_correct, bool)


def test_simulation_job_persistence_across_restarts(sample_snapshot_and_models):
    from shootingstar.application.replay import SimulationJobManager

    ctx = sample_snapshot_and_models
    sim_dir = ctx["tmp_path"] / "simulations"

    # Instance 1: create job and vote
    mgr1 = SimulationJobManager(snapshot_storage=ctx["storage"], models_dir=ctx["models_dir"], simulations_dir=sim_dir)
    c30 = ctx["candles"][30]
    job = mgr1.create_job(
        snapshot_path=ctx["snap_path"],
        snapshot_id=ctx["snap_sha"],
        buy_time_ms=c30.close_time_ms,
        buy_price=c30.close,
        horizon_minutes=30,
    )
    mgr1.record_vote(job.job_id, "DOWN")

    # Instance 2 (simulate server restart): points to same simulations_dir
    mgr2 = SimulationJobManager(snapshot_storage=ctx["storage"], models_dir=ctx["models_dir"], simulations_dir=sim_dir)
    reloaded_job = mgr2.get_job(job.job_id)
    assert reloaded_job.status == "VOTED"
    assert reloaded_job.user_vote.user_direction == "DOWN"

    # Reveal outcome on Instance 2
    revealed = mgr2.reveal_outcome(job.job_id, ctx["snap_path"])
    assert revealed.status == "REVEALED"
    assert revealed.outcome.status == "EVALUATED"
