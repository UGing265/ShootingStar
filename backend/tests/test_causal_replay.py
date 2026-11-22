"""Unit and boundary tests for replay simulation jobs with zero-lookahead guarantees."""

import tempfile
from pathlib import Path
import pytest

from shootingstar.adapters.storage import SnapshotStorage
from shootingstar.domain.exceptions import DomainError
from shootingstar.domain.models import Candle


@pytest.fixture
def sample_snapshot_and_models():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        storage = SnapshotStorage(snapshots_dir=tmp_path / "snapshots")

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
            "candles": candles,
            "snap_path": snap_path,
            "snap_sha": snap_sha,
            "base_time": base_time,
        }


def test_simulation_job_creation_and_no_model(sample_snapshot_and_models):
    from shootingstar.application.replay import SimulationJobManager

    ctx = sample_snapshot_and_models
    sim_dir = ctx["tmp_path"] / "simulations"
    mgr = SimulationJobManager(snapshot_storage=ctx["storage"], simulations_dir=sim_dir)

    c50 = ctx["candles"][50]
    buy_time = c50.close_time_ms
    buy_price = 45000.0  # hypothetical buy price

    job = mgr.create_job(
        snapshot_path=ctx["snap_path"],
        snapshot_id=ctx["snap_sha"],
        buy_time_ms=buy_time,
        buy_price=buy_price,
        horizon_minutes=30,
    )

    assert job.status == "AI_PREDICTED"
    assert job.buy_price == 45000.0
    assert job.candle_close_at_buy == c50.close
    assert job.ai_prediction is not None
    assert job.ai_prediction.predicted_direction == "NO_MODEL"
    assert job.user_vote is None
    assert job.outcome is None  # Outcome strictly hidden!


def test_simulation_job_user_vote_and_reveal_flow(sample_snapshot_and_models):
    from shootingstar.application.replay import SimulationJobManager
    from shootingstar.domain.exceptions import DomainError

    ctx = sample_snapshot_and_models
    sim_dir = ctx["tmp_path"] / "simulations"
    mgr = SimulationJobManager(snapshot_storage=ctx["storage"], simulations_dir=sim_dir)

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
    mgr1 = SimulationJobManager(snapshot_storage=ctx["storage"], simulations_dir=sim_dir)
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
    mgr2 = SimulationJobManager(snapshot_storage=ctx["storage"], simulations_dir=sim_dir)
    reloaded_job = mgr2.get_job(job.job_id)
    assert reloaded_job.status == "VOTED"
    assert reloaded_job.user_vote.user_direction == "DOWN"

    # Reveal outcome on Instance 2
    revealed = mgr2.reveal_outcome(job.job_id, ctx["snap_path"])
    assert revealed.status == "REVEALED"
    assert revealed.outcome.status == "EVALUATED"

def test_simulation_job_strategy_evaluation_and_barrier_outcome(sample_snapshot_and_models):
    from shootingstar.application.replay import SimulationJobManager
    from shootingstar.api.replay_routes import _to_job_response

    ctx = sample_snapshot_and_models
    sim_dir = ctx["tmp_path"] / "simulations"
    mgr = SimulationJobManager(snapshot_storage=ctx["storage"], simulations_dir=sim_dir)

    c80 = ctx["candles"][80]
    job = mgr.create_job(
        snapshot_path=ctx["snap_path"],
        snapshot_id=ctx["snap_sha"],
        buy_time_ms=c80.close_time_ms,
        buy_price=c80.close,
        horizon_minutes=30,
    )

    # Step 1: Strategy evaluation exists and is decoupled from AI prediction
    assert job.strategy_evaluation is not None
    assert "strategy_version" in job.strategy_evaluation
    assert "candidate_state" in job.strategy_evaluation
    assert "is_trade_eligible" in job.strategy_evaluation

    # Step 2 & 3: User votes independently with UP / DOWN
    voted_job = mgr.record_vote(job.job_id, "UP")
    assert voted_job.user_vote.user_direction == "UP"

    # Step 4: Reveal outcome computes both market direction AND barrier strategy outcome
    revealed_job = mgr.reveal_outcome(job.job_id, ctx["snap_path"])
    assert revealed_job.status == "REVEALED"
    assert revealed_job.outcome is not None
    assert revealed_job.outcome.market_direction in ("UP", "DOWN", "FLAT")
    assert revealed_job.outcome.user_is_correct == (revealed_job.outcome.market_direction == "UP")

    # Strategy outcome is populated
    assert revealed_job.strategy_outcome is not None
    assert "trade_executed" in revealed_job.strategy_outcome
    assert "outcome" in revealed_job.strategy_outcome

    # API Response DTO reflects both
    resp = _to_job_response(revealed_job)
    assert resp.strategy_evaluation is not None
    assert resp.strategy_outcome is not None
    assert resp.user_vote.user_direction == "UP"


def test_replay_false_fill_on_straddling_candle_rejected(sample_snapshot_and_models):
    from shootingstar.application.replay import SimulationJobManager

    ctx = sample_snapshot_and_models
    sim_dir = ctx["tmp_path"] / "simulations"
    mgr = SimulationJobManager(snapshot_storage=ctx["storage"], simulations_dir=sim_dir)

    c50 = ctx["candles"][50]
    job = mgr.create_job(
        snapshot_path=ctx["snap_path"],
        snapshot_id=ctx["snap_sha"],
        buy_time_ms=c50.close_time_ms,
        buy_price=c50.close,
        horizon_minutes=30,
    )

    # Inject a strategy evaluation with proposed_entry set to an extreme price not reached by in-horizon candles
    # but reached by modifying only a straddling candle
    job.strategy_evaluation = {
        "strategy_version": "30m-fast-entry-v1",
        "candidate_state": "CONFIRMED",
        "is_trade_eligible": True,
        "proposed_entry": 999999.0,
        "target_price": 1005000.0,
        "stop_price": 994000.0,
    }
    mgr._persist_job(job)

    mgr.record_vote(job.job_id, "UP")
    revealed_job = mgr.reveal_outcome(job.job_id, ctx["snap_path"])

    # Must be UNFILLED because 999999 was never touched within completed in-horizon candles
    assert revealed_job.strategy_outcome is not None
    assert revealed_job.strategy_outcome["trade_executed"] is False
    assert revealed_job.strategy_outcome["outcome"] == "UNFILLED"


def test_candidate_plan_reward_risk_ratio_regression():
    from decimal import Decimal
    from shootingstar.domain.trade_plan import (
        CandidatePlan,
        CandidateState,
        ConfirmationRule,
        EntryZone,
        InvalidationRule,
        RiskConfig,
        SymbolFilters,
    )

    plan = CandidatePlan(
        candidate_id="cand_test_01",
        strategy_version="v1-support-reclaim-30m",
        rule_config_hash="cfg_hash",
        decision_time_ms=1000,
        available_cutoff_ms=1000,
        entry_zone=EntryZone(
            min_price=Decimal("100.00"),
            max_price=Decimal("101.00"),
            proposed_entry=Decimal("100.00"),
        ),
        confirmation=ConfirmationRule(
            support_level=Decimal("98.00"),
            reclaim_level=Decimal("99.00"),
        ),
        invalidation=InvalidationRule(
            invalidation_price=Decimal("95.00"),
            buffer_percent=Decimal("0.002"),
        ),
        stop_price=Decimal("96.00"),
        target_price=Decimal("108.00"),
        risk_config=RiskConfig(
            max_notional_usdt=Decimal("1000.00"),
            max_planned_loss_usdt=Decimal("50.00"),
            fee_rate_bps=Decimal("10.0"),
            slippage_bps=Decimal("5.0"),
            max_wait_duration_ms=1_800_000,
            max_entry_deviation_pct=Decimal("0.002"),
            freshness_tolerance_ms=120_000,
            max_event_lag_ms=5_000,
            cost_model_source="vip0-evidence-v1",
        ),
        symbol_filters=SymbolFilters(
            symbol="BTCUSDT",
            tick_size=Decimal("0.01"),
            step_size=Decimal("0.00001"),
            min_notional=Decimal("5.0"),
            min_qty=Decimal("0.00001"),
        ),
        wait_expires_at_ms=2000,
    )

    # Target = 108, Entry = 100 -> Reward = 8
    # Entry = 100, Stop = 96 -> Risk = 4
    # R:R = 8 / 4 = 2.0
    assert hasattr(plan, "reward_risk_ratio")
    assert plan.reward_risk_ratio == Decimal("2.0")
    assert float(plan.reward_risk_ratio) == 2.0


def test_evaluate_strategy_candidate_with_valid_setup_serializes_reward_risk_ratio():
    from datetime import datetime, timezone
    from shootingstar.application.replay import SimulationJobManager
    from shootingstar.domain.models import Candle

    mgr = SimulationJobManager()

    base_t = 1_700_000_000_000
    interval_ms = 60_000
    candles = []
    for i in range(65):
        low = 89500.0 if i == 10 else 89800.0
        high = 92500.0 if i == 5 else 90500.0
        open_t = base_t + i * interval_ms
        close_t = open_t + interval_ms
        candles.append(
            Candle(
                venue="BINANCE",
                symbol="BTCUSDT",
                timeframe="1m",
                open_time_ms=open_t,
                close_time_ms=close_t,
                open=90000.0,
                high=high,
                low=low,
                close=90200.0,
                volume=100.0,
                quote_volume=9000000.0,
                trades_count=100,
                taker_buy_base_volume=50.0,
                taker_buy_quote_volume=4500000.0,
                observed_ingested_at_ms=close_t + 500,
            )
        )

    buy_t = candles[-1].close_time_ms
    eval_result = mgr._evaluate_strategy_candidate(
        visible_candles=candles,
        buy_time_ms=buy_t,
        horizon_minutes=30,
    )

    assert eval_result["has_setup"] is True
    assert eval_result["proposed_entry"] == 90200.0
    assert eval_result["target_price"] == 92500.0
    assert eval_result["reward_risk_ratio"] is not None
    assert isinstance(eval_result["reward_risk_ratio"], float)
    assert eval_result["reward_risk_ratio"] > 1.2
