"""Smoke run for Phase 01: EntryStrategyEngine on real Binance Spot market data.

STRICT INVARIANTS TESTED:
1. Dynamically fetches real BTCUSDT filters from Binance /api/v3/exchangeInfo.
2. Uses frozen strategy parameters (v1-support-reclaim-30m, lookback=60, min_rr=1.2).
3. Evaluates real historical 1m candles with honest availability (observed_ingested_at_ms=None).
4. Reports honest evidence without post-hoc tuning.
5. Verifies causal zero-lookahead invariance on real market data.
"""

import sys
import time
from decimal import Decimal
from shootingstar.adapters.binance import BinanceSpotClient
from shootingstar.adapters.binance_market_events import BinanceMarketEventsClient
from shootingstar.application.entry_strategy import EntryStrategyEngine
from shootingstar.domain.models import Candle
from shootingstar.domain.trade_plan import (
    ExecutionMode,
    ObservationDecision,
    RiskConfig,
)


def main():
    print("=== SHOOTINGSTAR PHASE 01 SMOKE RUN: FROZEN CONFIG ON REAL MARKET DATA ===")
    events_client = BinanceMarketEventsClient()
    spot_client = BinanceSpotClient()

    # 1. Fetch dynamic symbol filters from Binance Spot exchangeInfo
    print("Fetching real BTCUSDT filters from /api/v3/exchangeInfo...")
    symbol_filters = events_client.fetch_symbol_filters("BTCUSDT")
    print(f"Loaded filters: tick_size={symbol_filters.tick_size}, step_size={symbol_filters.step_size}, min_notional={symbol_filters.min_notional}, min_qty={symbol_filters.min_qty}")

    # 2. Fetch real 1m candles
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - (180 * 60 * 1000)  # 3 hours of real klines
    print(f"Fetching real BTCUSDT 1m candles (start={start_ms})...")
    raw_rows = spot_client.fetch_klines(symbol="BTCUSDT", interval="1m", start_time_ms=start_ms, limit=180)
    print(f"Fetched {len(raw_rows)} real candles.")

    candles = []
    for r in raw_rows:
        open_time = int(r[0])
        close_time = int(r[6])
        # Historical klines have observed_ingested_at_ms=None (honest reporting)
        candles.append(
            Candle(
                venue="BINANCE",
                symbol="BTCUSDT",
                timeframe="1m",
                open_time_ms=open_time,
                close_time_ms=close_time,
                open=float(r[1]),
                high=float(r[2]),
                low=float(r[3]),
                close=float(r[4]),
                volume=float(r[5]),
                quote_volume=float(r[7]),
                trades_count=int(r[8]),
                taker_buy_base_volume=float(r[9]),
                taker_buy_quote_volume=float(r[10]),
                observed_ingested_at_ms=None,
            )
        )

    # 3. Documented risk configuration (Phase 01 gate)
    risk_config = RiskConfig(
        max_notional_usdt=Decimal("2000.00"),
        max_planned_loss_usdt=Decimal("100.00"),
        fee_rate_bps=Decimal("10.0"),  # VIP 0 Taker (documented in docs/binance-spot-fees.md)
        slippage_bps=Decimal("5.0"),
        max_wait_duration_ms=1_800_000,
        max_entry_deviation_pct=Decimal("0.002"),
        freshness_tolerance_ms=120_000,
        max_event_lag_ms=5_000,
        cost_model_source="docs/binance-spot-fees.md#vip0-baseline",
    )

    # 4. Frozen strategy version and parameters
    engine = EntryStrategyEngine(
        strategy_version="v1-support-reclaim-30m",
        lookback_bars=60,
        support_tolerance_pct=Decimal("0.0015"),
        sl_buffer_pct=Decimal("0.002"),
        reclaim_buffer_pct=Decimal("0.001"),
        min_reward_risk_ratio=Decimal("1.2"),
        assumed_latency_ms=1000,
    )
    print(f"Engine rule_config_hash: {engine.rule_config_hash}")

    # 5. Evaluate sequentially across the real dataset
    print("\n--- Evaluating frozen strategy across historical real candles ---")
    reason_tallies = {}
    candidate_found = None
    candidate_idx = None

    for idx in range(60, len(candles)):
        c_cutoff = candles[idx]
        cutoff_ms = c_cutoff.close_time_ms + 1000

        plan, decision, reasons = engine.create_candidate(
            candles=candles[: idx + 1],
            decision_time_ms=cutoff_ms,
            available_cutoff_ms=cutoff_ms,
            symbol_filters=symbol_filters,
            risk_config=risk_config,
        )

        for r in reasons:
            reason_tallies[r.value] = reason_tallies.get(r.value, 0) + 1

        if plan is not None and candidate_found is None:
            candidate_found = plan
            candidate_idx = idx
            print(f"Candidate observed at idx {idx} (close={c_cutoff.close}):")
            print(f"  Proposed Entry: {plan.proposed_entry} USDT")
            print(f"  Stop: {plan.stop_price} USDT")
            print(f"  Target: {plan.target_price} USDT")
            print(f"  Decision: {decision.value}")
            print(f"  Reasons: {[r.value for r in reasons]}")

    print(f"\nSequence Evaluation Results across {len(candles) - 60} evaluations:")
    for reason_name, count in reason_tallies.items():
        print(f"  - {reason_name}: {count} occurrences")

    # 6. Verify Causal Invariance at cutoff = candle index 90
    test_idx = min(90, len(candles) - 10)
    test_cutoff_ms = candles[test_idx].close_time_ms + 1000
    plan_base, dec_base, reasons_base = engine.create_candidate(
        candles=candles[: test_idx + 1],
        decision_time_ms=test_cutoff_ms,
        available_cutoff_ms=test_cutoff_ms,
        symbol_filters=symbol_filters,
        risk_config=risk_config,
    )

    # Modify future candles completely (indices test_idx+1 onward)
    modified_future = list(candles[: test_idx + 1])
    for fc in candles[test_idx + 1 :]:
        modified_future.append(
            Candle(
                venue=fc.venue,
                symbol=fc.symbol,
                timeframe=fc.timeframe,
                open_time_ms=fc.open_time_ms,
                close_time_ms=fc.close_time_ms,
                open=fc.open * 3.0,
                high=fc.high * 3.0,
                low=fc.low * 3.0,
                close=fc.close * 3.0,
                volume=fc.volume,
                quote_volume=fc.quote_volume,
                trades_count=fc.trades_count,
                taker_buy_base_volume=fc.taker_buy_base_volume,
                taker_buy_quote_volume=fc.taker_buy_quote_volume,
                observed_ingested_at_ms=None,
            )
        )

    plan_mod, dec_mod, reasons_mod = engine.create_candidate(
        candles=modified_future,
        decision_time_ms=test_cutoff_ms,
        available_cutoff_ms=test_cutoff_ms,
        symbol_filters=symbol_filters,
        risk_config=risk_config,
    )

    assert dec_base == dec_mod, "Decision changed when modifying future candles!"
    assert [r.value for r in reasons_base] == [r.value for r in reasons_mod], "Reasons changed when modifying future!"
    if plan_base is not None:
        assert plan_base.stop_price == plan_mod.stop_price
        assert plan_base.target_price == plan_mod.target_price

    print(f"\n[OK] Causal Invariance Verified: Altering future candles produces identical outcome ({dec_base.value}).")
    print("=== PHASE 01 SMOKE RUN VERIFIED ===")


if __name__ == "__main__":
    main()
