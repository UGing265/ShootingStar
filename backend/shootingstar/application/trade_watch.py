"""Application service orchestrating trade watch lifecycle, barrier monitoring, and risk reservations.

STRICT INVARIANTS:
1. Max 30-minute position holding horizon: holding_expires_at_ms = entry_time_ms + 1_800_000 ms.
2. Atomic reservation on (operator_id, symbol) held while OPEN or EXIT_REQUIRED and remaining_quantity > 0.
3. EXIT_REQUIRED still carries financial exposure: blocks new entry or conflicting watch until confirmed flat.
4. Immutable execution mode: PAPER positions can only be closed by PAPER outcomes; MANUAL positions require MANUAL operator exit.
5. Delayed manual entry reconciliation: past prices between entry and receipt are checked; retrospective SL breach immediately triggers EXIT_REQUIRED.
6. Partial exit tracking: remaining_quantity tracked using Decimal; reservation preserved until remaining_quantity reaches 0.
"""

from __future__ import annotations

import json
import uuid
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from shootingstar.adapters.binance_market_events import BinanceMarketEventsClient, PublicTradeEvent
from shootingstar.adapters.db.models import (
    CandidatePlanModel,
    TradeObservationModel,
    TradeWatchModel,
)
from shootingstar.adapters.db.repository import (
    CandidatePlanRepository,
    TradeObservationRepository,
    TradeWatchRepository,
)
from shootingstar.application.entry_strategy import EntryStrategyEngine
from shootingstar.domain.models import Candle
from shootingstar.domain.trade_plan import (
    CandidatePlan,
    CandidateState,
    DecisionReason,
    EntryObservation,
    ExecutionMode,
    ExitObservation,
    ExitReason,
    ObservationDecision,
    PositionLifecycleState,
    RiskConfig,
    SymbolFilters,
)


class TradeWatchServiceError(Exception):
    """Domain/lifecycle error in TradeWatchService."""
    pass


class ActiveReservationConflictError(TradeWatchServiceError):
    """Raised when an active exposure reservation prevents starting a watch or opening a trade."""
    pass


class ExecutionModeMismatchError(TradeWatchServiceError):
    """Raised when exit mode does not match entry mode."""
    pass


class TradeWatchService:
    """Orchestrates candidate discovery, position tracking, barriers, and manual/paper execution."""

    def __init__(
        self,
        watch_repo: TradeWatchRepository,
        candidate_repo: CandidatePlanRepository,
        observation_repo: TradeObservationRepository,
        strategy_engine: Optional[EntryStrategyEngine] = None,
    ):
        self.watch_repo = watch_repo
        self.candidate_repo = candidate_repo
        self.observation_repo = observation_repo
        self.engine = strategy_engine or EntryStrategyEngine()

    def start_watch(
        self,
        operator_id: str,
        symbol: str,
        risk_config: RiskConfig,
        symbol_filters: SymbolFilters,
        strategy_version: str = "v1-support-reclaim-30m",
        lease_owner: Optional[str] = None,
        lease_token: Optional[str] = None,
        lease_ttl_ms: int = 60_000,
        current_time_ms: int = 0,
    ) -> TradeWatchModel:
        """Starts a new watch, verifying no active reservation exists on (operator_id, symbol)."""
        # Guard: Check active reservation
        active = self.watch_repo.find_active_reservation(operator_id, symbol)
        if active is not None:
            raise ActiveReservationConflictError(
                f"Operator {operator_id} already has active exposure on {symbol} in state {active.position_state} (watch {active.id})."
            )

        watch_id = f"watch_{uuid.uuid4().hex[:16]}"
        risk_json = json.dumps({
            "max_notional_usdt": str(risk_config.max_notional_usdt),
            "max_planned_loss_usdt": str(risk_config.max_planned_loss_usdt),
            "fee_rate_bps": str(risk_config.fee_rate_bps),
            "slippage_bps": str(risk_config.slippage_bps),
            "max_wait_duration_ms": risk_config.max_wait_duration_ms,
            "max_entry_deviation_pct": str(risk_config.max_entry_deviation_pct),
            "freshness_tolerance_ms": risk_config.freshness_tolerance_ms,
            "max_event_lag_ms": risk_config.max_event_lag_ms,
            "cost_model_source": risk_config.cost_model_source,
        })
        filters_json = json.dumps({
            "symbol": symbol_filters.symbol,
            "tick_size": str(symbol_filters.tick_size),
            "step_size": str(symbol_filters.step_size),
            "min_notional": str(symbol_filters.min_notional),
            "min_qty": str(symbol_filters.min_qty),
        })

        watch = TradeWatchModel(
            id=watch_id,
            operator_id=operator_id,
            symbol=symbol,
            status="WATCHING",
            position_state="FLAT",
            strategy_version=strategy_version,
            risk_config_json=risk_json,
            symbol_filters_json=filters_json,
            lease_owner=lease_owner,
            lease_token=lease_token,
            lease_expires_at_ms=(current_time_ms + lease_ttl_ms) if lease_owner else None,
        )
        return self.watch_repo.save(watch)

    def stop_watch(self, watch_id: str) -> TradeWatchModel:
        """Stops candidate discovery. If in OPEN or EXIT_REQUIRED, monitoring continues until flat."""
        watch = self.watch_repo.get_by_id(watch_id)
        if not watch:
            raise TradeWatchServiceError(f"Watch {watch_id} not found.")

        watch.status = "STOPPED"
        self.watch_repo.save(watch)
        return watch

    def record_entry(
        self,
        watch_id: str,
        candidate_id: str,
        mode: ExecutionMode,
        price: Decimal,
        quantity: Decimal,
        actual_entry_time_ms: int,
        receipt_time_ms: int,
        idempotency_key: str,
        recent_lowest_price_since_entry: Optional[Decimal] = None,
        notes: Optional[str] = None,
    ) -> Tuple[TradeWatchModel, TradeObservationModel]:
        """Records position entry, locks immutable mode, sets 30m horizon deadline, and verifies deviation."""
        watch = self.watch_repo.get_by_id(watch_id)
        if not watch:
            raise TradeWatchServiceError(f"Watch {watch_id} not found.")

        # Idempotency check
        existing_obs = self.observation_repo.get_by_idempotency_key(idempotency_key)
        if existing_obs is not None:
            return watch, existing_obs

        # Active exposure check: cannot enter if already OPEN or EXIT_REQUIRED
        if watch.position_state in ("OPEN", "EXIT_REQUIRED"):
            raise ActiveReservationConflictError(
                f"Watch {watch_id} already has an active position in state {watch.position_state}."
            )

        cand_model = self.candidate_repo.get_by_id(candidate_id)
        if not cand_model:
            raise TradeWatchServiceError(f"Candidate {candidate_id} not found.")

        stop_price = Decimal(str(cand_model.stop_price))
        entry_zone_data = json.loads(cand_model.entry_zone_json)
        proposed_entry = Decimal(str(entry_zone_data["proposed_entry"]))
        risk_data = json.loads(watch.risk_config_json)
        max_deviation = Decimal(str(risk_data["max_entry_deviation_pct"]))
        fee_rate_bps = Decimal(str(risk_data["fee_rate_bps"]))
        max_notional = Decimal(str(risk_data["max_notional_usdt"]))

        # Check deviation and risk breach
        deviation = abs(price - proposed_entry) / proposed_entry
        is_off_plan = deviation > max_deviation
        is_risk_breach = (price * quantity) > max_notional

        # Delayed entry reconciliation: past low breached SL before receipt
        reconciled_sl_breach = False
        if recent_lowest_price_since_entry is not None and recent_lowest_price_since_entry <= stop_price:
            reconciled_sl_breach = True
            is_risk_breach = True

        fees_paid = (price * quantity * (fee_rate_bps / Decimal("10000")))

        obs_id = f"obs_entry_{uuid.uuid4().hex[:16]}"
        obs = TradeObservationModel(
            id=obs_id,
            idempotency_key=idempotency_key,
            candidate_id=candidate_id,
            watch_id=watch_id,
            observation_type="ENTRY",
            mode=mode.value,
            price=price,
            quantity=quantity,
            remaining_quantity=quantity,
            fees_paid=fees_paid,
            actual_time_ms=actual_entry_time_ms,
            receipt_time_ms=receipt_time_ms,
            is_off_plan=is_off_plan,
            is_risk_breach=is_risk_breach,
            reconciled_sl_breach=reconciled_sl_breach,
            notes=notes,
        )
        saved_obs = self.observation_repo.save(obs)

        # Update watch state
        watch.active_candidate_id = candidate_id
        watch.execution_mode = mode.value
        watch.opened_at_ms = actual_entry_time_ms
        # 30-minute horizon: exactly entry_time + 1_800_000 ms
        watch.deadline_ms = actual_entry_time_ms + 1_800_000

        # If retroactive SL breach detected during delayed entry receipt, go straight to EXIT_REQUIRED
        if reconciled_sl_breach:
            watch.position_state = "EXIT_REQUIRED"
        else:
            watch.position_state = "OPEN"

        self.watch_repo.save(watch)
        return watch, saved_obs

    def record_exit(
        self,
        watch_id: str,
        candidate_id: str,
        mode: ExecutionMode,
        price: Decimal,
        quantity: Decimal,
        exit_reason: ExitReason,
        actual_exit_time_ms: int,
        receipt_time_ms: int,
        idempotency_key: str,
        notes: Optional[str] = None,
    ) -> Tuple[TradeWatchModel, TradeObservationModel]:
        """Records partial or full position exit with strict execution mode matching."""
        watch = self.watch_repo.get_by_id(watch_id)
        if not watch:
            raise TradeWatchServiceError(f"Watch {watch_id} not found.")

        existing_obs = self.observation_repo.get_by_idempotency_key(idempotency_key)
        if existing_obs is not None:
            return watch, existing_obs

        if watch.position_state not in ("OPEN", "EXIT_REQUIRED"):
            raise TradeWatchServiceError(f"Cannot exit watch {watch_id} in state {watch.position_state}.")

        # Invariant 4: Immutable execution mode
        if watch.execution_mode != mode.value:
            raise ExecutionModeMismatchError(
                f"Position execution mode is {watch.execution_mode}, cannot be closed by {mode.value} exit."
            )

        # Calculate current remaining quantity across all prior observations
        prior_observations = self.observation_repo.list_by_candidate_id(candidate_id)
        entry_obs = next((o for o in prior_observations if o.observation_type == "ENTRY"), None)
        if not entry_obs:
            raise TradeWatchServiceError(f"No entry observation found for candidate {candidate_id}.")

        entry_qty = Decimal(str(entry_obs.quantity))
        entry_price = Decimal(str(entry_obs.price))
        total_exited_so_far = sum(
            Decimal(str(o.quantity)) for o in prior_observations if o.observation_type == "EXIT"
        )
        current_remaining = entry_qty - total_exited_so_far

        if quantity > current_remaining:
            raise TradeWatchServiceError(
                f"Exit quantity {quantity} exceeds remaining position quantity {current_remaining}."
            )

        new_remaining = current_remaining - quantity
        risk_data = json.loads(watch.risk_config_json)
        fee_rate_bps = Decimal(str(risk_data["fee_rate_bps"]))
        fees_paid = price * quantity * (fee_rate_bps / Decimal("10000"))

        # PnL on exited portion
        gross_pnl = (price - entry_price) * quantity
        net_pnl = gross_pnl - fees_paid - (entry_price * quantity * (fee_rate_bps / Decimal("10000")))

        obs_id = f"obs_exit_{uuid.uuid4().hex[:16]}"
        obs = TradeObservationModel(
            id=obs_id,
            idempotency_key=idempotency_key,
            candidate_id=candidate_id,
            watch_id=watch_id,
            observation_type="EXIT",
            mode=mode.value,
            price=price,
            quantity=quantity,
            remaining_quantity=new_remaining,
            fees_paid=fees_paid,
            actual_time_ms=actual_exit_time_ms,
            receipt_time_ms=receipt_time_ms,
            exit_reason=exit_reason.value,
            realized_pnl_usdt=net_pnl,
            notes=notes,
        )
        saved_obs = self.observation_repo.save(obs)

        # Partial vs Final exit:
        if new_remaining == Decimal("0"):
            watch.position_state = "CLOSED"
            watch.closed_at_ms = actual_exit_time_ms
        else:
            # Partial exit preserves reservation and exposure
            watch.position_state = "OPEN"

        self.watch_repo.save(watch)
        return watch, saved_obs

    def process_ordered_trades(
        self,
        watch_id: str,
        trades: List[PublicTradeEvent],
    ) -> Optional[Tuple[ExitReason, int, Decimal]]:
        """Monitors active open position using strictly ordered trade events.

        INVARIANTS:
        1. Trades must be evaluated in chronological sequence (event_time_ms, trade_id).
        2. If a trade occurs at or after deadline_ms, it triggers TIMEOUT exit instruction at deadline boundary.
        3. Trades after deadline_ms are never attributed as TP or SL hits.
        """
        watch = self.watch_repo.get_by_id(watch_id)
        if not watch or watch.position_state != "OPEN":
            return None

        if not watch.active_candidate_id:
            return None

        cand_model = self.candidate_repo.get_by_id(watch.active_candidate_id)
        if not cand_model:
            return None

        stop_price = Decimal(str(cand_model.stop_price))
        target_price = Decimal(str(cand_model.target_price))
        deadline_ms = watch.deadline_ms

        # Ensure chronological ordering
        sorted_trades = sorted(trades, key=lambda t: (t.event_time_ms, t.trade_id))

        for t in sorted_trades:
            # 1. Event strictly AFTER deadline boundary: triggers timeout, barrier touch ignored
            if deadline_ms is not None and t.event_time_ms > deadline_ms:
                watch.position_state = "EXIT_REQUIRED"
                self.watch_repo.save(watch)
                return (ExitReason.TIMEOUT, deadline_ms, t.price)

            # 2. Event is <= deadline_ms (inclusive of deadline): barriers evaluated first!
            if t.price <= stop_price:
                watch.position_state = "EXIT_REQUIRED"
                self.watch_repo.save(watch)
                return (ExitReason.SL_HIT, t.event_time_ms, t.price)

            if t.price >= target_price:
                watch.position_state = "EXIT_REQUIRED"
                self.watch_repo.save(watch)
                return (ExitReason.TP_HIT, t.event_time_ms, t.price)

            # 3. Exact deadline match with no barrier touch -> timeout instruction
            if deadline_ms is not None and t.event_time_ms == deadline_ms:
                watch.position_state = "EXIT_REQUIRED"
                self.watch_repo.save(watch)
                return (ExitReason.TIMEOUT, deadline_ms, t.price)

        return None

    def process_ohlc_candle(
        self,
        watch_id: str,
        candle: Candle,
    ) -> Tuple[Optional[ExitReason], Optional[str]]:
        """Replays historical 1m/5m candle with strict ambiguity detection.

        INVARIANTS:
        1. Same-bar TP and SL touch is strictly AMBIGUOUS (no arbitrary SL-first or TP-first).
        2. If candle straddles or exceeds deadline, deadline takes precedence.
        """
        watch = self.watch_repo.get_by_id(watch_id)
        if not watch or watch.position_state != "OPEN":
            return None, None

        if not watch.active_candidate_id:
            return None, None

        cand_model = self.candidate_repo.get_by_id(watch.active_candidate_id)
        if not cand_model:
            return None, None

        stop_price = Decimal(str(cand_model.stop_price))
        target_price = Decimal(str(cand_model.target_price))
        deadline_ms = watch.deadline_ms

        # Candle starts at or after deadline
        if deadline_ms is not None and candle.open_time_ms >= deadline_ms:
            watch.position_state = "EXIT_REQUIRED"
            self.watch_repo.save(watch)
            return ExitReason.TIMEOUT, None

        c_low = Decimal(str(candle.low))
        c_high = Decimal(str(candle.high))

        touches_sl = c_low <= stop_price
        touches_tp = c_high >= target_price

        # Invariant: Both touched in same bar without trade sequence -> AMBIGUOUS
        # Position MUST NOT remain OPEN: transition to EXIT_REQUIRED with ambiguous flag
        if touches_sl and touches_tp:
            watch.position_state = "EXIT_REQUIRED"
            self.watch_repo.save(watch)
            return None, "AMBIGUOUS"

        # Single barrier touches before deadline
        if touches_sl:
            if deadline_ms is not None and candle.close_time_ms > deadline_ms:
                watch.position_state = "EXIT_REQUIRED"
                self.watch_repo.save(watch)
                return None, "AMBIGUOUS_DEADLINE_STRADDLE"
            watch.position_state = "EXIT_REQUIRED"
            self.watch_repo.save(watch)
            return ExitReason.SL_HIT, None

        if touches_tp:
            if deadline_ms is not None and candle.close_time_ms > deadline_ms:
                watch.position_state = "EXIT_REQUIRED"
                self.watch_repo.save(watch)
                return None, "AMBIGUOUS_DEADLINE_STRADDLE"
            watch.position_state = "EXIT_REQUIRED"
            self.watch_repo.save(watch)
            return ExitReason.TP_HIT, None
        # If no barrier hit and candle closed past deadline -> TIMEOUT
        if deadline_ms is not None and candle.close_time_ms >= deadline_ms:
            watch.position_state = "EXIT_REQUIRED"
            self.watch_repo.save(watch)
            return ExitReason.TIMEOUT, None

        return None, None


def run_watch_worker(
    watch_id: str,
    session_factory,
    symbol: str = "BTCUSDT",
    once: bool = False,
    poll_interval_s: float = 3.0,
    worker_id: Optional[str] = None,
    lease_token: Optional[str] = None,
) -> int:
    """Durable worker loop managing candidate discovery and position monitoring.

    INVARIANTS:
    1. Runs until operator stop (or single cycle if once=True).
    2. Atomic CAS lease check prevents split-brain worker execution.
    3. Position monitoring runs on ordered trade events; stops cannot abandon OPEN or EXIT_REQUIRED positions.
    """
    import logging
    import time
    from shootingstar.adapters.binance import BinanceSpotClient

    logger = logging.getLogger("shootingstar.watch_worker")
    w_id = worker_id or f"worker_{uuid.uuid4().hex[:8]}"
    l_token = lease_token or f"token_{uuid.uuid4().hex[:8]}"
    events_client = BinanceMarketEventsClient()
    spot_client = BinanceSpotClient()
    engine = EntryStrategyEngine()

    logger.info("Worker %s started for watch %s on %s (once=%s)", w_id, watch_id, symbol, once)

    try:
        while True:
            now_ms = int(time.time() * 1000)
            with session_factory() as session:
                watch_repo = TradeWatchRepository(session)
                cand_repo = CandidatePlanRepository(session)
                obs_repo = TradeObservationRepository(session)
                service = TradeWatchService(watch_repo, cand_repo, obs_repo, engine)

                # 1. Atomic lease renewal
                acquired = watch_repo.acquire_or_renew_lease(
                    watch_id=watch_id,
                    worker_id=w_id,
                    lease_token=l_token,
                    lease_ttl_ms=30_000,
                    current_time_ms=now_ms,
                )
                if not acquired:
                    logger.critical("Failed to acquire/renew lease for watch %s. Halting worker.", watch_id)
                    return 1

                watch = watch_repo.get_by_id(watch_id)
                if not watch:
                    logger.error("Watch %s not found in database.", watch_id)
                    return 1

                if watch.status == "STOPPED" and watch.position_state in ("FLAT", "CLOSED"):
                    logger.info("Watch %s marked STOPPED by operator and position is %s. Exiting worker loop.", watch_id, watch.position_state)
                    break

                # 2. Position Monitoring when OPEN or EXIT_REQUIRED
                if watch.position_state == "OPEN":
                    trades = []
                    try:
                        trades = events_client.fetch_recent_trades(symbol=symbol, limit=50)
                    except Exception as exc:
                        logger.warning("Failed to fetch recent trades during monitoring: %s", exc)

                    exit_event = service.process_ordered_trades(watch_id, trades)
                    if exit_event is not None:
                        reason, event_t, p = exit_event
                        logger.warning(
                            "EXIT INSTRUCTION TRIGGERED: reason=%s at time=%s price=%s! Operator action required.",
                            reason.value, event_t, p
                        )
                    elif watch.deadline_ms is not None and now_ms >= watch.deadline_ms:
                        watch.position_state = "EXIT_REQUIRED"
                        watch_repo.save(watch)
                        logger.warning(
                            "EXIT INSTRUCTION TRIGGERED: TIMEOUT by clock at deadline=%s! Disconnect/no trades. Operator action required.",
                            watch.deadline_ms
                        )

                elif watch.position_state == "EXIT_REQUIRED":
                    overdue_ms = now_ms - (watch.deadline_ms or now_ms)
                    logger.warning(
                        "OVERDUE EXPOSURE: watch %s is in EXIT_REQUIRED state (past deadline by %s ms). "
                        "Active exposure preserved. Waiting for operator to record exit.",
                        watch_id, overdue_ms
                    )

                # 3. Setup Discovery ONLY when FLAT and WATCHING
                elif watch.position_state == "FLAT" and watch.status == "WATCHING":
                    risk_data = json.loads(watch.risk_config_json)
                    risk_config = RiskConfig(
                        max_notional_usdt=Decimal(str(risk_data["max_notional_usdt"])),
                        max_planned_loss_usdt=Decimal(str(risk_data["max_planned_loss_usdt"])),
                        fee_rate_bps=Decimal(str(risk_data["fee_rate_bps"])),
                        slippage_bps=Decimal(str(risk_data["slippage_bps"])),
                        max_wait_duration_ms=int(risk_data["max_wait_duration_ms"]),
                        max_entry_deviation_pct=Decimal(str(risk_data["max_entry_deviation_pct"])),
                        freshness_tolerance_ms=int(risk_data["freshness_tolerance_ms"]),
                        max_event_lag_ms=int(risk_data["max_event_lag_ms"]),
                        cost_model_source=str(risk_data["cost_model_source"]),
                    )
                    filter_data = json.loads(watch.symbol_filters_json)
                    symbol_filters = SymbolFilters(
                        symbol=filter_data["symbol"],
                        tick_size=Decimal(str(filter_data["tick_size"])),
                        step_size=Decimal(str(filter_data["step_size"])),
                        min_notional=Decimal(str(filter_data["min_notional"])),
                        min_qty=Decimal(str(filter_data["min_qty"])),
                    )

                    # Fetch klines
                    start_kline_ms = now_ms - (120 * 60 * 1000)
                    rows = spot_client.fetch_klines(symbol=symbol, interval="1m", start_time_ms=start_kline_ms, limit=120)
                    candles = [spot_client.parse_kline_row(r, venue="BINANCE", symbol=symbol, timeframe="1m") for r in rows]

                    cutoff_ms = candles[-1].close_time_ms + 1000

                    if watch.active_candidate_id:
                        cand_model = cand_repo.get_by_id(watch.active_candidate_id)
                        if cand_model:
                            # Advance candidate
                            entry_zone_dict = json.loads(cand_model.entry_zone_json)
                            from shootingstar.domain.trade_plan import EntryZone, ConfirmationRule, InvalidationRule
                            locked_plan = CandidatePlan(
                                candidate_id=cand_model.id,
                                strategy_version=cand_model.strategy_version,
                                rule_config_hash=cand_model.rule_config_hash,
                                decision_time_ms=cand_model.decision_time_ms,
                                available_cutoff_ms=cand_model.available_cutoff_ms,
                                entry_zone=EntryZone(
                                    min_price=Decimal(str(entry_zone_dict["min_price"])),
                                    max_price=Decimal(str(entry_zone_dict["max_price"])),
                                    proposed_entry=Decimal(str(entry_zone_dict["proposed_entry"])),
                                ),
                                confirmation=ConfirmationRule(
                                    support_level=Decimal(str(json.loads(cand_model.confirmation_json)["support_level"])),
                                    reclaim_level=Decimal(str(json.loads(cand_model.confirmation_json)["reclaim_level"])),
                                ),
                                invalidation=InvalidationRule(
                                    invalidation_price=Decimal(str(json.loads(cand_model.invalidation_json)["invalidation_price"])),
                                    buffer_percent=Decimal(str(json.loads(cand_model.invalidation_json)["buffer_percent"])),
                                ),
                                stop_price=Decimal(str(cand_model.stop_price)),
                                target_price=Decimal(str(cand_model.target_price)),
                                risk_config=risk_config,
                                symbol_filters=symbol_filters,
                                wait_expires_at_ms=cand_model.wait_expires_at_ms,
                                horizon_ms=cand_model.horizon_ms,
                            )
                            adv_plan, adv_decision, adv_reasons = engine.advance_candidate(
                                locked_plan=locked_plan,
                                new_candles=[candles[-1]],
                                current_time_ms=now_ms,
                            )
                            cand_model.candidate_state = adv_plan.candidate_state.value
                            cand_model.reasons_json = json.dumps([r.value for r in adv_reasons])
                            cand_repo.save(cand_model)
                            if adv_plan.candidate_state in (CandidateState.INVALIDATED, CandidateState.EXPIRED):
                                watch.active_candidate_id = None
                                watch_repo.save(watch)
                    else:
                        plan, decision, reasons = engine.create_candidate(
                            candles=candles,
                            decision_time_ms=cutoff_ms,
                            available_cutoff_ms=cutoff_ms,
                            symbol_filters=symbol_filters,
                            risk_config=risk_config,
                        )
                        if plan:
                            cand_model = CandidatePlanModel(
                                id=plan.candidate_id,
                                watch_id=watch.id,
                                strategy_version=plan.strategy_version,
                                rule_config_hash=plan.rule_config_hash,
                                decision_time_ms=plan.decision_time_ms,
                                available_cutoff_ms=plan.available_cutoff_ms,
                                entry_zone_json=json.dumps({
                                    "min_price": str(plan.entry_zone.min_price),
                                    "max_price": str(plan.entry_zone.max_price),
                                    "proposed_entry": str(plan.entry_zone.proposed_entry),
                                }),
                                confirmation_json=json.dumps({
                                    "support_level": str(plan.confirmation.support_level),
                                    "reclaim_level": str(plan.confirmation.reclaim_level),
                                }),
                                invalidation_json=json.dumps({
                                    "invalidation_price": str(plan.invalidation.invalidation_price),
                                    "buffer_percent": str(plan.invalidation.buffer_percent),
                                }),
                                stop_price=plan.stop_price,
                                target_price=plan.target_price,
                                wait_expires_at_ms=plan.wait_expires_at_ms,
                                horizon_ms=plan.horizon_ms,
                                reasons_json=json.dumps([r.value for r in reasons]),
                                candidate_state=plan.candidate_state.value,
                            )
                            cand_repo.save(cand_model)
                            watch.active_candidate_id = plan.candidate_id
                            watch_repo.save(watch)
                            logger.info("New candidate plan %s created: Stop=%s Entry=%s Target=%s", plan.candidate_id, plan.stop_price, plan.proposed_entry, plan.target_price)

                session.commit()

            if once:
                break
            time.sleep(poll_interval_s)

    except KeyboardInterrupt:
        logger.info("Operator interrupt received.")
        with session_factory() as session:
            watch_repo = TradeWatchRepository(session)
            watch = watch_repo.get_by_id(watch_id)
            if watch:
                if watch.position_state in ("FLAT", "CLOSED"):
                    watch.status = "STOPPED"
                    watch_repo.save(watch)
                    session.commit()
                    logger.info("Watch %s safely marked STOPPED (position=%s).", watch_id, watch.position_state)
                else:
                    logger.warning(
                        "ACTIVE POSITION IN STATE %s! Watch NOT stopped. Deadline %s preserved.",
                        watch.position_state, watch.deadline_ms
                    )
    return 0
