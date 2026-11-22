"""Barrier outcome evaluation and causal path simulation.

Follows Phase 03 plan: docs/plans/261010-fast-entry-30m-strategy/phase-03-probability-validation.md.
Adheres strictly to Binance Spot VIP 0 fee schedule (docs/binance-spot-fees.md).
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional

from shootingstar.domain.models import Candle


class FirstTouchOutcome(str, Enum):
    """First-touch barrier simulation outcome labels."""

    TP_FIRST = "TP_FIRST"
    SL_FIRST = "SL_FIRST"
    TIMEOUT = "TIMEOUT"
    AMBIGUOUS = "AMBIGUOUS"
    CENSORED = "CENSORED"
    UNSCORABLE = "UNSCORABLE"


@dataclass(frozen=True)
class BarrierSimulationResult:
    """Outcome and cost-adjusted metrics of a single barrier holding episode."""

    outcome: FirstTouchOutcome
    entry_price: Decimal
    exit_price: Optional[Decimal]
    entry_time_ms: int
    exit_time_ms: int
    gross_return_pct: Optional[Decimal]
    net_return_pct: Optional[Decimal]
    fee_rate_bps: Decimal
    slippage_bps: Decimal
    is_cost_gated: bool
    note: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "outcome": self.outcome.value,
            "entry_price": float(self.entry_price),
            "exit_price": float(self.exit_price) if self.exit_price is not None else None,
            "entry_time_ms": self.entry_time_ms,
            "exit_time_ms": self.exit_time_ms,
            "gross_return_pct": float(self.gross_return_pct) if self.gross_return_pct is not None else None,
            "net_return_pct": float(self.net_return_pct) if self.net_return_pct is not None else None,
            "fee_rate_bps": float(self.fee_rate_bps),
            "slippage_bps": float(self.slippage_bps),
            "is_cost_gated": self.is_cost_gated,
            "note": self.note,
        }


class FirstTouchLabeler:
    """Causal first-touch labeler over subsequent historical candle paths."""

    # Default VIP 0 fee schedule: 10 bps maker/taker; 5 bps slippage assumption
    DEFAULT_FEE_RATE_BPS = Decimal("10.0")
    DEFAULT_SLIPPAGE_BPS = Decimal("5.0")

    def evaluate_path(
        self,
        entry_price: Decimal,
        target_price: Decimal,
        stop_price: Decimal,
        entry_time_ms: int,
        deadline_ms: int,
        candles: List[Candle],
        fee_rate_bps: Decimal = DEFAULT_FEE_RATE_BPS,
        slippage_bps: Decimal = DEFAULT_SLIPPAGE_BPS,
        has_quote_depth: bool = False,
    ) -> BarrierSimulationResult:
        """Evaluate path causally from entry to target/stop or deadline."""
        if not candles:
            return BarrierSimulationResult(
                outcome=FirstTouchOutcome.UNSCORABLE,
                entry_price=entry_price,
                exit_price=None,
                entry_time_ms=entry_time_ms,
                exit_time_ms=entry_time_ms,
                gross_return_pct=None,
                net_return_pct=None,
                fee_rate_bps=fee_rate_bps,
                slippage_bps=slippage_bps,
                is_cost_gated=True,
                note="No subsequent candles available for path evaluation.",
            )

        # Invariant: Long-only spot BTCUSDT
        if not (stop_price < entry_price < target_price):
            return BarrierSimulationResult(
                outcome=FirstTouchOutcome.UNSCORABLE,
                entry_price=entry_price,
                exit_price=None,
                entry_time_ms=entry_time_ms,
                exit_time_ms=entry_time_ms,
                gross_return_pct=None,
                net_return_pct=None,
                fee_rate_bps=fee_rate_bps,
                slippage_bps=slippage_bps,
                is_cost_gated=True,
                note=f"Invalid barrier geometry: stop={stop_price}, entry={entry_price}, target={target_price}",
            )

        target_dec = target_price
        stop_dec = stop_price
        entry_dec = entry_price

        # Filter forward candles strictly occurring at or after entry
        forward_candles = [c for c in candles if c.close_time_ms >= entry_time_ms]
        if not forward_candles:
            return BarrierSimulationResult(
                outcome=FirstTouchOutcome.CENSORED,
                entry_price=entry_price,
                exit_price=entry_price,
                entry_time_ms=entry_time_ms,
                exit_time_ms=entry_time_ms,
                gross_return_pct=Decimal("0.0"),
                net_return_pct=None,
                fee_rate_bps=fee_rate_bps,
                slippage_bps=slippage_bps,
                is_cost_gated=True,
                note="Censored: No candles observed after entry_time_ms.",
            )

        resolved_outcome: Optional[FirstTouchOutcome] = None
        exit_price_dec: Optional[Decimal] = entry_dec
        exit_time_ms: int = entry_time_ms
        note_str = ""

        for c in forward_candles:
            # Guard against post-deadline bars
            if c.open_time_ms >= deadline_ms:
                break
            high_dec = Decimal(str(c.high))
            low_dec = Decimal(str(c.low))
            close_dec = Decimal(str(c.close))
            touches_tp = high_dec >= target_dec
            touches_sl = low_dec <= stop_dec

            # Rule: Fill bar barrier touch without intrabar ticks is UNSCORABLE
            # (cannot causally determine if barrier was hit before or after entry price)
            if c.open_time_ms == entry_time_ms and (touches_tp or touches_sl):
                resolved_outcome = FirstTouchOutcome.UNSCORABLE
                exit_price_dec = None
                exit_time_ms = c.close_time_ms
                note_str = (
                    f"Unscorable: Barrier touched on intrabar fill candle ({c.open_time_ms} - {c.close_time_ms}); "
                    f"entry timing vs barrier order unknowable without tick-level arrival order."
                )
                break

            # Explicitly resolve bars straddling the deadline
            if c.open_time_ms < deadline_ms < c.close_time_ms:
                if touches_tp or touches_sl:
                    resolved_outcome = FirstTouchOutcome.UNSCORABLE
                    exit_price_dec = None
                    exit_time_ms = deadline_ms
                    note_str = (
                        f"Unscorable: Candle straddles deadline {deadline_ms} (open={c.open_time_ms}, close={c.close_time_ms}) "
                        f"and touched barrier without tick-level arrival order."
                    )
                else:
                    resolved_outcome = FirstTouchOutcome.TIMEOUT
                    exit_price_dec = None
                    exit_time_ms = deadline_ms
                    note_str = (
                        f"Horizon deadline {deadline_ms} reached within candle without barrier breach (TIMEOUT). "
                        f"Exit price and PnL unavailable without tick data at deadline (no invented exit price/fee)."
                    )
                break

            # Rule: Same-bar ambiguity without intrabar ticks must be labeled AMBIGUOUS
            if touches_tp and touches_sl:
                resolved_outcome = FirstTouchOutcome.AMBIGUOUS
                exit_price_dec = None
                exit_time_ms = c.close_time_ms
                note_str = (
                    f"Ambiguous: Bar at {c.close_time_ms} breached both target ({target_dec}) "
                    f"and stop ({stop_dec}) without tick-level arrival order."
                )
                break
            if touches_tp:
                resolved_outcome = FirstTouchOutcome.TP_FIRST
                exit_price_dec = target_dec
                exit_time_ms = c.close_time_ms
                note_str = f"Target price {target_dec} touched at candle closing {c.close_time_ms}."
                break

            if touches_sl:
                resolved_outcome = FirstTouchOutcome.SL_FIRST
                exit_price_dec = stop_dec
                exit_time_ms = c.close_time_ms
                note_str = f"Stop price {stop_dec} breached at candle closing {c.close_time_ms}."
                break

            # Deadline boundary reached (inclusive of 1ms kline convention)
            if (c.close_time_ms + 1) >= deadline_ms:
                resolved_outcome = FirstTouchOutcome.TIMEOUT
                exit_price_dec = close_dec
                exit_time_ms = c.close_time_ms
                note_str = f"Horizon deadline {deadline_ms} reached. Position closed at candle close {close_dec}."
                break

        if resolved_outcome is None:
            # Data ended before reaching deadline or barriers
            resolved_outcome = FirstTouchOutcome.CENSORED
            exit_price_dec = Decimal(str(forward_candles[-1].close))
            exit_time_ms = forward_candles[-1].close_time_ms
            note_str = f"Censored: Forward data truncated at {exit_time_ms} before deadline {deadline_ms}."

        if exit_price_dec is not None:
            gross_return_pct = ((exit_price_dec - entry_dec) / entry_dec) * Decimal("100.0")
        else:
            gross_return_pct = None

        # Cost-adjustment policy: Round-trip fee (2 x fee_rate) + Round-trip slippage (2 x slippage)
        # Total cost rate in percent: (2 * fee_bps + 2 * slippage_bps) / 100
        total_cost_pct = (Decimal("2.0") * fee_rate_bps + Decimal("2.0") * slippage_bps) / Decimal("100.0")

        if resolved_outcome in (FirstTouchOutcome.AMBIGUOUS, FirstTouchOutcome.UNSCORABLE) or gross_return_pct is None:
            net_return_pct = None
            is_cost_gated = True
        elif not has_quote_depth:
            # Under docs/binance-spot-fees.md: Gated baseline if snapshot lacks executable quote depth
            net_return_pct = gross_return_pct - total_cost_pct
            is_cost_gated = True
            note_str += " [Gated: Net PnL assumes VIP 0 10 bps fee + 5 bps slippage baseline without order book depth]."
        else:
            net_return_pct = gross_return_pct - total_cost_pct
            is_cost_gated = False
        return BarrierSimulationResult(
            outcome=resolved_outcome,
            entry_price=entry_dec,
            exit_price=exit_price_dec,
            entry_time_ms=entry_time_ms,
            exit_time_ms=exit_time_ms,
            gross_return_pct=gross_return_pct,
            net_return_pct=net_return_pct,
            fee_rate_bps=fee_rate_bps,
            slippage_bps=slippage_bps,
            is_cost_gated=is_cost_gated,
            note=note_str,
        )


