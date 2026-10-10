"""Barrier outcome evaluation, causal path simulation, and empirical probability estimation.

Follows Phase 03 plan: docs/plans/261010-fast-entry-30m-strategy/phase-03-probability-validation.md.
Adheres strictly to Binance Spot VIP 0 fee schedule (docs/binance-spot-fees.md).
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy.stats import beta

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


@dataclass(frozen=True)
class MultinomialProbabilityEstimate:
    """Smoothed empirical probability distribution across competing outcomes."""

    p_tp: Optional[float]
    p_sl: Optional[float]
    p_timeout: Optional[float]
    sample_size: int
    alpha_smoothing: float
    is_calibrated: bool
    gating_reason: Optional[str]
    credible_intervals: Optional[Dict[str, Tuple[float, float]]] = None
    def to_dict(self) -> Dict[str, Any]:
        return {
            "p_tp": self.p_tp,
            "p_sl": self.p_sl,
            "p_timeout": self.p_timeout,
            "sample_size": self.sample_size,
            "alpha_smoothing": self.alpha_smoothing,
            "is_calibrated": self.is_calibrated,
            "gating_reason": self.gating_reason,
            "credible_intervals": {k: list(v) for k, v in self.credible_intervals.items()} if self.credible_intervals else None,
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


class EmpiricalMultinomialEstimator:
    """Computes Dirichlet-smoothed empirical probability distribution."""

    def estimate(
        self,
        outcomes: List[FirstTouchOutcome],
        min_samples: int = 30,
        alpha: float = 1.0,
    ) -> MultinomialProbabilityEstimate:
        """Estimate smoothed probabilities across TP_FIRST, SL_FIRST, TIMEOUT.

        Resolves unobserved or insufficient samples with gated null probabilities.
        """
        valid_outcomes = [o for o in outcomes if o in (FirstTouchOutcome.TP_FIRST, FirstTouchOutcome.SL_FIRST, FirstTouchOutcome.TIMEOUT)]
        n_total = len(valid_outcomes)

        if n_total < min_samples:
            return MultinomialProbabilityEstimate(
                p_tp=None,
                p_sl=None,
                p_timeout=None,
                sample_size=n_total,
                alpha_smoothing=alpha,
                is_calibrated=False,
                gating_reason=f"Insufficient sample size ({n_total} < min {min_samples}). Gated per Accuracy Before Speed.",
            )

        n_tp = sum(1 for o in valid_outcomes if o == FirstTouchOutcome.TP_FIRST)
        n_sl = sum(1 for o in valid_outcomes if o == FirstTouchOutcome.SL_FIRST)
        n_to = sum(1 for o in valid_outcomes if o == FirstTouchOutcome.TIMEOUT)

        denom = float(n_total + 3.0 * alpha)
        p_tp = (n_tp + alpha) / denom
        p_sl = (n_sl + alpha) / denom
        p_timeout = (n_to + alpha) / denom

        return MultinomialProbabilityEstimate(
            p_tp=round(p_tp, 4),
            p_sl=round(p_sl, 4),
            p_timeout=round(p_timeout, 4),
            sample_size=n_total,
            alpha_smoothing=alpha,
            is_calibrated=True,
            gating_reason=None,
            credible_intervals={
                "p_tp": (
                    round(float(beta.ppf(0.05, n_tp + alpha, n_total - n_tp + 2.0 * alpha)), 4),
                    round(float(beta.ppf(0.95, n_tp + alpha, n_total - n_tp + 2.0 * alpha)), 4),
                ),
                "p_sl": (
                    round(float(beta.ppf(0.05, n_sl + alpha, n_total - n_sl + 2.0 * alpha)), 4),
                    round(float(beta.ppf(0.95, n_sl + alpha, n_total - n_sl + 2.0 * alpha)), 4),
                ),
                "p_timeout": (
                    round(float(beta.ppf(0.05, n_to + alpha, n_total - n_to + 2.0 * alpha)), 4),
                    round(float(beta.ppf(0.95, n_to + alpha, n_total - n_to + 2.0 * alpha)), 4),
                ),
            },
        )


@dataclass(frozen=True)
class BarrierModelArtifact:
    """Persisted candidate or approved barrier probability model artifact."""

    artifact_hash: str
    strategy_version: str
    created_at_utc: str
    train_cutoff_ms: int
    sample_size: int
    alpha_smoothing: float
    p_tp: float
    p_sl: float
    p_timeout: float
    credible_intervals: Dict[str, Tuple[float, float]]
    brier_score: Optional[float] = None
    log_loss: Optional[float] = None
    is_approved: bool = False
    approved_by: Optional[str] = None
    approved_at_utc: Optional[str] = None
    approval_verdict: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "artifact_hash": self.artifact_hash,
            "strategy_version": self.strategy_version,
            "created_at_utc": self.created_at_utc,
            "train_cutoff_ms": self.train_cutoff_ms,
            "sample_size": self.sample_size,
            "alpha_smoothing": self.alpha_smoothing,
            "p_tp": self.p_tp,
            "p_sl": self.p_sl,
            "p_timeout": self.p_timeout,
            "credible_intervals": {k: list(v) for k, v in self.credible_intervals.items()},
            "brier_score": self.brier_score,
            "log_loss": self.log_loss,
            "is_approved": self.is_approved,
            "approved_by": self.approved_by,
            "approved_at_utc": self.approved_at_utc,
            "approval_verdict": self.approval_verdict,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "BarrierModelArtifact":
        cis = {k: tuple(v) for k, v in d["credible_intervals"].items()}
        return cls(
            artifact_hash=d["artifact_hash"],
            strategy_version=d["strategy_version"],
            created_at_utc=d["created_at_utc"],
            train_cutoff_ms=d["train_cutoff_ms"],
            sample_size=d["sample_size"],
            alpha_smoothing=d["alpha_smoothing"],
            p_tp=d["p_tp"],
            p_sl=d["p_sl"],
            p_timeout=d["p_timeout"],
            credible_intervals=cis,
            brier_score=d.get("brier_score"),
            log_loss=d.get("log_loss"),
            is_approved=d.get("is_approved", False),
            approved_by=d.get("approved_by"),
            approved_at_utc=d.get("approved_at_utc"),
            approval_verdict=d.get("approval_verdict"),
        )


class BarrierArtifactManager:
    """Manages serialization, out-of-sample evaluation, and strict gating for barrier artifacts."""

    @staticmethod
    def save_artifact(artifact: BarrierModelArtifact, target_dir: Path) -> Path:
        target_dir.mkdir(parents=True, exist_ok=True)
        out_path = target_dir / f"barrier_{artifact.artifact_hash}.manifest.json"
        out_path.write_text(json.dumps(artifact.to_dict(), indent=2), encoding="utf-8")
        return out_path

    @staticmethod
    def load_artifact(artifact_path: Path) -> BarrierModelArtifact:
        raw = json.loads(artifact_path.read_text(encoding="utf-8"))
        return BarrierModelArtifact.from_dict(raw)

    @staticmethod
    def compute_multiclass_metrics(
        p_tp: float,
        p_sl: float,
        p_timeout: float,
        outcomes: List[FirstTouchOutcome],
        eval_start_ms: Optional[int] = None,
        eps: float = 1e-6,
    ) -> Dict[str, Any]:
        """Compute multiclass Brier score and log loss over test outcomes."""
        valid_outcomes = [o for o in outcomes if o in (FirstTouchOutcome.TP_FIRST, FirstTouchOutcome.SL_FIRST, FirstTouchOutcome.TIMEOUT)]
        if not valid_outcomes:
            return {"brier_score": 0.0, "log_loss": 0.0, "test_samples": 0.0}

        probs = [p_tp, p_sl, p_timeout]
        brier_sum = 0.0
        log_loss_sum = 0.0

        for o in valid_outcomes:
            y = [
                1.0 if o == FirstTouchOutcome.TP_FIRST else 0.0,
                1.0 if o == FirstTouchOutcome.SL_FIRST else 0.0,
                1.0 if o == FirstTouchOutcome.TIMEOUT else 0.0,
            ]
            for p, target in zip(probs, y):
                brier_sum += (p - target) ** 2
                if target == 1.0:
                    log_loss_sum += -float(np.log(max(p, eps)))

        n = float(len(valid_outcomes))
        return {
            "brier_score": round(brier_sum / n, 4),
            "log_loss": round(log_loss_sum / n, 4),
            "test_samples": float(n),
            "eval_start_ms": eval_start_ms,
        }

    @staticmethod
    def verify_approval_gates(
        artifact: BarrierModelArtifact,
        eval_report: Dict[str, Any],
        min_samples: int = 30,
        max_ci_width: float = 0.35,
    ) -> Tuple[bool, List[str]]:
        """Verify strict gates before approving an artifact."""
        violations = []
        if artifact.sample_size < min_samples:
            violations.append(f"Gate 1 failed: Training sample size ({artifact.sample_size}) < min {min_samples}.")

        for k, (low, high) in artifact.credible_intervals.items():
            width = high - low
            if width > max_ci_width:
                violations.append(f"Gate 2 failed: Credible interval {k} width ({width:.4f}) exceeds max {max_ci_width}.")

        test_samples = eval_report.get("test_samples", 0)
        if test_samples < 10:
            violations.append(f"Gate 3 failed: OOS evaluation sample count ({test_samples}) < 10.")

        brier = eval_report.get("brier_score", 1.0)
        # Uniform baseline: 2/3 = 0.6667
        if brier >= 0.667:
            violations.append(f"Gate 4 failed: Brier score ({brier}) does not outperform uniform baseline (0.667).")

        eval_start_ms = eval_report.get("eval_start_ms")
        if eval_start_ms is None or eval_start_ms <= artifact.train_cutoff_ms:
            violations.append(
                f"Gate 5 failed: Evaluation start time ({eval_start_ms}) "
                f"<= artifact training cutoff ({artifact.train_cutoff_ms}). Strict temporal separation violated."
            )

        return len(violations) == 0, violations

    @staticmethod
    def approve_artifact(
        artifact_path: Path,
        eval_report: Dict[str, Any],
        approver: str = "admin",
    ) -> BarrierModelArtifact:
        artifact = BarrierArtifactManager.load_artifact(artifact_path)
        ok, violations = BarrierArtifactManager.verify_approval_gates(artifact, eval_report)
        from datetime import datetime, timezone
        now_iso = datetime.now(timezone.utc).isoformat()
        if not ok:
            verdict = f"REJECTED: {'; '.join(violations)}"
            updated = BarrierModelArtifact(
                artifact_hash=artifact.artifact_hash,
                strategy_version=artifact.strategy_version,
                created_at_utc=artifact.created_at_utc,
                train_cutoff_ms=artifact.train_cutoff_ms,
                sample_size=artifact.sample_size,
                alpha_smoothing=artifact.alpha_smoothing,
                p_tp=artifact.p_tp,
                p_sl=artifact.p_sl,
                p_timeout=artifact.p_timeout,
                credible_intervals=artifact.credible_intervals,
                brier_score=eval_report.get("brier_score"),
                log_loss=eval_report.get("log_loss"),
                is_approved=False,
                approved_by=approver,
                approved_at_utc=now_iso,
                approval_verdict=verdict,
            )
            BarrierArtifactManager.save_artifact(updated, artifact_path.parent)
            raise ValueError(f"Approval rejected per validation gates: {violations}")

        verdict = "APPROVED: All validation gates passed."
        updated = BarrierModelArtifact(
            artifact_hash=artifact.artifact_hash,
            strategy_version=artifact.strategy_version,
            created_at_utc=artifact.created_at_utc,
            train_cutoff_ms=artifact.train_cutoff_ms,
            sample_size=artifact.sample_size,
            alpha_smoothing=artifact.alpha_smoothing,
            p_tp=artifact.p_tp,
            p_sl=artifact.p_sl,
            p_timeout=artifact.p_timeout,
            credible_intervals=artifact.credible_intervals,
            brier_score=eval_report.get("brier_score"),
            log_loss=eval_report.get("log_loss"),
            is_approved=True,
            approved_by=approver,
            approved_at_utc=now_iso,
            approval_verdict=verdict,
        )
        BarrierArtifactManager.save_artifact(updated, artifact_path.parent)
        return updated
