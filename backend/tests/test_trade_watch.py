"""Unit and behavioral tests for Phase 02: Trade watcher lifecycle, adapters, and API routes."""

import pytest
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from shootingstar.adapters.binance_market_events import PublicTradeEvent
from shootingstar.adapters.db.models import (
    Base,
    CandidatePlanModel,
    TradeObservationModel,
    TradeWatchModel,
)
from shootingstar.adapters.db.repository import (
    CandidatePlanRepository,
    TradeObservationRepository,
    TradeWatchRepository,
)
from shootingstar.application.trade_watch import (
    ActiveReservationConflictError,
    ExecutionModeMismatchError,
    TradeWatchService,
)
from shootingstar.domain.models import Candle
from shootingstar.domain.trade_plan import (
    CandidateState,
    ExecutionMode,
    ExitReason,
    RiskConfig,
    SymbolFilters,
)
from shootingstar.api.app import app


@pytest.fixture
def test_db_session():
    from sqlalchemy.pool import StaticPool
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()

@pytest.fixture
def btc_symbol_filters() -> SymbolFilters:
    return SymbolFilters(
        symbol="BTCUSDT",
        tick_size=Decimal("0.01"),
        step_size=Decimal("0.00001"),
        min_notional=Decimal("5.0"),
        min_qty=Decimal("0.00001"),
    )


@pytest.fixture
def sample_risk_config() -> RiskConfig:
    return RiskConfig(
        max_notional_usdt=Decimal("2000.00"),
        max_planned_loss_usdt=Decimal("100.00"),
        fee_rate_bps=Decimal("10.0"),
        slippage_bps=Decimal("5.0"),
        max_wait_duration_ms=1_800_000,
        max_entry_deviation_pct=Decimal("0.002"),
        freshness_tolerance_ms=120_000,
        max_event_lag_ms=5_000,
        cost_model_source="vip0-doc-ref",
    )


def test_atomic_reservation_blocks_second_watch_or_position(test_db_session, sample_risk_config, btc_symbol_filters):
    watch_repo = TradeWatchRepository(test_db_session)
    cand_repo = CandidatePlanRepository(test_db_session)
    obs_repo = TradeObservationRepository(test_db_session)
    service = TradeWatchService(watch_repo, cand_repo, obs_repo)

    # 1. Start first watch for operator "user1" on "BTCUSDT"
    watch1 = service.start_watch(
        operator_id="user1",
        symbol="BTCUSDT",
        risk_config=sample_risk_config,
        symbol_filters=btc_symbol_filters,
    )
    assert watch1.status == "WATCHING"

    # 2. Starting second watch for same operator on same symbol MUST fail with ActiveReservationConflictError
    with pytest.raises(ActiveReservationConflictError, match="already has active exposure"):
        service.start_watch(
            operator_id="user1",
            symbol="BTCUSDT",
            risk_config=sample_risk_config,
            symbol_filters=btc_symbol_filters,
        )

    # 3. Starting watch for different operator succeeds
    watch2 = service.start_watch(
        operator_id="user2",
        symbol="BTCUSDT",
        risk_config=sample_risk_config,
        symbol_filters=btc_symbol_filters,
    )
    assert watch2.operator_id == "user2"


def test_lease_fencing_atomic_cas(test_db_session, sample_risk_config, btc_symbol_filters):
    watch_repo = TradeWatchRepository(test_db_session)
    cand_repo = CandidatePlanRepository(test_db_session)
    obs_repo = TradeObservationRepository(test_db_session)
    service = TradeWatchService(watch_repo, cand_repo, obs_repo)

    watch = service.start_watch(
        operator_id="worker_test",
        symbol="BTCUSDT",
        risk_config=sample_risk_config,
        symbol_filters=btc_symbol_filters,
        lease_owner="worker_1",
        lease_token="token_a",
        lease_ttl_ms=30_000,
        current_time_ms=1000,
    )

    # Worker 2 tries to acquire unexpired lease with different token -> fails
    acquired = watch_repo.acquire_or_renew_lease(
        watch_id=watch.id,
        worker_id="worker_2",
        lease_token="token_b",
        lease_ttl_ms=30_000,
        current_time_ms=5000,
    )
    assert acquired is False

    # Worker 1 renews own lease with matching token -> succeeds
    renewed = watch_repo.acquire_or_renew_lease(
        watch_id=watch.id,
        worker_id="worker_1",
        lease_token="token_a",
        lease_ttl_ms=30_000,
        current_time_ms=6000,
    )
    assert renewed is True

    # After expiry (time 40000 > 6000 + 30000 = 36000), worker 2 can claim
    claimed = watch_repo.acquire_or_renew_lease(
        watch_id=watch.id,
        worker_id="worker_2",
        lease_token="token_b",
        lease_ttl_ms=30_000,
        current_time_ms=40_000,
    )
    assert claimed is True


def test_immutable_execution_mode_and_partial_exits(test_db_session, sample_risk_config, btc_symbol_filters):
    watch_repo = TradeWatchRepository(test_db_session)
    cand_repo = CandidatePlanRepository(test_db_session)
    obs_repo = TradeObservationRepository(test_db_session)
    service = TradeWatchService(watch_repo, cand_repo, obs_repo)

    watch = service.start_watch(
        operator_id="op1",
        symbol="BTCUSDT",
        risk_config=sample_risk_config,
        symbol_filters=btc_symbol_filters,
    )

    # Seed candidate plan
    cand = CandidatePlanModel(
        id="cand_100",
        watch_id=watch.id,
        strategy_version="v1",
        rule_config_hash="abc",
        decision_time_ms=1_000_000,
        available_cutoff_ms=1_000_000,
        entry_zone_json='{"proposed_entry": "90000"}',
        confirmation_json='{"support_level": "89500", "reclaim_level": "90000"}',
        invalidation_json='{"invalidation_price": "89000"}',
        stop_price=89000.0,
        target_price=92000.0,
        wait_expires_at_ms=2_000_000,
        horizon_ms=1_800_000,
    )
    cand_repo.save(cand)

    # 1. Record MANUAL_REPORTED entry for 0.01000 BTC
    watch, entry_obs = service.record_entry(
        watch_id=watch.id,
        candidate_id="cand_100",
        mode=ExecutionMode.MANUAL_REPORTED,
        price=Decimal("90000"),
        quantity=Decimal("0.01000"),
        actual_entry_time_ms=1_050_000,
        receipt_time_ms=1_051_000,
        idempotency_key="entry_key_1",
    )
    assert watch.position_state == "OPEN"
    assert watch.execution_mode == "MANUAL_REPORTED"
    assert watch.deadline_ms == 1_050_000 + 1_800_000  # Exactly entry + 30m

    # 2. Attempt to exit with PAPER mode on MANUAL position MUST be rejected
    with pytest.raises(ExecutionModeMismatchError, match="cannot be closed by PAPER exit"):
        service.record_exit(
            watch_id=watch.id,
            candidate_id="cand_100",
            mode=ExecutionMode.PAPER,
            price=Decimal("91000"),
            quantity=Decimal("0.00500"),
            exit_reason=ExitReason.TP_HIT,
            actual_exit_time_ms=1_060_000,
            receipt_time_ms=1_061_000,
            idempotency_key="exit_key_paper",
        )

    # 3. Partial exit with MANUAL_REPORTED for 0.00400 BTC
    watch, exit_obs_1 = service.record_exit(
        watch_id=watch.id,
        candidate_id="cand_100",
        mode=ExecutionMode.MANUAL_REPORTED,
        price=Decimal("91500"),
        quantity=Decimal("0.00400"),
        exit_reason=ExitReason.TP_HIT,
        actual_exit_time_ms=1_070_000,
        receipt_time_ms=1_071_000,
        idempotency_key="exit_key_partial_1",
    )
    assert exit_obs_1.remaining_quantity == Decimal("0.00600")
    # Position remains OPEN (reservation preserved)
    assert watch.position_state == "OPEN"

    # 4. Final exit for remaining 0.00600 BTC
    watch, exit_obs_2 = service.record_exit(
        watch_id=watch.id,
        candidate_id="cand_100",
        mode=ExecutionMode.MANUAL_REPORTED,
        price=Decimal("91800"),
        quantity=Decimal("0.00600"),
        exit_reason=ExitReason.TP_HIT,
        actual_exit_time_ms=1_080_000,
        receipt_time_ms=1_081_000,
        idempotency_key="exit_key_final",
    )
    assert exit_obs_2.remaining_quantity == Decimal("0.0")
    assert watch.position_state == "CLOSED"


def test_ordered_trades_boundary_precedence(test_db_session, sample_risk_config, btc_symbol_filters):
    watch_repo = TradeWatchRepository(test_db_session)
    cand_repo = CandidatePlanRepository(test_db_session)
    obs_repo = TradeObservationRepository(test_db_session)
    service = TradeWatchService(watch_repo, cand_repo, obs_repo)

    watch = service.start_watch(
        operator_id="op_boundary",
        symbol="BTCUSDT",
        risk_config=sample_risk_config,
        symbol_filters=btc_symbol_filters,
    )
    cand = CandidatePlanModel(
        id="cand_boundary",
        watch_id=watch.id,
        strategy_version="v1",
        rule_config_hash="abc",
        decision_time_ms=1_000_000,
        available_cutoff_ms=1_000_000,
        entry_zone_json='{"proposed_entry": "90000"}',
        confirmation_json='{"support_level": "89500", "reclaim_level": "90000"}',
        invalidation_json='{"invalidation_price": "89000"}',
        stop_price=89000.0,
        target_price=92000.0,
        wait_expires_at_ms=2_000_000,
        horizon_ms=1_800_000,
    )
    cand_repo.save(cand)

    # Entry at 1_000_000 -> deadline is 2_800_000
    watch, _ = service.record_entry(
        watch_id=watch.id,
        candidate_id="cand_boundary",
        mode=ExecutionMode.PAPER,
        price=Decimal("90000"),
        quantity=Decimal("0.01"),
        actual_entry_time_ms=1_000_000,
        receipt_time_ms=1_000_050,
        idempotency_key="entry_boundary_1",
    )
    assert watch.deadline_ms == 2_800_000

    # Trade exactly at deadline_ms (2_800_000) touches target (92050 >= 92000):
    # INVARIANT: Touch at exact deadline takes precedence over TIMEOUT!
    trade_at_boundary = PublicTradeEvent(
        trade_id=1,
        symbol="BTCUSDT",
        price=Decimal("92050"),
        quantity=Decimal("0.1"),
        event_time_ms=2_800_000,
        is_buyer_maker=False,
        received_at_ms=2_800_010,
    )
    result = service.process_ordered_trades(watch.id, [trade_at_boundary])
    assert result is not None
    assert result[0] == ExitReason.TP_HIT

    # Reset position to OPEN for testing strictly after deadline
    watch.position_state = "OPEN"
    watch_repo.save(watch)

    # Trade strictly after deadline (2_800_001):
    # INVARIANT: Post-deadline events MUST trigger TIMEOUT, barrier hit is ignored!
    trade_after_deadline = PublicTradeEvent(
        trade_id=2,
        symbol="BTCUSDT",
        price=Decimal("92500"),  # Above target, but AFTER deadline!
        quantity=Decimal("0.1"),
        event_time_ms=2_800_001,
        is_buyer_maker=False,
        received_at_ms=2_800_020,
    )
    result_after = service.process_ordered_trades(watch.id, [trade_after_deadline])
    assert result_after is not None
    assert result_after[0] == ExitReason.TIMEOUT


def test_ambiguous_ohlc_transitions_to_exit_required(test_db_session, sample_risk_config, btc_symbol_filters):
    watch_repo = TradeWatchRepository(test_db_session)
    cand_repo = CandidatePlanRepository(test_db_session)
    obs_repo = TradeObservationRepository(test_db_session)
    service = TradeWatchService(watch_repo, cand_repo, obs_repo)

    watch = service.start_watch(
        operator_id="op_ambiguous",
        symbol="BTCUSDT",
        risk_config=sample_risk_config,
        symbol_filters=btc_symbol_filters,
    )
    cand = CandidatePlanModel(
        id="cand_ambiguous",
        watch_id=watch.id,
        strategy_version="v1",
        rule_config_hash="abc",
        decision_time_ms=1_000_000,
        available_cutoff_ms=1_000_000,
        entry_zone_json='{"proposed_entry": "90000"}',
        confirmation_json='{"support_level": "89500", "reclaim_level": "90000"}',
        invalidation_json='{"invalidation_price": "89000"}',
        stop_price=89000.0,
        target_price=92000.0,
        wait_expires_at_ms=2_000_000,
        horizon_ms=1_800_000,
    )
    cand_repo.save(cand)

    watch, _ = service.record_entry(
        watch_id=watch.id,
        candidate_id="cand_ambiguous",
        mode=ExecutionMode.PAPER,
        price=Decimal("90000"),
        quantity=Decimal("0.01"),
        actual_entry_time_ms=1_000_000,
        receipt_time_ms=1_000_050,
        idempotency_key="entry_ambiguous_1",
    )

    # Replay candle that breaches SL (low=88500 <= 89000) AND touches TP (high=92500 >= 92000)
    ambiguous_candle = Candle(
        venue="BINANCE",
        symbol="BTCUSDT",
        timeframe="1m",
        open_time_ms=1_060_000,
        close_time_ms=1_120_000,
        open=90000.0,
        high=92500.0,
        low=88500.0,
        close=91000.0,
        volume=50.0,
        quote_volume=4500000.0,
        trades_count=500,
        taker_buy_base_volume=25.0,
        taker_buy_quote_volume=2250000.0,
    )

    exit_reason, label = service.process_ohlc_candle(watch.id, ambiguous_candle)
    assert exit_reason is None
    assert label == "AMBIGUOUS"

    # Position MUST NOT remain OPEN: transitioned to EXIT_REQUIRED
    updated_watch = watch_repo.get_by_id(watch.id)
    assert updated_watch.position_state == "EXIT_REQUIRED"


def test_api_routes_admin_auth_and_endpoints(monkeypatch, test_db_session):
    import contextlib

    @contextlib.contextmanager
    def mock_db_session():
        yield test_db_session

    monkeypatch.setattr("shootingstar.api.trade_plan_routes.get_db_session", mock_db_session)
    monkeypatch.setenv("SHOOTINGSTAR_ADMIN_KEY", "secret-test-key")
    client = TestClient(app)
    # 1. Unauthenticated request -> 403 Forbidden
    res_no_auth = client.post(
        "/trade-watches",
        json={
            "symbol": "BTCUSDT",
            "max_notional_usdt": "2000.00",
            "max_planned_loss_usdt": "100.00",
            "fee_rate_bps": "10.0",
            "slippage_bps": "5.0",
            "max_wait_duration_ms": 1800000,
            "max_entry_deviation_pct": "0.002",
            "freshness_tolerance_ms": 120000,
            "max_event_lag_ms": 5000,
            "cost_model_source": "vip0-doc",
        },
    )
    assert res_no_auth.status_code == 403

    # 2. Authenticated request -> 201 Created
    res_auth = client.post(
        "/trade-watches",
        headers={"X-Admin-Key": "secret-test-key"},
        json={
            "symbol": "BTCUSDT",
            "max_notional_usdt": "2000.00",
            "max_planned_loss_usdt": "100.00",
            "fee_rate_bps": "10.0",
            "slippage_bps": "5.0",
            "max_wait_duration_ms": 1800000,
            "max_entry_deviation_pct": "0.002",
            "freshness_tolerance_ms": 120000,
            "max_event_lag_ms": 5000,
            "cost_model_source": "vip0-doc",
        },
    )
    assert res_auth.status_code == 201
    watch_data = res_auth.json()
    assert watch_data["status"] == "WATCHING"
    assert watch_data["operator_id"] == "local_admin"
    watch_id = watch_data["id"]

    # 3. GET /trade-watches/{id}
    res_get = client.get(
        f"/trade-watches/{watch_id}",
        headers={"X-Admin-Key": "secret-test-key"},
    )
    assert res_get.status_code == 200
    assert res_get.json()["id"] == watch_id

    # 4. POST /trade-watches/{id}/stop
    res_stop = client.post(
        f"/trade-watches/{watch_id}/stop",
        headers={"X-Admin-Key": "secret-test-key"},
    )
    assert res_stop.status_code == 200
    assert res_stop.json()["status"] == "STOPPED"


def test_run_watch_worker_stopped_flat_exits(test_db_session, sample_risk_config, btc_symbol_filters):
    import contextlib
    from shootingstar.application.trade_watch import run_watch_worker

    watch_repo = TradeWatchRepository(test_db_session)
    cand_repo = CandidatePlanRepository(test_db_session)
    obs_repo = TradeObservationRepository(test_db_session)
    service = TradeWatchService(watch_repo, cand_repo, obs_repo)

    watch = service.start_watch(
        operator_id="op_test",
        symbol="BTCUSDT",
        risk_config=sample_risk_config,
        symbol_filters=btc_symbol_filters,
    )
    watch.status = "STOPPED"
    watch.position_state = "FLAT"
    watch_repo.save(watch)
    test_db_session.commit()

    @contextlib.contextmanager
    def session_factory():
        yield test_db_session

    # Worker should recognize STOPPED + FLAT and exit with returncode 0 immediately
    res = run_watch_worker(
        watch_id=watch.id,
        session_factory=session_factory,
        symbol="BTCUSDT",
        once=True,
    )
    assert res == 0


def test_run_watch_worker_open_timeout_by_clock(test_db_session, sample_risk_config, btc_symbol_filters, monkeypatch):
    import contextlib
    import time
    from shootingstar.application.trade_watch import run_watch_worker

    watch_repo = TradeWatchRepository(test_db_session)
    cand_repo = CandidatePlanRepository(test_db_session)
    obs_repo = TradeObservationRepository(test_db_session)
    service = TradeWatchService(watch_repo, cand_repo, obs_repo)

    watch = service.start_watch(
        operator_id="op_test_clock",
        symbol="BTCUSDT",
        risk_config=sample_risk_config,
        symbol_filters=btc_symbol_filters,
    )

    # Simulate OPEN position with expired deadline in past
    now_ms = int(time.time() * 1000)
    watch.position_state = "OPEN"
    watch.deadline_ms = now_ms - 5000  # 5 seconds overdue
    watch_repo.save(watch)
    test_db_session.commit()

    # Mock events_client to return empty list (e.g. disconnected or no trades)
    monkeypatch.setattr(
        "shootingstar.adapters.binance_market_events.BinanceMarketEventsClient.fetch_recent_trades",
        lambda self, symbol, limit=50: [],
    )

    @contextlib.contextmanager
    def session_factory():
        yield test_db_session

    # Run single worker cycle
    res = run_watch_worker(
        watch_id=watch.id,
        session_factory=session_factory,
        symbol="BTCUSDT",
        once=True,
    )
    assert res == 0

    updated = watch_repo.get_by_id(watch.id)
    # Clock timeout MUST transition to EXIT_REQUIRED without requiring trade touches
    assert updated.position_state == "EXIT_REQUIRED"


def test_run_watch_worker_split_brain_lease_refusal(test_db_session, sample_risk_config, btc_symbol_filters):
    import contextlib
    import time
    from shootingstar.application.trade_watch import run_watch_worker

    watch_repo = TradeWatchRepository(test_db_session)
    cand_repo = CandidatePlanRepository(test_db_session)
    obs_repo = TradeObservationRepository(test_db_session)
    service = TradeWatchService(watch_repo, cand_repo, obs_repo)

    watch = service.start_watch(
        operator_id="op_split",
        symbol="BTCUSDT",
        risk_config=sample_risk_config,
        symbol_filters=btc_symbol_filters,
    )

    now_ms = int(time.time() * 1000)
    # Another worker holds active lease until now + 60s
    watch.lease_owner = "worker_other_active"
    watch.lease_token = "tok_other"
    watch.lease_expires_at_ms = now_ms + 60_000
    watch_repo.save(watch)
    test_db_session.commit()

    @contextlib.contextmanager
    def session_factory():
        yield test_db_session

    # New worker with different worker_id must fail lease acquisition and return 1
    res = run_watch_worker(
        watch_id=watch.id,
        session_factory=session_factory,
        symbol="BTCUSDT",
        once=True,
        worker_id="worker_new_attempt",
    )
    assert res == 1


def test_cas_lease_refuses_same_owner_with_wrong_token(test_db_session, sample_risk_config, btc_symbol_filters):
    import time

    watch_repo = TradeWatchRepository(test_db_session)
    cand_repo = CandidatePlanRepository(test_db_session)
    obs_repo = TradeObservationRepository(test_db_session)
    service = TradeWatchService(watch_repo, cand_repo, obs_repo)

    watch = service.start_watch(
        operator_id="op_fencing",
        symbol="BTCUSDT",
        risk_config=sample_risk_config,
        symbol_filters=btc_symbol_filters,
    )

    now_ms = int(time.time() * 1000)
    # Lease held by worker_alpha with token_123, expires in 60s
    watch.lease_owner = "worker_alpha"
    watch.lease_token = "token_123"
    watch.lease_expires_at_ms = now_ms + 60_000
    watch_repo.save(watch)
    test_db_session.commit()

    # 1. Same worker_id ("worker_alpha") but wrong/stale token ("stale_token_999") -> MUST BE REFUSED
    renew_failed = watch_repo.acquire_or_renew_lease(
        watch_id=watch.id,
        worker_id="worker_alpha",
        lease_token="stale_token_999",
        lease_ttl_ms=30_000,
        current_time_ms=now_ms,
    )
    assert renew_failed is False

    # 2. Same worker_id ("worker_alpha") with matching token ("token_123") -> MUST SUCCEED
    renew_success = watch_repo.acquire_or_renew_lease(
        watch_id=watch.id,
        worker_id="worker_alpha",
        lease_token="token_123",
        lease_ttl_ms=30_000,
        current_time_ms=now_ms,
    )
    assert renew_success is True


def test_run_watch_worker_stopped_open_multi_cycle_monitoring(test_db_session, sample_risk_config, btc_symbol_filters, monkeypatch):
    import contextlib
    import json
    import time
    from shootingstar.application.trade_watch import run_watch_worker

    watch_repo = TradeWatchRepository(test_db_session)
    cand_repo = CandidatePlanRepository(test_db_session)
    obs_repo = TradeObservationRepository(test_db_session)
    service = TradeWatchService(watch_repo, cand_repo, obs_repo)

    watch = service.start_watch(
        operator_id="op_multi",
        symbol="BTCUSDT",
        risk_config=sample_risk_config,
        symbol_filters=btc_symbol_filters,
    )
    now_ms = int(time.time() * 1000)
    cand_id = "cand_multi_01"
    c_plan = CandidatePlanModel(
        id=cand_id,
        watch_id=watch.id,
        strategy_version="v1-support-reclaim-30m",
        rule_config_hash="hash_multi",
        decision_time_ms=now_ms - 60000,
        available_cutoff_ms=now_ms - 60000,
        entry_zone_json=json.dumps({"min_price": "60000.00", "max_price": "60100.00", "proposed_entry": "60050.00"}),
        confirmation_json=json.dumps({"support_level": "59900.00", "reclaim_level": "60000.00"}),
        invalidation_json=json.dumps({"invalidation_price": "59800.00", "buffer_percent": "0.002"}),
        stop_price=Decimal("59700.00"),
        target_price=Decimal("60500.00"),
        wait_expires_at_ms=now_ms + 1200000,
        horizon_ms=1800000,
        candidate_state="CONFIRMED",
    )
    cand_repo.save(c_plan)
    watch.active_candidate_id = cand_id
    watch_repo.save(watch)

    # Enter position
    watch, _ = service.record_entry(
        watch_id=watch.id,
        candidate_id=cand_id,
        mode=ExecutionMode.PAPER,
        price=Decimal("60050.00"),
        quantity=Decimal("0.02"),
        actual_entry_time_ms=now_ms,
        receipt_time_ms=now_ms + 10,
        idempotency_key="key_multi_entry",
    )
    assert watch.position_state == "OPEN"

    # Operator stops watch while OPEN
    watch = service.stop_watch(watch.id)
    assert watch.status == "STOPPED"
    test_db_session.commit()

    @contextlib.contextmanager
    def session_factory():
        yield test_db_session

    worker_id = "worker_multi_test"
    lease_tok = "tok_multi_test"

    # Cycle 1: No trades, position remains OPEN, discovery is NOT run
    monkeypatch.setattr(
        "shootingstar.adapters.binance_market_events.BinanceMarketEventsClient.fetch_recent_trades",
        lambda self, symbol, limit=50: [],
    )
    res1 = run_watch_worker(
        watch_id=watch.id,
        session_factory=session_factory,
        symbol="BTCUSDT",
        once=True,
        worker_id=worker_id,
        lease_token=lease_tok,
    )
    assert res1 == 0
    w1 = watch_repo.get_by_id(watch.id)
    assert w1.status == "STOPPED"
    assert w1.position_state == "OPEN"  # Continues monitoring!

    # Cycle 2: Trade arrives touching TP -> triggers EXIT_REQUIRED
    tp_trade = PublicTradeEvent(
        symbol="BTCUSDT",
        trade_id=201,
        price=Decimal("60500.00"),
        quantity=Decimal("0.01"),
        event_time_ms=now_ms + 20000,
        received_at_ms=now_ms + 20005,
        is_buyer_maker=False,
    )
    monkeypatch.setattr(
        "shootingstar.adapters.binance_market_events.BinanceMarketEventsClient.fetch_recent_trades",
        lambda self, symbol, limit=50: [tp_trade],
    )
    res2 = run_watch_worker(
        watch_id=watch.id,
        session_factory=session_factory,
        symbol="BTCUSDT",
        once=True,
        worker_id=worker_id,
        lease_token=lease_tok,
    )
    assert res2 == 0
    w2 = watch_repo.get_by_id(watch.id)
    assert w2.position_state == "EXIT_REQUIRED"  # Transitioned!

    # Operator executes full exit
    w_closed, exit_obs = service.record_exit(
        watch_id=watch.id,
        candidate_id=cand_id,
        mode=ExecutionMode.PAPER,
        price=Decimal("60500.00"),
        quantity=Decimal("0.02"),
        actual_exit_time_ms=now_ms + 20000,
        receipt_time_ms=now_ms + 20010,
        idempotency_key="key_multi_exit",
        exit_reason=ExitReason.TP_HIT,
    )
    assert w_closed.position_state == "CLOSED"
    test_db_session.commit()

    # Cycle 3: Now STOPPED and CLOSED -> worker exits cleanly
    res3 = run_watch_worker(
        watch_id=watch.id,
        session_factory=session_factory,
        symbol="BTCUSDT",
        once=True,
        worker_id=worker_id,
        lease_token=lease_tok,
    )
    assert res3 == 0
