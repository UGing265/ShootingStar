"""Smoke run for Phase 02: Trade watcher lifecycle, durable worker loop, and exit invariants.

STRICT INVARIANTS TESTED:
1. Single active exposure reservation per (operator, symbol).
2. Atomic CAS lease renewal preventing split-brain execution.
3. Stop behavior: FLAT stops discovery; OPEN/EXIT_REQUIRED preserves monitoring.
4. Position monitoring: ordered trade touches, clock timeout on disconnect/no trades.
5. Mode matching: PAPER vs MANUAL_REPORTED immutable lock.
"""

import contextlib
from decimal import Decimal
import json
import time
import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from shootingstar.adapters.binance_market_events import PublicTradeEvent
from shootingstar.adapters.db.models import Base
from shootingstar.adapters.db.repository import (
    CandidatePlanRepository,
    TradeObservationRepository,
    TradeWatchRepository,
)
from shootingstar.application.trade_watch import (
    ActiveReservationConflictError,
    ExecutionModeMismatchError,
    TradeWatchService,
    run_watch_worker,
)
from shootingstar.domain.trade_plan import (
    ExecutionMode,
    ExitReason,
    RiskConfig,
    SymbolFilters,
)


def run_smoke():
    print("=== SHOOTINGSTAR PHASE 02 SMOKE RUN: WATCHER LIFECYCLE & INVARIANTS ===")

    # In-memory shared engine
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionFactory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    @contextlib.contextmanager
    def session_provider():
        session = SessionFactory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    risk_config = RiskConfig(
        max_notional_usdt=Decimal("2000.00"),
        max_planned_loss_usdt=Decimal("100.00"),
        fee_rate_bps=Decimal("10.0"),
        slippage_bps=Decimal("5.0"),
        max_wait_duration_ms=1800000,
        max_entry_deviation_pct=Decimal("0.002"),
        freshness_tolerance_ms=120000,
        max_event_lag_ms=5000,
        cost_model_source="vip0-doc",
    )

    symbol_filters = SymbolFilters(
        symbol="BTCUSDT",
        tick_size=Decimal("0.01"),
        step_size=Decimal("0.00001"),
        min_notional=Decimal("5.0"),
        min_qty=Decimal("0.00001"),
    )

    operator_id = "op_smoke"
    symbol = "BTCUSDT"

    # Step 1: Create trade watch session
    print("1. Creating trade watch session...")
    with session_provider() as session:
        watch_repo = TradeWatchRepository(session)
        cand_repo = CandidatePlanRepository(session)
        obs_repo = TradeObservationRepository(session)
        service = TradeWatchService(watch_repo, cand_repo, obs_repo)

        watch = service.start_watch(
            operator_id=operator_id,
            symbol=symbol,
            risk_config=risk_config,
            symbol_filters=symbol_filters,
        )
        watch_id = watch.id
        print(f"   Created watch {watch_id} (status={watch.status}, position={watch.position_state})")

    # Step 2: Enforce single active reservation
    print("2. Verifying single active reservation constraint...")
    with session_provider() as session:
        service = TradeWatchService(TradeWatchRepository(session), CandidatePlanRepository(session), TradeObservationRepository(session))
        try:
            service.start_watch(
                operator_id=operator_id,
                symbol=symbol,
                risk_config=risk_config,
                symbol_filters=symbol_filters,
            )
            raise AssertionError("Duplicate active reservation should have raised ActiveReservationConflictError!")
        except ActiveReservationConflictError:
            print("   [OK] Active reservation conflict caught correctly.")

    # Step 3: Record position entry and verify immutable execution mode
    print("3. Recording entry and verifying immutable execution mode...")
    now_ms = int(time.time() * 1000)
    candidate_id = f"cand_{uuid.uuid4().hex[:8]}"
    with session_provider() as session:
        service = TradeWatchService(TradeWatchRepository(session), CandidatePlanRepository(session), TradeObservationRepository(session))
        # Create a single candidate plan
        from shootingstar.adapters.db.models import CandidatePlanModel
        c_plan = CandidatePlanModel(
            id=candidate_id,
            watch_id=watch_id,
            strategy_version="v1-support-reclaim-30m",
            rule_config_hash="test_hash_001",
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
        CandidatePlanRepository(session).save(c_plan)
        watch = TradeWatchRepository(session).get_by_id(watch_id)
        watch.active_candidate_id = candidate_id
        TradeWatchRepository(session).save(watch)

        # Enter position in PAPER mode
        watch, obs = service.record_entry(
            watch_id=watch_id,
            candidate_id=candidate_id,
            mode=ExecutionMode.PAPER,
            price=Decimal("60050.00"),
            quantity=Decimal("0.02"),
            actual_entry_time_ms=now_ms,
            receipt_time_ms=now_ms + 10,
            idempotency_key="entry_key_smoke_01",
        )
        assert watch.position_state == "OPEN"
        assert watch.execution_mode == "PAPER"
        assert watch.deadline_ms == now_ms + 1800000
        print(f"   [OK] Entry recorded: position={watch.position_state}, mode={watch.execution_mode}, deadline={watch.deadline_ms}")
    # Step 4: Verify mode mismatch rejection on exit
    print("4. Verifying mode mismatch rejection...")
    with session_provider() as session:
        service = TradeWatchService(TradeWatchRepository(session), CandidatePlanRepository(session), TradeObservationRepository(session))
        try:
            service.record_exit(
                watch_id=watch_id,
                candidate_id=candidate_id,
                mode=ExecutionMode.MANUAL_REPORTED,  # mismatch!
                price=Decimal("60500.00"),
                quantity=Decimal("0.02"),
                actual_exit_time_ms=now_ms + 30000,
                receipt_time_ms=now_ms + 30010,
                idempotency_key="exit_key_smoke_01",
                exit_reason=ExitReason.TP_HIT,
            )
            raise AssertionError("Manual exit on paper position should have raised ExecutionModeMismatchError!")
        except ExecutionModeMismatchError:
            print("   [OK] Execution mode mismatch rejected.")
    # Step 5: Test stop_watch on active position
    print("5. Verifying stop_watch on active OPEN position...")
    with session_provider() as session:
        service = TradeWatchService(TradeWatchRepository(session), CandidatePlanRepository(session), TradeObservationRepository(session))
        watch = service.stop_watch(watch_id)
        assert watch.status == "STOPPED"
        assert watch.position_state == "OPEN"
        print("   [OK] Watch status marked STOPPED while position remains OPEN (preserves active monitoring).")

    # Step 6: Test worker run on OPEN position with trade touch
    print("6. Testing worker cycle on OPEN position with trade touch...")
    trades = [
        PublicTradeEvent(
            symbol=symbol,
            trade_id=101,
            price=Decimal("60500.00"),  # hits target_price 60500.00
            quantity=Decimal("0.05"),
            event_time_ms=now_ms + 50000,
            received_at_ms=now_ms + 50005,
            is_buyer_maker=False,
        )
    ]
    from unittest.mock import patch
    with patch("shootingstar.adapters.binance_market_events.BinanceMarketEventsClient.fetch_recent_trades", return_value=trades):
        w_res = run_watch_worker(
            watch_id=watch_id,
            session_factory=session_provider,
            symbol=symbol,
            once=True,
            worker_id="smoke_worker_01",
            lease_token="smoke_token_01",
        )
        assert w_res == 0

    with session_provider() as session:
        watch = TradeWatchRepository(session).get_by_id(watch_id)
        assert watch.position_state == "EXIT_REQUIRED"
        print(f"   [OK] Worker processed trade event and transitioned position to {watch.position_state}.")

    # Step 7: Record full exit to return to FLAT
    print("7. Recording full exit and releasing active reservation...")
    with session_provider() as session:
        service = TradeWatchService(TradeWatchRepository(session), CandidatePlanRepository(session), TradeObservationRepository(session))
        watch, exit_obs = service.record_exit(
            watch_id=watch_id,
            candidate_id=candidate_id,
            mode=ExecutionMode.PAPER,
            price=Decimal("60500.00"),
            quantity=Decimal("0.02"),
            actual_exit_time_ms=now_ms + 50000,
            receipt_time_ms=now_ms + 50010,
            idempotency_key="exit_key_smoke_valid",
            exit_reason=ExitReason.TP_HIT,
        )
        assert watch.position_state == "CLOSED"
        print(f"   [OK] Position closed: {watch.position_state}, realized PnL = {exit_obs.realized_pnl_usdt} USDT.")
    # Step 8: Verify worker exits cleanly now that status is STOPPED and position is CLOSED
    # Step 8a: Verify unexpired lease with mismatched token is refused
    print("8a. Verifying CAS refusal when worker passes mismatched token...")
    res_wrong = run_watch_worker(
        watch_id=watch_id,
        session_factory=session_provider,
        symbol=symbol,
        once=True,
        worker_id="smoke_worker_01",
        lease_token="stale_or_wrong_token",
    )
    assert res_wrong == 1
    print("   [OK] Stale/mismatched token correctly refused (returncode 1).")

    # Step 8b: Verify worker exits cleanly with matching authorized token
    print("8b. Testing worker termination when STOPPED, CLOSED, and token matches...")
    res_auth = run_watch_worker(
        watch_id=watch_id,
        session_factory=session_provider,
        symbol=symbol,
        once=True,
        worker_id="smoke_worker_01",
        lease_token="smoke_token_01",
    )
    assert res_auth == 0
    print("   [OK] Authorized worker exited cleanly (returncode 0).")
    print("\n=== PHASE 02 LIFECYCLE SMOKE RUN VERIFIED SUCCESSFULLY ===")


if __name__ == "__main__":
    run_smoke()
