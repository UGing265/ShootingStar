"""Simulation job engine: point-in-time buy simulation with zero-lookahead, user vote and outcome reveal."""

from dataclasses import dataclass
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid

from shootingstar.adapters.storage import SnapshotStorage
from shootingstar.domain.exceptions import DomainError
from shootingstar.domain.models import Candle, Timeframe

logger = logging.getLogger(__name__)



@dataclass
class SimulationAIPrediction:
    predicted_direction: str  # "UP", "DOWN", or "NO_MODEL"
    probability_up: Optional[float] = None
    probability_down: Optional[float] = None
    model_version: Optional[str] = None
    model_cutoff_ms: Optional[int] = None
    evidence_summary: Optional[str] = None
    is_calibrated: bool = False


@dataclass
class SimulationUserVote:
    user_direction: str
    voted_at_utc: str
    is_locked: bool = True


@dataclass
class SimulationOutcome:
    status: str  # "EVALUATED", "PENDING", "UNSCORABLE"
    horizon_time_ms: int
    future_price: Optional[float] = None
    price_change_pct: Optional[float] = None
    market_direction: Optional[str] = None
    ai_is_correct: Optional[bool] = None
    user_is_correct: Optional[bool] = None
    unscorable_reason: Optional[str] = None
    revealed_at_utc: Optional[str] = None


@dataclass
class SimulationJob:
    job_id: str
    snapshot_id: str
    symbol: str
    timeframe: str
    buy_time_ms: int
    buy_price: float
    candle_close_at_buy: float
    price_offset_pct: float
    horizon_minutes: int
    status: str  # "AI_PREDICTED", "VOTED", "REVEALED", "FAILED"
    created_at_utc: str
    ai_prediction: Optional[SimulationAIPrediction] = None
    user_vote: Optional[SimulationUserVote] = None
    outcome: Optional[SimulationOutcome] = None
    strategy_evaluation: Optional[Dict[str, Any]] = None
    strategy_outcome: Optional[Dict[str, Any]] = None

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "snapshot_id": self.snapshot_id,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "buy_time_ms": self.buy_time_ms,
            "buy_price": self.buy_price,
            "candle_close_at_buy": self.candle_close_at_buy,
            "price_offset_pct": self.price_offset_pct,
            "horizon_minutes": self.horizon_minutes,
            "status": self.status,
            "created_at_utc": self.created_at_utc,
            "ai_prediction": self.ai_prediction.__dict__ if self.ai_prediction else None,
            "user_vote": self.user_vote.__dict__ if self.user_vote else None,
            "outcome": self.outcome.__dict__ if self.outcome else None,
            "strategy_evaluation": self.strategy_evaluation,
            "strategy_outcome": self.strategy_outcome,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SimulationJob":
        ai_pred = SimulationAIPrediction(**d["ai_prediction"]) if d.get("ai_prediction") else None
        vote = SimulationUserVote(**d["user_vote"]) if d.get("user_vote") else None
        outcome = SimulationOutcome(**d["outcome"]) if d.get("outcome") else None
        return cls(
            job_id=d["job_id"],
            snapshot_id=d["snapshot_id"],
            symbol=d["symbol"],
            timeframe=d["timeframe"],
            buy_time_ms=d["buy_time_ms"],
            buy_price=d["buy_price"],
            candle_close_at_buy=d["candle_close_at_buy"],
            price_offset_pct=d["price_offset_pct"],
            horizon_minutes=d["horizon_minutes"],
            status=d["status"],
            created_at_utc=d["created_at_utc"],
            ai_prediction=ai_pred,
            user_vote=vote,
            outcome=outcome,
            strategy_evaluation=d.get("strategy_evaluation"),
            strategy_outcome=d.get("strategy_outcome"),
        )


class SimulationJobManager:
    """Manages 4-step point-in-time simulations with zero-lookahead guarantees and disk persistence."""

    def __init__(
        self,
        snapshot_storage: Optional[SnapshotStorage] = None,
        simulations_dir: Optional[Path] = None,
    ):
        self.snapshot_storage = snapshot_storage or SnapshotStorage()
        self.simulations_dir = simulations_dir or Path("data/simulations")
        self.simulations_dir.mkdir(parents=True, exist_ok=True)
        self._jobs: Dict[str, SimulationJob] = {}
        self._load_persisted_jobs()

    def _load_persisted_jobs(self) -> None:
        for p in self.simulations_dir.glob("*.json"):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                job = SimulationJob.from_dict(data)
                self._jobs[job.job_id] = job
            except Exception as err:
                logger.warning("Failed to load persisted simulation job %s: %s", p, err)

    def _persist_job(self, job: SimulationJob) -> None:
        out_path = self.simulations_dir / f"{job.job_id}.json"
        out_path.write_text(json.dumps(job.to_dict(), indent=2), encoding="utf-8")
        self._jobs[job.job_id] = job

    @staticmethod
    def _snapshot_info(path: Path) -> tuple[int, int, str]:
        """Read only metadata columns when the caller has no snapshot DB record."""
        import pyarrow.parquet as pq

        parquet = pq.ParquetFile(path)
        metadata = parquet.metadata
        if metadata.num_rows == 0:
            raise DomainError(f"Snapshot has no candles: {path}")

        def boundary(column: str, group: int, first: bool):
            stats = metadata.row_group(group).column(parquet.schema.names.index(column)).statistics
            if stats is not None and stats.has_min_max:
                return stats.min if first else stats.max
            values = parquet.read_row_group(group, columns=[column])[column]
            return values[0 if first else -1].as_py()

        return (boundary("open_time_ms", 0, True),
                boundary("close_time_ms", metadata.num_row_groups - 1, False),
                boundary("timeframe", 0, True))


    def create_job(
        self,
        snapshot_path: Path,
        snapshot_id: str,
        buy_time_ms: int,
        buy_price: float,
        horizon_minutes: int = 30,
        *,
        snapshot_start_ms: Optional[int] = None,
        snapshot_end_ms: Optional[int] = None,
        snapshot_timeframe: Optional[str] = None,
    ) -> SimulationJob:
        if snapshot_start_ms is None or snapshot_end_ms is None or snapshot_timeframe is None:
            snapshot_start_ms, snapshot_end_ms, snapshot_timeframe = self._snapshot_info(snapshot_path)
        snap_start_ms = snapshot_start_ms
        snap_end_ms = snapshot_end_ms

        if buy_time_ms < snap_start_ms or buy_time_ms > snap_end_ms:
            raise DomainError(
                f"buy_time_ms ({buy_time_ms}) outside snapshot bounds [{snap_start_ms}, {snap_end_ms}]"
            )

        from shootingstar.application.entry_strategy import EntryStrategyEngine, is_candle_causally_available

        tf_ms = Timeframe(snapshot_timeframe).duration_ms
        engine = EntryStrategyEngine()
        span = (engine.lookback_bars + 2) * tf_ms
        while True:
            start = max(snap_start_ms, buy_time_ms - span)
            candles = self.snapshot_storage.load_snapshot_window(
                snapshot_path, start_ms=start, end_ms=min(snap_end_ms, buy_time_ms + tf_ms - 1))
            if start <= snap_start_ms or sum(
                is_candle_causally_available(c, buy_time_ms, engine.assumed_latency_ms) for c in candles
            ) >= engine.lookback_bars:
                break
            span *= 2
        if not candles:
            import pyarrow.parquet as pq
            if pq.read_metadata(snapshot_path).num_rows == 0:
                raise DomainError(f"Snapshot has no candles: {snapshot_path}")
            raise DomainError("Cannot simulate prior to first available candle in snapshot")
        symbol = candles[0].symbol
        timeframe = candles[0].timeframe

        # Strict zero-lookahead: visible candles are strictly candles available/closed <= buy_time_ms
        visible_candles = [c for c in candles if c.close_time_ms <= buy_time_ms]
        if not visible_candles:
            visible_candles = [c for c in candles if c.open_time_ms <= buy_time_ms]

        if not visible_candles:
            raise DomainError("Cannot simulate prior to first available candle in snapshot")

        c_t = visible_candles[-1]
        candle_close = c_t.close
        price_offset_pct = ((buy_price - candle_close) / candle_close) * 100.0

        # AI Prediction generation
        ai_prediction = self._evaluate_ai_prediction(
            visible_candles=visible_candles,
            buy_time_ms=buy_time_ms,
            horizon_minutes=horizon_minutes,
        )

        # Evaluate fast-entry 30m barrier strategy offline without lookahead
        strategy_evaluation = self._evaluate_strategy_candidate(
            visible_candles=visible_candles,
            buy_time_ms=buy_time_ms,
            horizon_minutes=horizon_minutes,
        )

        from datetime import datetime, timezone
        job_id = str(uuid.uuid4())
        now_utc = datetime.now(timezone.utc).isoformat()

        job = SimulationJob(
            job_id=job_id,
            snapshot_id=snapshot_id,
            symbol=symbol,
            timeframe=timeframe,
            buy_time_ms=buy_time_ms,
            buy_price=buy_price,
            candle_close_at_buy=candle_close,
            price_offset_pct=round(price_offset_pct, 4),
            horizon_minutes=horizon_minutes,
            status="AI_PREDICTED",
            created_at_utc=now_utc,
            ai_prediction=ai_prediction,
            user_vote=None,
            outcome=None,
            strategy_evaluation=strategy_evaluation,
            strategy_outcome=None,
        )
        self._persist_job(job)
        return job
    def _evaluate_strategy_candidate(
        self,
        visible_candles: List[Candle],
        buy_time_ms: int,
        horizon_minutes: int,
    ) -> Dict[str, Any]:
        from decimal import Decimal
        from shootingstar.application.entry_strategy import EntryStrategyEngine
        from shootingstar.domain.trade_plan import CandidateState, ObservationDecision, RiskConfig, SymbolFilters

        engine = EntryStrategyEngine()
        symbol = visible_candles[0].symbol if visible_candles else "BTCUSDT"
        symbol_filters = SymbolFilters(
            symbol=symbol,
            tick_size=Decimal("0.01"),
            step_size=Decimal("0.00001"),
            min_notional=Decimal("5.0"),
            min_qty=Decimal("0.00001"),
        )
        risk_config = RiskConfig(
            max_notional_usdt=Decimal("2000.00"),
            max_planned_loss_usdt=Decimal("100.00"),
            fee_rate_bps=Decimal("10.0"),  # VIP 0 10 bps
            slippage_bps=Decimal("5.0"),   # Registered baseline
            max_wait_duration_ms=horizon_minutes * 60 * 1000,
            max_entry_deviation_pct=Decimal("0.002"),
            freshness_tolerance_ms=120000,
            max_event_lag_ms=5000,
            cost_model_source="vip0-doc",
        )

        plan, decision, reasons = engine.create_candidate(
            candles=visible_candles,
            decision_time_ms=buy_time_ms,
            available_cutoff_ms=buy_time_ms,
            symbol_filters=symbol_filters,
            risk_config=risk_config,
        )

        if plan is None:
            return {
                "strategy_version": engine.strategy_version,
                "candidate_state": "NO_SETUP",
                "decision": decision.value,
                "reasons": [r.value for r in reasons],
                "proposed_entry": None,
                "zone_low": None,
                "zone_high": None,
                "target_price": None,
                "stop_price": None,
                "reward_risk_ratio": None,
                "support_level": None,
                "reclaim_level": None,
                "is_trade_eligible": False,
            }
        return {
            "strategy_version": plan.strategy_version,
            "candidate_state": plan.candidate_state.value,
            "decision": decision.value,
            "reasons": [r.value for r in reasons],
            "proposed_entry": float(plan.entry_zone.proposed_entry),
            "zone_low": float(plan.entry_zone.min_price),
            "zone_high": float(plan.entry_zone.max_price),
            "target_price": float(plan.target_price),
            "stop_price": float(plan.stop_price),
            "reward_risk_ratio": float(plan.reward_risk_ratio) if hasattr(plan, "reward_risk_ratio") else float((plan.target_price - plan.proposed_entry) / (plan.proposed_entry - plan.stop_price)),
            "support_level": float(plan.confirmation.support_level),
            "reclaim_level": float(plan.confirmation.reclaim_level),
            "has_setup": True,
            "is_trade_eligible": decision == ObservationDecision.BUY_ELIGIBLE,
        }


    def _evaluate_ai_prediction(
        self,
        visible_candles: List[Candle],
        buy_time_ms: int,
        horizon_minutes: int,
    ) -> SimulationAIPrediction:
        # No trained model exists. Directional AI opinion comes only from the external Gemini
        # report (/external-analysis/jobs), never from this engine.
        return SimulationAIPrediction(
            predicted_direction="NO_MODEL",
            evidence_summary="Không có mô hình tự huấn luyện. Dùng báo cáo phân tích ngoài (external-analysis) để có nhận định AI.",
        )

    def get_job(self, job_id: str) -> SimulationJob:
        job = self._jobs.get(job_id)
        if not job:
            raise DomainError(f"Simulation job {job_id} not found")
        return job

    def record_vote(self, job_id: str, user_direction: str) -> SimulationJob:
        job = self.get_job(job_id)
        if job.user_vote is not None:
            raise DomainError("Lựa chọn của người dùng đã được khóa trước đó, không thể sửa.")

        if user_direction not in ("UP", "DOWN"):
            raise DomainError(f"user_direction must be 'UP' or 'DOWN', got: {user_direction}")

        from datetime import datetime, timezone
        job.user_vote = SimulationUserVote(
            user_direction=user_direction,
            voted_at_utc=datetime.now(timezone.utc).isoformat(),
            is_locked=True,
        )
        job.status = "VOTED"
        self._persist_job(job)
        return job

    def reveal_outcome(self, job_id: str, snapshot_path: Path, *, snapshot_end_ms: Optional[int] = None) -> SimulationJob:
        job = self.get_job(job_id)
        if job.user_vote is None:
            raise DomainError("Phải khóa dự đoán của bạn trước khi xem kết quả thực tế.")

        if job.outcome is not None:
            return job  # Idempotent: already revealed

        target_time_ms = job.buy_time_ms + (job.horizon_minutes * 60 * 1000)
        if snapshot_end_ms is None:
            try:
                _, snapshot_end_ms, _ = self._snapshot_info(snapshot_path)
            except DomainError:
                raise DomainError("Snapshot has no candles") from None
        tf = Timeframe(job.timeframe)
        candles = self.snapshot_storage.load_snapshot_window(
            snapshot_path, start_ms=job.buy_time_ms - tf.duration_ms,
            end_ms=target_time_ms + 3 * tf.duration_ms)
        if not candles:
            import pyarrow.parquet as pq
            if pq.read_metadata(snapshot_path).num_rows == 0:
                raise DomainError("Snapshot has no candles")
        from datetime import datetime, timezone
        now_utc = datetime.now(timezone.utc).isoformat()

        # Check if snapshot covers the horizon
        if snapshot_end_ms < target_time_ms:
            job.outcome = SimulationOutcome(
                status="PENDING",
                horizon_time_ms=target_time_ms,
                unscorable_reason="Snapshot kết thúc trước mốc horizon kết quả.",
                revealed_at_utc=now_utc,
            )
            job.status = "REVEALED"
            self._persist_job(job)
            return job

        # Find target candle
        matching_candles = [c for c in candles if c.open_time_ms <= target_time_ms <= c.close_time_ms]
        if not matching_candles:
            # Look for candle closing closest after target_time_ms
            after_candles = [c for c in candles if c.close_time_ms >= target_time_ms]
            if after_candles and abs(after_candles[0].open_time_ms - target_time_ms) <= 2 * tf.duration_ms:
                c_target = after_candles[0]
            else:
                job.outcome = SimulationOutcome(
                    status="UNSCORABLE",
                    horizon_time_ms=target_time_ms,
                    unscorable_reason="Phát hiện khoảng trống dữ liệu (gap) tại mốc horizon.",
                    revealed_at_utc=now_utc,
                )
                job.status = "REVEALED"
                self._persist_job(job)
                return job
        else:
            c_target = matching_candles[0]

        future_price = c_target.close
        ret = (future_price - job.buy_price) / job.buy_price
        change_pct = ret * 100.0

        if ret > 0:
            market_dir = "UP"
        elif ret < 0:
            market_dir = "DOWN"
        else:
            market_dir = "FLAT"

        ai_ok = (
            (job.ai_prediction.predicted_direction == market_dir)
            if (job.ai_prediction and job.ai_prediction.predicted_direction in ("UP", "DOWN"))
            else None
        )
        user_ok = (job.user_vote.user_direction == market_dir)

        job.outcome = SimulationOutcome(
            status="EVALUATED",
            horizon_time_ms=target_time_ms,
            future_price=future_price,
            price_change_pct=round(change_pct, 4),
            market_direction=market_dir,
            ai_is_correct=ai_ok,
            user_is_correct=user_ok,
            revealed_at_utc=now_utc,
        )
        job.status = "REVEALED"
        # Evaluate barrier strategy outcome causally
        strategy_outcome: Optional[Dict[str, Any]] = None
        strat_eval = job.strategy_evaluation
        if strat_eval and strat_eval.get("is_trade_eligible") and strat_eval.get("proposed_entry"):
            from decimal import Decimal
            from shootingstar.application.barrier_evaluation import FirstTouchLabeler

            proposed_entry = Decimal(str(strat_eval["proposed_entry"]))
            target_price = Decimal(str(strat_eval["target_price"]))
            stop_price = Decimal(str(strat_eval["stop_price"]))

            forward_candles = [
                c for c in candles
                if c.open_time_ms >= job.buy_time_ms and c.open_time_ms < target_time_ms
            ]
            in_horizon_candles = [c for c in forward_candles if (c.close_time_ms + 1) <= target_time_ms]

            entry_triggered = False
            fill_candle_idx = -1
            for idx, c in enumerate(in_horizon_candles):
                if Decimal(str(c.low)) <= proposed_entry <= Decimal(str(c.high)):
                    entry_triggered = True
                    fill_candle_idx = idx
                    break

            if not entry_triggered:
                strategy_outcome = {
                    "trade_executed": False,
                    "reason": "Price never reached proposed entry within horizon window (UNFILLED).",
                    "outcome": "UNFILLED",
                    "net_return_pct": None,
                }
            else:
                labeler = FirstTouchLabeler()
                fill_candle = in_horizon_candles[fill_candle_idx]
                remaining_candles = forward_candles[fill_candle_idx:]

                barrier_res = labeler.evaluate_path(
                    entry_price=proposed_entry,
                    target_price=target_price,
                    stop_price=stop_price,
                    entry_time_ms=fill_candle.open_time_ms,
                    deadline_ms=target_time_ms,
                    candles=remaining_candles,
                    fee_rate_bps=Decimal("10.0"),
                    slippage_bps=Decimal("5.0"),
                    has_quote_depth=False,
                )
                strategy_outcome = {
                    "trade_executed": True,
                    **barrier_res.to_dict(),
                }
        else:
            reason = "No trade-eligible candidate plan at decision time (NO_TRADE)."
            if strat_eval and strat_eval.get("decision") == "WAIT_CONFIRMATION":
                reason = "Candidate pending confirmation (WAIT_CONFIRMATION / NO_TRADE)."
            elif strat_eval and strat_eval.get("decision") == "WATCH_ONLY":
                reason = "Candidate setup confirmed but probability/cost unverified (WATCH_ONLY / NO_TRADE)."
            strategy_outcome = {
                "trade_executed": False,
                "reason": reason,
                "outcome": "NO_TRADE",
                "net_return_pct": None,
            }

        job.strategy_outcome = strategy_outcome
        job.status = "REVEALED"
        self._persist_job(job)
        return job
