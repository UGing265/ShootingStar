"""Deterministic entry barrier strategy engine and risk evaluation.

STRICT INVARIANTS:
1. Long-only Binance Spot BTCUSDT: stop_price < proposed_entry < target_price.
2. Single support-bounce/reclaim setup: extrema computed on causal lookback window strictly before confirmation.
3. No future leakage: candles available_at <= available_cutoff_ms with receipt latency check.
4. Separate create vs advance: create locks barriers and wait_expires_at_ms; advance evaluates locked plan against new incoming candles without moving barriers or drifting deadlines.
5. Precedence: Invalidation/expiry strictly beats confirmation. If low breaches stop_price, candidate is INVALIDATED even if close reclaims.
6. Confirmation: low touched support zone AND close reclaimed >= locked_plan.confirmation.reclaim_level.
7. Symbol filters (tickSize, stepSize, minNotional, minQty) provided from exchangeInfo, not hardcoded.
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP, ROUND_CEILING
from typing import Any, Dict, List, Optional, Tuple

from shootingstar.domain.models import Candle, Timeframe
from shootingstar.domain.trade_plan import (
    BarrierProbability,
    CandidatePlan,
    CandidateState,
    ConfirmationRule,
    DecisionReason,
    EntryObservation,
    EntryZone,
    ExecutionMode,
    InvalidationRule,
    ObservationDecision,
    PayoffExpectancyModel,
    RiskConfig,
    SymbolFilters,
)


def compute_rule_config_hash(params: Dict[str, Any]) -> str:
    canonical_json = json.dumps(params, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()[:16]


def is_candle_causally_available(candle: Candle, cutoff_ms: int, assumed_latency_ms: int = 1000) -> bool:
    """Checks that candle was completed and available at or before cutoff_ms."""
    if candle.close_time_ms > cutoff_ms:
        return False
    if candle.observed_ingested_at_ms is not None:
        return candle.observed_ingested_at_ms <= cutoff_ms
    return (candle.close_time_ms + assumed_latency_ms) <= cutoff_ms


class EntryStrategyEngine:
    """Pure deterministic barrier generator and risk gating engine."""

    def __init__(
        self,
        strategy_version: str = "v1-support-reclaim-30m",
        lookback_bars: int = 60,
        support_tolerance_pct: Decimal = Decimal("0.0015"),  # 0.15% zone around support
        sl_buffer_pct: Decimal = Decimal("0.002"),           # 0.20% buffer below support for SL
        reclaim_buffer_pct: Decimal = Decimal("0.001"),      # 0.10% buffer above support for reclaim
        min_reward_risk_ratio: Decimal = Decimal("1.2"),     # Min (TP - Entry) / (Entry - SL)
        assumed_latency_ms: int = 1000,
    ):
        self.strategy_version = strategy_version
        self.lookback_bars = lookback_bars
        self.support_tolerance_pct = support_tolerance_pct
        self.sl_buffer_pct = sl_buffer_pct
        self.reclaim_buffer_pct = reclaim_buffer_pct
        self.min_reward_risk_ratio = min_reward_risk_ratio
        self.assumed_latency_ms = assumed_latency_ms
        self._config_params = {
            "strategy_version": self.strategy_version,
            "lookback_bars": self.lookback_bars,
            "support_tolerance_pct": str(self.support_tolerance_pct),
            "sl_buffer_pct": str(self.sl_buffer_pct),
            "reclaim_buffer_pct": str(self.reclaim_buffer_pct),
            "min_reward_risk_ratio": str(self.min_reward_risk_ratio),
            "assumed_latency_ms": self.assumed_latency_ms,
        }
        self.rule_config_hash = compute_rule_config_hash(self._config_params)

    def create_candidate(
        self,
        candles: List[Candle],
        decision_time_ms: int,
        available_cutoff_ms: int,
        symbol_filters: SymbolFilters,
        risk_config: Optional[RiskConfig] = None,
        candidate_id: Optional[str] = None,
    ) -> Tuple[Optional[CandidatePlan], ObservationDecision, List[DecisionReason]]:
        """Identifies setup and locks barriers, entry zone, and wait deadline immutably."""
        reasons: List[DecisionReason] = []

        causal_candles = [
            c for c in candles
            if is_candle_causally_available(c, available_cutoff_ms, self.assumed_latency_ms)
        ]
        causal_candles.sort(key=lambda c: c.open_time_ms)

        if len(causal_candles) < self.lookback_bars:
            reasons.append(DecisionReason.INSUFFICIENT_HISTORY)
            return None, ObservationDecision.SKIP, reasons

        if risk_config is None:
            reasons.append(DecisionReason.CONFIG_REQUIRED)
            return None, ObservationDecision.SKIP, reasons

        eval_window = causal_candles[-self.lookback_bars:]
        latest_candle = eval_window[-1]

        # Calculate local swing support (excluding latest candle)
        prior_window = eval_window[:-1]
        support_low = min(c.low for c in prior_window)
        support_price = symbol_filters.quantize_price(Decimal(str(support_low)), rounding=ROUND_FLOOR)

        # Calculate swing resistance
        current_close = symbol_filters.quantize_price(Decimal(str(latest_candle.close)))
        higher_highs = [c.high for c in eval_window if c.high > float(current_close) * 1.002]

        if not higher_highs:
            reasons.append(DecisionReason.NO_TARGET)
            return None, ObservationDecision.SKIP, reasons

        resistance_high = max(higher_highs)
        target_price = symbol_filters.quantize_price(Decimal(str(resistance_high)), rounding=ROUND_CEILING)

        # Stop loss below support
        stop_price = symbol_filters.quantize_price(
            support_price * (Decimal("1") - self.sl_buffer_pct),
            rounding=ROUND_FLOOR,
        )
        if stop_price >= current_close:
            reasons.append(DecisionReason.TICK_COLLAPSE)
            return None, ObservationDecision.SKIP, reasons

        proposed_entry = current_close

        # Check reward/risk ratio
        reward = target_price - proposed_entry
        risk = proposed_entry - stop_price
        if risk <= Decimal("0") or (reward / risk) < self.min_reward_risk_ratio:
            reasons.append(DecisionReason.NO_TARGET)
            return None, ObservationDecision.SKIP, reasons

        min_entry = symbol_filters.quantize_price(
            support_price * (Decimal("1") - self.support_tolerance_pct),
            rounding=ROUND_FLOOR,
        )
        max_entry = symbol_filters.quantize_price(
            proposed_entry * (Decimal("1") + self.support_tolerance_pct),
            rounding=ROUND_CEILING,
        )
        if min_entry > proposed_entry:
            min_entry = proposed_entry
        if max_entry < proposed_entry:
            max_entry = proposed_entry

        entry_zone = EntryZone(
            min_price=min_entry,
            max_price=max_entry,
            proposed_entry=proposed_entry,
        )

        reclaim_level = symbol_filters.quantize_price(
            support_price * (Decimal("1") + self.reclaim_buffer_pct),
            rounding=ROUND_CEILING,
        )
        confirmation = ConfirmationRule(
            support_level=support_price,
            reclaim_level=reclaim_level,
        )
        invalidation = InvalidationRule(
            invalidation_price=stop_price,
            buffer_percent=self.sl_buffer_pct,
        )

        wait_expires_at_ms = decision_time_ms + risk_config.max_wait_duration_ms
        cid = candidate_id or f"cand_{decision_time_ms}_{int(support_price)}"
        evidence_ids = tuple(c.close_time_ms for c in eval_window[-5:])

        plan = CandidatePlan(
            candidate_id=cid,
            strategy_version=self.strategy_version,
            rule_config_hash=self.rule_config_hash,
            decision_time_ms=decision_time_ms,
            available_cutoff_ms=available_cutoff_ms,
            entry_zone=entry_zone,
            confirmation=confirmation,
            invalidation=invalidation,
            stop_price=stop_price,
            target_price=target_price,
            risk_config=risk_config,
            symbol_filters=symbol_filters,
            wait_expires_at_ms=wait_expires_at_ms,
            evidence_candle_ids=evidence_ids,
            candidate_state=CandidateState.WAITING,
        )
        reasons.append(DecisionReason.CONFIRMATION_PENDING)
        return plan, ObservationDecision.WAIT_CONFIRMATION, reasons

    def advance_candidate(
        self,
        locked_plan: CandidatePlan,
        new_candles: List[Candle],
        current_time_ms: int,
        probability: Optional[BarrierProbability] = None,
        payoff_model: Optional[PayoffExpectancyModel] = None,
        cost_model_approved: bool = False,
    ) -> Tuple[CandidatePlan, ObservationDecision, List[DecisionReason]]:
        """Evaluates incoming candles strictly against locked plan barriers and deadline."""
        reasons: List[DecisionReason] = []

        # 1. Check expiration
        if current_time_ms >= locked_plan.wait_expires_at_ms:
            reasons.append(DecisionReason.EXPIRED)
            expired_plan = CandidatePlan(
                candidate_id=locked_plan.candidate_id,
                strategy_version=locked_plan.strategy_version,
                rule_config_hash=locked_plan.rule_config_hash,
                decision_time_ms=locked_plan.decision_time_ms,
                available_cutoff_ms=locked_plan.available_cutoff_ms,
                entry_zone=locked_plan.entry_zone,
                confirmation=locked_plan.confirmation,
                invalidation=locked_plan.invalidation,
                stop_price=locked_plan.stop_price,
                target_price=locked_plan.target_price,
                risk_config=locked_plan.risk_config,
                symbol_filters=locked_plan.symbol_filters,
                wait_expires_at_ms=locked_plan.wait_expires_at_ms,
                evidence_candle_ids=locked_plan.evidence_candle_ids,
                probability=probability or locked_plan.probability,
                cost_model_version=payoff_model.model_version if payoff_model else locked_plan.cost_model_version,
                reasons=tuple(reasons),
                candidate_state=CandidateState.EXPIRED,
            )
            return expired_plan, ObservationDecision.SKIP, reasons

        # Filter causally available new candles
        available_new = [
            c for c in new_candles
            if is_candle_causally_available(c, current_time_ms, self.assumed_latency_ms)
        ]
        available_new.sort(key=lambda c: c.open_time_ms)

        if not available_new:
            reasons.append(DecisionReason.CONFIRMATION_PENDING)
            return locked_plan, ObservationDecision.WAIT_CONFIRMATION, reasons

        # 2. Check invalidation on all new candles (Precedence over confirmation)
        for c in available_new:
            c_low = Decimal(str(c.low))
            if c_low <= locked_plan.stop_price:
                reasons.append(DecisionReason.INVALIDATED)
                invalidated_plan = CandidatePlan(
                    candidate_id=locked_plan.candidate_id,
                    strategy_version=locked_plan.strategy_version,
                    rule_config_hash=locked_plan.rule_config_hash,
                    decision_time_ms=locked_plan.decision_time_ms,
                    available_cutoff_ms=locked_plan.available_cutoff_ms,
                    entry_zone=locked_plan.entry_zone,
                    confirmation=locked_plan.confirmation,
                    invalidation=locked_plan.invalidation,
                    stop_price=locked_plan.stop_price,
                    target_price=locked_plan.target_price,
                    risk_config=locked_plan.risk_config,
                    symbol_filters=locked_plan.symbol_filters,
                    wait_expires_at_ms=locked_plan.wait_expires_at_ms,
                    evidence_candle_ids=locked_plan.evidence_candle_ids,
                    probability=probability or locked_plan.probability,
                    cost_model_version=payoff_model.model_version if payoff_model else locked_plan.cost_model_version,
                    reasons=tuple(reasons),
                    candidate_state=CandidateState.INVALIDATED,
                )
                return invalidated_plan, ObservationDecision.SKIP, reasons

        # 3. Check confirmation on latest candle
        latest_candle = available_new[-1]
        latest_low = Decimal(str(latest_candle.low))
        latest_close = Decimal(str(latest_candle.close))

        support_zone_max = locked_plan.confirmation.support_level * (Decimal("1") + self.support_tolerance_pct)
        touched_support = latest_low <= support_zone_max
        reclaimed_above = latest_close >= locked_plan.confirmation.reclaim_level
        is_confirmed = touched_support and reclaimed_above

        if not is_confirmed:
            reasons.append(DecisionReason.CONFIRMATION_PENDING)
            return locked_plan, ObservationDecision.WAIT_CONFIRMATION, reasons

        # 4. Confirmed! Check risk and evidence gates
        planned_qty = locked_plan.compute_planned_quantity()
        if planned_qty <= Decimal("0"):
            reasons.append(DecisionReason.RISK_EXCEEDED)
            return locked_plan, ObservationDecision.SKIP, reasons

        planned_loss = locked_plan.compute_planned_loss_usdt(planned_qty)
        if planned_loss > locked_plan.risk_config.max_planned_loss_usdt:
            reasons.append(DecisionReason.RISK_EXCEEDED)
            return locked_plan, ObservationDecision.SKIP, reasons

        if not cost_model_approved or payoff_model is None or not payoff_model.is_approved:
            reasons.append(DecisionReason.COST_UNVERIFIED)

        if probability is None or not probability.is_valid():
            reasons.append(DecisionReason.PROBABILITY_UNVERIFIED)

        if DecisionReason.COST_UNVERIFIED in reasons or DecisionReason.PROBABILITY_UNVERIFIED in reasons:
            watch_plan = CandidatePlan(
                candidate_id=locked_plan.candidate_id,
                strategy_version=locked_plan.strategy_version,
                rule_config_hash=locked_plan.rule_config_hash,
                decision_time_ms=locked_plan.decision_time_ms,
                available_cutoff_ms=locked_plan.available_cutoff_ms,
                entry_zone=locked_plan.entry_zone,
                confirmation=locked_plan.confirmation,
                invalidation=locked_plan.invalidation,
                stop_price=locked_plan.stop_price,
                target_price=locked_plan.target_price,
                risk_config=locked_plan.risk_config,
                symbol_filters=locked_plan.symbol_filters,
                wait_expires_at_ms=locked_plan.wait_expires_at_ms,
                evidence_candle_ids=locked_plan.evidence_candle_ids,
                probability=probability,
                cost_model_version=payoff_model.model_version if payoff_model else None,
                reasons=tuple(reasons),
                candidate_state=CandidateState.WAITING,
            )
            return watch_plan, ObservationDecision.WATCH_ONLY, reasons

        effective_probability = probability or locked_plan.probability
        evaluated_plan = CandidatePlan(
            candidate_id=locked_plan.candidate_id,
            strategy_version=locked_plan.strategy_version,
            rule_config_hash=locked_plan.rule_config_hash,
            decision_time_ms=locked_plan.decision_time_ms,
            available_cutoff_ms=locked_plan.available_cutoff_ms,
            entry_zone=locked_plan.entry_zone,
            confirmation=locked_plan.confirmation,
            invalidation=locked_plan.invalidation,
            stop_price=locked_plan.stop_price,
            target_price=locked_plan.target_price,
            risk_config=locked_plan.risk_config,
            symbol_filters=locked_plan.symbol_filters,
            wait_expires_at_ms=locked_plan.wait_expires_at_ms,
            evidence_candle_ids=locked_plan.evidence_candle_ids,
            probability=effective_probability,
            cost_model_version=payoff_model.model_version if payoff_model else locked_plan.cost_model_version,
        )

        # Check net expectancy E[net] > 0
        net_edge = evaluated_plan.compute_net_expectancy(planned_qty, payoff_model)
        if net_edge is None or net_edge <= Decimal("0"):
            reasons.append(DecisionReason.RISK_EXCEEDED)
            return evaluated_plan, ObservationDecision.WATCH_ONLY, reasons
        # All gates passed: BUY_ELIGIBLE
        reasons.append(DecisionReason.SETUP_VALID)
        eligible_plan = CandidatePlan(
            candidate_id=locked_plan.candidate_id,
            strategy_version=locked_plan.strategy_version,
            rule_config_hash=locked_plan.rule_config_hash,
            decision_time_ms=locked_plan.decision_time_ms,
            available_cutoff_ms=locked_plan.available_cutoff_ms,
            entry_zone=locked_plan.entry_zone,
            confirmation=locked_plan.confirmation,
            invalidation=locked_plan.invalidation,
            stop_price=locked_plan.stop_price,
            target_price=locked_plan.target_price,
            risk_config=locked_plan.risk_config,
            symbol_filters=locked_plan.symbol_filters,
            wait_expires_at_ms=locked_plan.wait_expires_at_ms,
            evidence_candle_ids=locked_plan.evidence_candle_ids,
            probability=probability,
            cost_model_version=payoff_model.model_version,
            reasons=tuple(reasons),
            candidate_state=CandidateState.ELIGIBLE,
        )
        return eligible_plan, ObservationDecision.BUY_ELIGIBLE, reasons

    def validate_and_record_entry(
        self,
        plan: CandidatePlan,
        actual_price: Decimal,
        actual_quantity: Decimal,
        actual_entry_time_ms: int,
        receipt_time_ms: int,
        mode: ExecutionMode,
        recent_low_since_entry: Optional[Decimal] = None,
        notes: Optional[str] = None,
    ) -> EntryObservation:
        """Validates entry deviation, checks for retroactive SL breach, and records observation."""
        deviation = abs(actual_price - plan.proposed_entry) / plan.proposed_entry
        is_off_plan = False
        is_risk_breach = False

        if deviation > plan.risk_config.max_entry_deviation_pct:
            is_off_plan = True

        actual_notional = actual_price * actual_quantity
        if actual_notional > plan.risk_config.max_notional_usdt:
            is_risk_breach = True

        reconciled_sl_breach = False
        if recent_low_since_entry is not None and recent_low_since_entry <= plan.stop_price:
            reconciled_sl_breach = True
            is_risk_breach = True

        cost_rate = (plan.risk_config.fee_rate_bps) / Decimal("10000")
        estimated_fee = (actual_price * actual_quantity * cost_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        obs_id = f"entry_obs_{plan.candidate_id}_{actual_entry_time_ms}"
        return EntryObservation(
            observation_id=obs_id,
            candidate_id=plan.candidate_id,
            mode=mode,
            entry_price=actual_price,
            entry_quantity=actual_quantity,
            actual_entry_time_ms=actual_entry_time_ms,
            receipt_time_ms=receipt_time_ms,
            fees_paid_usdt=estimated_fee,
            is_off_plan=is_off_plan,
            is_risk_breach=is_risk_breach,
            reconciled_sl_breach_detected=reconciled_sl_breach,
            notes=notes,
        )
