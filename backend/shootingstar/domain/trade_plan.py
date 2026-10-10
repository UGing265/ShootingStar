"""Domain models and contracts for 30-minute fast-entry barriers, risk, and trade plan lifecycle.

STRICT INVARIANTS:
1. Long-only Binance BTCUSDT Spot: stop_price < proposed_entry < target_price.
2. Max 30-minute position horizon: 1,800,000 ms from entry confirmation.
3. Pure domain: no SQLAlchemy, FastAPI, or Binance SDK imports.
4. Decimal-first money and price math: exact multiple increment quantization ((value / inc).to_integral_value() * inc).
5. Quantity MUST use ROUND_FLOOR against risk limits and lot size.
6. No hardcoded fee, slippage, or symbol filter defaults: filters come from exchangeInfo, fees from documented models.
7. Evidence-first: unverified probabilities or missing cost payoffs leave expectancy as None.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class ObservationDecision(str, Enum):
    """Advisory decision state for an observed candidate setup."""
    WAIT_CONFIRMATION = "WAIT_CONFIRMATION"
    SKIP = "SKIP"
    WATCH_ONLY = "WATCH_ONLY"
    BUY_ELIGIBLE = "BUY_ELIGIBLE"


class DecisionReason(str, Enum):
    """Deterministic machine-readable reason codes."""
    CONFIG_REQUIRED = "CONFIG_REQUIRED"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    COST_UNVERIFIED = "COST_UNVERIFIED"
    PROBABILITY_UNVERIFIED = "PROBABILITY_UNVERIFIED"
    STALE = "STALE"
    NO_TARGET = "NO_TARGET"
    RISK_EXCEEDED = "RISK_EXCEEDED"
    CONFIRMATION_PENDING = "CONFIRMATION_PENDING"
    INVALIDATED = "INVALIDATED"
    EXPIRED = "EXPIRED"
    TICK_COLLAPSE = "TICK_COLLAPSE"
    OFF_PLAN = "OFF_PLAN"
    RISK_BREACH = "RISK_BREACH"
    SETUP_VALID = "SETUP_VALID"


class PositionLifecycleState(str, Enum):
    """Position state of the local operator."""
    FLAT = "FLAT"
    OPEN = "OPEN"
    EXIT_REQUIRED = "EXIT_REQUIRED"
    CLOSED = "CLOSED"


class CandidateState(str, Enum):
    """Lifecycle of the evaluated candidate plan."""
    WAITING = "WAITING"
    ELIGIBLE = "ELIGIBLE"
    SKIPPED = "SKIPPED"
    INVALIDATED = "INVALIDATED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"
    EXECUTED = "EXECUTED"


class OutcomeDataStatus(str, Enum):
    """Data integrity status of barrier outcome tracking."""
    PENDING = "PENDING"
    OBSERVED = "OBSERVED"
    AMBIGUOUS = "AMBIGUOUS"
    UNSCORABLE = "UNSCORABLE"


class ExecutionMode(str, Enum):
    """Execution recording mode: immutable once opened."""
    PAPER = "PAPER"
    MANUAL_REPORTED = "MANUAL_REPORTED"


class ExitReason(str, Enum):
    """Reason for triggering or recording exit."""
    TP_HIT = "TP_HIT"
    SL_HIT = "SL_HIT"
    TIMEOUT = "TIMEOUT"
    MANUAL_CANCEL = "MANUAL_CANCEL"
    INVALIDATED_BEFORE_ENTRY = "INVALIDATED_BEFORE_ENTRY"


class BarrierOutcomeType(str, Enum):
    """First-touch barrier event outcomes."""
    TP_FIRST = "TP_FIRST"
    SL_FIRST = "SL_FIRST"
    TIMEOUT = "TIMEOUT"


@dataclass(frozen=True)
class SymbolFilters:
    """Exchange-reported trading rules (e.g. from Binance Spot exchangeInfo)."""
    symbol: str
    tick_size: Decimal
    step_size: Decimal
    min_notional: Decimal
    min_qty: Decimal

    def __post_init__(self) -> None:
        if self.tick_size <= Decimal("0") or self.step_size <= Decimal("0"):
            raise ValueError("tick_size and step_size must be strictly positive.")
        if self.min_notional < Decimal("0") or self.min_qty < Decimal("0"):
            raise ValueError("min_notional and min_qty cannot be negative.")

    def quantize_price(self, price: Decimal, rounding=ROUND_HALF_UP) -> Decimal:
        """Quantizes price to exact integer multiple of tick_size."""
        units = (price / self.tick_size).to_integral_value(rounding=rounding)
        return units * self.tick_size

    def quantize_quantity_floor(self, qty: Decimal) -> Decimal:
        """Quantizes quantity to exact integer multiple of step_size strictly rounded down."""
        units = (qty / self.step_size).to_integral_value(rounding=ROUND_FLOOR)
        return units * self.step_size


@dataclass(frozen=True)
class BarrierProbability:
    """Multinomial barrier probabilities with validation status."""
    tp_first: Optional[float] = None
    sl_first: Optional[float] = None
    timeout: Optional[float] = None
    calibration_status: str = "UNVERIFIED"  # "UNVERIFIED" | "CALIBRATED" | "DEGRADED"
    sample_count: int = 0
    period: Optional[str] = None
    interval_tp: Optional[Tuple[float, float]] = None
    interval_sl: Optional[Tuple[float, float]] = None
    artifact_version: Optional[str] = None

    def is_valid(self) -> bool:
        if self.tp_first is None or self.sl_first is None or self.timeout is None:
            return False
        total = self.tp_first + self.sl_first + self.timeout
        return 0.99 <= total <= 1.01 and self.calibration_status == "CALIBRATED" and self.sample_count > 0


@dataclass(frozen=True)
class PayoffExpectancyModel:
    """Fill-aware payoff model parameter estimates derived from empirical execution data."""
    model_version: str
    is_approved: bool
    expected_tp_slippage_bps: Decimal
    expected_sl_slippage_bps: Decimal
    expected_timeout_net_return_bps: Decimal  # Empirical net price move at 30m timeout

    def __post_init__(self) -> None:
        if not self.model_version:
            raise ValueError("model_version is required.")


@dataclass(frozen=True)
class RiskConfig:
    """Capital, fee, and risk boundaries. NO arbitrary default values."""
    max_notional_usdt: Decimal
    max_planned_loss_usdt: Decimal
    fee_rate_bps: Decimal
    slippage_bps: Decimal
    max_wait_duration_ms: int
    max_entry_deviation_pct: Decimal
    freshness_tolerance_ms: int
    max_event_lag_ms: int
    cost_model_source: str

    def __post_init__(self) -> None:
        if self.max_notional_usdt <= Decimal("0"):
            raise ValueError("max_notional_usdt must be strictly positive.")
        if self.max_planned_loss_usdt <= Decimal("0"):
            raise ValueError("max_planned_loss_usdt must be strictly positive.")
        if self.max_planned_loss_usdt > self.max_notional_usdt:
            raise ValueError("max_planned_loss_usdt cannot exceed max_notional_usdt.")
        if self.fee_rate_bps < Decimal("0"):
            raise ValueError("fee_rate_bps cannot be negative.")
        if self.slippage_bps < Decimal("0"):
            raise ValueError("slippage_bps cannot be negative.")
        if self.max_wait_duration_ms <= 0:
            raise ValueError("max_wait_duration_ms must be strictly positive.")
        if not self.cost_model_source:
            raise ValueError("cost_model_source is required to verify fee/slippage provenance.")


@dataclass(frozen=True)
class EntryZone:
    """Price boundaries for valid candidate entry."""
    min_price: Decimal
    max_price: Decimal
    proposed_entry: Decimal

    def __post_init__(self) -> None:
        if self.min_price <= Decimal("0") or self.max_price <= Decimal("0") or self.proposed_entry <= Decimal("0"):
            raise ValueError("Prices in EntryZone must be strictly positive.")
        if not (self.min_price <= self.proposed_entry <= self.max_price):
            raise ValueError(f"proposed_entry {self.proposed_entry} outside [{self.min_price}, {self.max_price}].")


@dataclass(frozen=True)
class ConfirmationRule:
    """Conditions required on closed candles before entry eligibility."""
    support_level: Decimal
    reclaim_level: Decimal
    confirmation_candle_close_ms: Optional[int] = None
    touched_at_ms: Optional[int] = None
    confirmed_at_ms: Optional[int] = None

    def __post_init__(self) -> None:
        if self.support_level <= Decimal("0") or self.reclaim_level <= Decimal("0"):
            raise ValueError("Confirmation levels must be strictly positive.")


@dataclass(frozen=True)
class InvalidationRule:
    """Predicate marking candidate invalidated before entry."""
    invalidation_price: Decimal
    buffer_percent: Decimal

    def __post_init__(self) -> None:
        if self.invalidation_price <= Decimal("0"):
            raise ValueError("invalidation_price must be strictly positive.")


@dataclass(frozen=True)
class CandidatePlan:
    """Deterministic candidate barrier plan generated at decision_time_ms."""
    candidate_id: str
    strategy_version: str
    rule_config_hash: str
    decision_time_ms: int
    available_cutoff_ms: int
    entry_zone: EntryZone
    confirmation: ConfirmationRule
    invalidation: InvalidationRule
    stop_price: Decimal
    target_price: Decimal
    risk_config: RiskConfig
    symbol_filters: SymbolFilters
    wait_expires_at_ms: int
    horizon_ms: int = 1_800_000  # Exactly 30 minutes
    snapshot_hash: Optional[str] = None
    feed_hash: Optional[str] = None
    live_receipt_refs: Tuple[str, ...] = ()
    evidence_candle_ids: Tuple[int, ...] = ()
    cost_model_version: Optional[str] = None
    probability_estimate_ref: Optional[str] = None
    probability: Optional[BarrierProbability] = None
    reasons: Tuple[DecisionReason, ...] = ()
    contradictions: Tuple[str, ...] = ()
    candidate_state: CandidateState = CandidateState.WAITING

    def __post_init__(self) -> None:
        # Long-only invariant: stop_price < proposed_entry < target_price
        if not (self.stop_price < self.entry_zone.proposed_entry < self.target_price):
            raise ValueError(
                f"Barrier order invariant violated: stop ({self.stop_price}) < "
                f"proposed_entry ({self.entry_zone.proposed_entry}) < target ({self.target_price}) required."
            )
        if self.invalidation.invalidation_price > self.entry_zone.proposed_entry:
            raise ValueError("invalidation_price cannot be above proposed_entry in long setup.")
        if self.wait_expires_at_ms <= self.decision_time_ms:
            raise ValueError("wait_expires_at_ms must be strictly after decision_time_ms.")

    @property
    def proposed_entry(self) -> Decimal:
        return self.entry_zone.proposed_entry

    @property
    def reward_risk_ratio(self) -> Decimal:
        risk = self.proposed_entry - self.stop_price
        if risk <= Decimal("0"):
            return Decimal("0")
        return (self.target_price - self.proposed_entry) / risk

    def compute_planned_quantity(self) -> Decimal:
        """Computes quantity using strictly ROUND_FLOOR so risk limits are never exceeded."""
        cost_rate = (2 * self.risk_config.fee_rate_bps + 2 * self.risk_config.slippage_bps) / Decimal("10000")
        price_drop = self.proposed_entry - self.stop_price
        loss_per_coin = price_drop + (self.proposed_entry * cost_rate)

        qty_by_risk = self.risk_config.max_planned_loss_usdt / loss_per_coin
        qty_by_notional = self.risk_config.max_notional_usdt / self.proposed_entry

        qty = min(qty_by_risk, qty_by_notional)
        floored_qty = self.symbol_filters.quantize_quantity_floor(qty)

        if floored_qty < self.symbol_filters.min_qty:
            return Decimal("0")
        if (floored_qty * self.proposed_entry) < self.symbol_filters.min_notional:
            return Decimal("0")

        return floored_qty

    def compute_planned_loss_usdt(self, quantity: Decimal) -> Decimal:
        """Planned loss including fees and slippage."""
        price_drop = (self.proposed_entry - self.stop_price) * quantity
        cost_rate = (2 * self.risk_config.fee_rate_bps + 2 * self.risk_config.slippage_bps) / Decimal("10000")
        costs = self.proposed_entry * quantity * cost_rate
        return (price_drop + costs).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def compute_net_expectancy(
        self,
        quantity: Decimal,
        payoff_model: Optional[PayoffExpectancyModel] = None,
    ) -> Optional[Decimal]:
        """Expected net payoff E[net] = p_tp*E[net|tp] + p_sl*E[net|sl] + p_to*E[net|to]."""
        if self.probability is None or not self.probability.is_valid():
            return None
        if payoff_model is None or not payoff_model.is_approved:
            return None

        fee_rate = (2 * self.risk_config.fee_rate_bps) / Decimal("10000")
        total_fees = self.proposed_entry * quantity * fee_rate

        tp_slippage = (payoff_model.expected_tp_slippage_bps / Decimal("10000")) * self.target_price * quantity
        gain_tp = ((self.target_price - self.proposed_entry) * quantity) - total_fees - tp_slippage

        sl_slippage = (payoff_model.expected_sl_slippage_bps / Decimal("10000")) * self.stop_price * quantity
        loss_sl = -(((self.proposed_entry - self.stop_price) * quantity) + total_fees + sl_slippage)

        timeout_price_move = (payoff_model.expected_timeout_net_return_bps / Decimal("10000")) * self.proposed_entry * quantity
        payoff_to = timeout_price_move - total_fees

        e_net = (
            Decimal(str(self.probability.tp_first)) * gain_tp
            + Decimal(str(self.probability.sl_first)) * loss_sl
            + Decimal(str(self.probability.timeout)) * payoff_to
        )
        return e_net.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class EntryObservation:
    """Record of an executed or reported trade entry."""
    observation_id: str
    candidate_id: str
    mode: ExecutionMode
    entry_price: Decimal
    entry_quantity: Decimal
    actual_entry_time_ms: int
    receipt_time_ms: int
    fees_paid_usdt: Decimal
    is_off_plan: bool = False
    is_risk_breach: bool = False
    reconciled_sl_breach_detected: bool = False
    notes: Optional[str] = None

    def __post_init__(self) -> None:
        if self.entry_price <= Decimal("0"):
            raise ValueError("entry_price must be strictly positive.")
        if self.entry_quantity <= Decimal("0"):
            raise ValueError("entry_quantity must be strictly positive.")
        if self.receipt_time_ms < self.actual_entry_time_ms:
            raise ValueError("receipt_time_ms cannot be before actual_entry_time_ms.")


@dataclass(frozen=True)
class ExitObservation:
    """Record of an executed or reported position exit."""
    exit_id: str
    candidate_id: str
    mode: ExecutionMode
    exit_price: Decimal
    exit_quantity: Decimal
    actual_exit_time_ms: int
    receipt_time_ms: int
    fees_paid_usdt: Decimal
    exit_reason: ExitReason
    realized_pnl_usdt: Optional[Decimal] = None
    notes: Optional[str] = None

    def __post_init__(self) -> None:
        if self.exit_price <= Decimal("0"):
            raise ValueError("exit_price must be strictly positive.")
        if self.exit_quantity <= Decimal("0"):
            raise ValueError("exit_quantity must be strictly positive.")
        if self.receipt_time_ms < self.actual_exit_time_ms:
            raise ValueError("receipt_time_ms cannot be before actual_exit_time_ms.")
