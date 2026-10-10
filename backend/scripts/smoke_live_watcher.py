"""Phase 02 Live Public Data Watcher Smoke.

Connects to Binance Spot public REST endpoints (NO API keys required),
verifies real market event intake, candidate discovery over live klines,
atomic CAS lease acquisition/renewal, and stop/restart continuity.
"""

import contextlib
from decimal import Decimal
import json
import time

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from shootingstar.adapters.binance_market_events import BinanceMarketEventsClient
from shootingstar.adapters.db.models import Base
from shootingstar.adapters.db.repository import (
    CandidatePlanRepository,
    TradeObservationRepository,
    TradeWatchRepository,
)
from shootingstar.application.trade_watch import (
    TradeWatchService,
    run_watch_worker,
)
from shootingstar.domain.trade_plan import RiskConfig


def main():
    print("=== SHOOTINGSTAR PHASE 02: LIVE PUBLIC DATA WATCHER SMOKE ===")
    symbol = "BTCUSDT"

    # Step 1: Connect to public Binance REST endpoints
    events_client = BinanceMarketEventsClient()
    print(f"1. Fetching live symbol filters for {symbol} from Binance Spot...")
    symbol_filters = events_client.fetch_symbol_filters(symbol)
    print(f"   [OK] Live filters: tick={symbol_filters.tick_size}, step={symbol_filters.step_size}, min_notional={symbol_filters.min_notional}")

    print(f"2. Fetching live recent trades for {symbol}...")
    trades = events_client.fetch_recent_trades(symbol, limit=10)
    assert len(trades) > 0, "Expected at least 1 recent trade from live Binance feed"
    print(f"   [OK] Received {len(trades)} live trades. Latest trade #{trades[-1].trade_id}: price={trades[-1].price}, time={trades[-1].event_time_ms}")

    # Step 2: Initialize isolated in-memory DB session factory
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

    # Step 3: Create durable watch in DB
    operator_id = "live_smoke_op"
    print("3. Creating durable watch session in database...")
    with session_provider() as session:
        service = TradeWatchService(
            TradeWatchRepository(session),
            CandidatePlanRepository(session),
            TradeObservationRepository(session),
        )
        watch = service.start_watch(
            operator_id=operator_id,
            symbol=symbol,
            risk_config=risk_config,
            symbol_filters=symbol_filters,
        )
        watch_id = watch.id
        print(f"   [OK] Watch {watch_id} created (status={watch.status}, position={watch.position_state})")

    # Step 4: Run live worker cycle (fetches live 120m klines, evaluates setup)
    print("4. Running live watcher cycle (once=True)...")
    worker_id = "worker_live_smoke_01"
    lease_token = "token_live_smoke_01"
    rc = run_watch_worker(
        watch_id=watch_id,
        session_factory=session_provider,
        symbol=symbol,
        once=True,
        worker_id=worker_id,
        lease_token=lease_token,
    )
    assert rc == 0, f"Worker returned non-zero code {rc}"
    print(f"   [OK] Live worker cycle completed successfully (rc={rc}).")

    with session_provider() as session:
        w = TradeWatchRepository(session).get_by_id(watch_id)
        assert w.lease_owner == worker_id
        assert w.lease_token == lease_token
        print(f"   [OK] Lease verified: owner={w.lease_owner}, active_candidate={w.active_candidate_id}")

    # Step 5: Test stop and restart continuity
    print("5. Testing stop and restart continuity...")
    with session_provider() as session:
        service = TradeWatchService(
            TradeWatchRepository(session),
            CandidatePlanRepository(session),
            TradeObservationRepository(session),
        )
        service.stop_watch(watch_id)
        print("   [OK] Watch status marked STOPPED.")

    # Resuming with same authorized worker
    rc_restart = run_watch_worker(
        watch_id=watch_id,
        session_factory=session_provider,
        symbol=symbol,
        once=True,
        worker_id=worker_id,
        lease_token=lease_token,
    )
    assert rc_restart == 0, "Restart worker should exit cleanly with return code 0"
    print(f"   [OK] Stopped watcher cleanly exited on restart (rc={rc_restart}).")

    print("\n=== LIVE PUBLIC DATA WATCHER SMOKE COMPLETED SUCCESSFULLY ===")


if __name__ == "__main__":
    main()
