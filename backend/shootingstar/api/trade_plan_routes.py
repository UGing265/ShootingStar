"""API endpoints for trade watcher lifecycle and barrier plan execution."""

import json
import os
from decimal import Decimal
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel

from shootingstar.adapters.binance_market_events import BinanceMarketEventsClient
from shootingstar.adapters.db.repository import (
    CandidatePlanRepository,
    TradeObservationRepository,
    TradeWatchRepository,
)
from shootingstar.adapters.db.session import get_db_session
from shootingstar.api.schemas import (
    CandidatePlanResponse,
    EntryObservationRequest,
    ExitObservationRequest,
    TradeObservationResponse,
    TradeWatchCreateRequest,
    TradeWatchResponse,
)
from shootingstar.application.trade_watch import (
    ActiveReservationConflictError,
    ExecutionModeMismatchError,
    TradeWatchService,
    TradeWatchServiceError,
)
from shootingstar.domain.trade_plan import (
    CandidateState,
    ExecutionMode,
    ExitReason,
    RiskConfig,
    SymbolFilters,
)

router = APIRouter(prefix="", tags=["Trade Watch & Plans"])

DEFAULT_OPERATOR_ID = "local_admin"


def verify_admin_key(x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key")) -> str:
    """Strict server-side administrator gating.
    Fails closed if SHOOTINGSTAR_ADMIN_KEY is unset or key does not match.
    """
    expected_key = os.environ.get("SHOOTINGSTAR_ADMIN_KEY", "").strip()
    if not expected_key or not x_admin_key or x_admin_key != expected_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator authentication required via X-Admin-Key header.",
        )
    return DEFAULT_OPERATOR_ID


@router.post("/trade-watches", response_model=TradeWatchResponse, status_code=status.HTTP_201_CREATED)
def create_trade_watch(
    req: TradeWatchCreateRequest,
    operator_id: str = Depends(verify_admin_key),
):
    """Creates a new trade watch session, strictly enforcing single active exposure reservation."""
    with get_db_session() as session:
        watch_repo = TradeWatchRepository(session)
        cand_repo = CandidatePlanRepository(session)
        obs_repo = TradeObservationRepository(session)
        service = TradeWatchService(watch_repo, cand_repo, obs_repo)

        # Parse symbol filters dynamically from exchangeInfo client
        events_client = BinanceMarketEventsClient()
        try:
            symbol_filters = events_client.fetch_symbol_filters(req.symbol)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to fetch exchange filters for {req.symbol}: {exc}",
            )

        risk_config = RiskConfig(
            max_notional_usdt=req.max_notional_usdt,
            max_planned_loss_usdt=req.max_planned_loss_usdt,
            fee_rate_bps=req.fee_rate_bps,
            slippage_bps=req.slippage_bps,
            max_wait_duration_ms=req.max_wait_duration_ms,
            max_entry_deviation_pct=req.max_entry_deviation_pct,
            freshness_tolerance_ms=req.freshness_tolerance_ms,
            max_event_lag_ms=req.max_event_lag_ms,
            cost_model_source=req.cost_model_source,
        )

        try:
            watch = service.start_watch(
                operator_id=operator_id,
                symbol=req.symbol,
                risk_config=risk_config,
                symbol_filters=symbol_filters,
                strategy_version=req.strategy_version,
            )
        except ActiveReservationConflictError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(exc),
            )

        return TradeWatchResponse(
            id=watch.id,
            operator_id=watch.operator_id,
            symbol=watch.symbol,
            status=watch.status,
            position_state=watch.position_state,
            strategy_version=watch.strategy_version,
            risk_config=json.loads(watch.risk_config_json),
            symbol_filters=json.loads(watch.symbol_filters_json),
            active_candidate_id=watch.active_candidate_id,
            execution_mode=watch.execution_mode,
            opened_at_ms=watch.opened_at_ms,
            deadline_ms=watch.deadline_ms,
            closed_at_ms=watch.closed_at_ms,
            created_at=watch.created_at.isoformat(),
            updated_at=watch.updated_at.isoformat(),
        )


@router.get("/trade-watches/{watch_id}", response_model=TradeWatchResponse)
def get_trade_watch(
    watch_id: str,
    _: str = Depends(verify_admin_key),
):
    with get_db_session() as session:
        watch_repo = TradeWatchRepository(session)
        watch = watch_repo.get_by_id(watch_id)
        if not watch:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Watch {watch_id} not found.")

        return TradeWatchResponse(
            id=watch.id,
            operator_id=watch.operator_id,
            symbol=watch.symbol,
            status=watch.status,
            position_state=watch.position_state,
            strategy_version=watch.strategy_version,
            risk_config=json.loads(watch.risk_config_json),
            symbol_filters=json.loads(watch.symbol_filters_json),
            active_candidate_id=watch.active_candidate_id,
            execution_mode=watch.execution_mode,
            opened_at_ms=watch.opened_at_ms,
            deadline_ms=watch.deadline_ms,
            closed_at_ms=watch.closed_at_ms,
            created_at=watch.created_at.isoformat(),
            updated_at=watch.updated_at.isoformat(),
        )


@router.post("/trade-watches/{watch_id}/stop", response_model=TradeWatchResponse)
def stop_trade_watch(
    watch_id: str,
    _: str = Depends(verify_admin_key),
):
    with get_db_session() as session:
        watch_repo = TradeWatchRepository(session)
        cand_repo = CandidatePlanRepository(session)
        obs_repo = TradeObservationRepository(session)
        service = TradeWatchService(watch_repo, cand_repo, obs_repo)
        try:
            watch = service.stop_watch(watch_id)
        except TradeWatchServiceError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

        return TradeWatchResponse(
            id=watch.id,
            operator_id=watch.operator_id,
            symbol=watch.symbol,
            status=watch.status,
            position_state=watch.position_state,
            strategy_version=watch.strategy_version,
            risk_config=json.loads(watch.risk_config_json),
            symbol_filters=json.loads(watch.symbol_filters_json),
            active_candidate_id=watch.active_candidate_id,
            execution_mode=watch.execution_mode,
            opened_at_ms=watch.opened_at_ms,
            deadline_ms=watch.deadline_ms,
            closed_at_ms=watch.closed_at_ms,
            created_at=watch.created_at.isoformat(),
            updated_at=watch.updated_at.isoformat(),
        )


@router.get("/trade-plans/{candidate_id}", response_model=CandidatePlanResponse)
def get_candidate_plan(
    candidate_id: str,
    _: str = Depends(verify_admin_key),
):
    with get_db_session() as session:
        cand_repo = CandidatePlanRepository(session)
        obs_repo = TradeObservationRepository(session)

        plan = cand_repo.get_by_id(candidate_id)
        if not plan:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Candidate plan {candidate_id} not found.")

        observations = obs_repo.list_by_candidate_id(candidate_id)
        obs_dtos = [
            TradeObservationResponse(
                id=o.id,
                idempotency_key=o.idempotency_key,
                candidate_id=o.candidate_id,
                watch_id=o.watch_id,
                observation_type=o.observation_type,
                mode=o.mode,
                price=float(o.price),
                quantity=float(o.quantity),
                remaining_quantity=float(o.remaining_quantity) if o.remaining_quantity is not None else None,
                fees_paid=float(o.fees_paid),
                actual_time_ms=o.actual_time_ms,
                receipt_time_ms=o.receipt_time_ms,
                is_off_plan=o.is_off_plan,
                is_risk_breach=o.is_risk_breach,
                reconciled_sl_breach=o.reconciled_sl_breach,
                exit_reason=o.exit_reason,
                realized_pnl_usdt=float(o.realized_pnl_usdt) if o.realized_pnl_usdt is not None else None,
                notes=o.notes,
                created_at=o.created_at.isoformat(),
            )
            for o in observations
        ]

        return CandidatePlanResponse(
            id=plan.id,
            watch_id=plan.watch_id,
            strategy_version=plan.strategy_version,
            rule_config_hash=plan.rule_config_hash,
            decision_time_ms=plan.decision_time_ms,
            available_cutoff_ms=plan.available_cutoff_ms,
            entry_zone=json.loads(plan.entry_zone_json),
            confirmation=json.loads(plan.confirmation_json),
            invalidation=json.loads(plan.invalidation_json),
            stop_price=float(plan.stop_price),
            target_price=float(plan.target_price),
            wait_expires_at_ms=plan.wait_expires_at_ms,
            horizon_ms=plan.horizon_ms,
            probability=json.loads(plan.probability_json) if plan.probability_json else None,
            reasons=json.loads(plan.reasons_json) if plan.reasons_json else [],
            candidate_state=plan.candidate_state,
            observations=obs_dtos,
            created_at=plan.created_at.isoformat(),
        )


@router.post("/trade-plans/{candidate_id}/entry-observations", response_model=TradeObservationResponse, status_code=status.HTTP_201_CREATED)
def record_entry_observation(
    candidate_id: str,
    req: EntryObservationRequest,
    _: str = Depends(verify_admin_key),
):
    import time
    receipt_time = int(time.time() * 1000)

    with get_db_session() as session:
        watch_repo = TradeWatchRepository(session)
        cand_repo = CandidatePlanRepository(session)
        obs_repo = TradeObservationRepository(session)
        service = TradeWatchService(watch_repo, cand_repo, obs_repo)

        plan = cand_repo.get_by_id(candidate_id)
        if not plan:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Candidate {candidate_id} not found.")

        watch_id = plan.watch_id
        if not watch_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Candidate not attached to an active watch.")

        try:
            mode_enum = ExecutionMode(req.mode)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Invalid mode {req.mode}.")

        try:
            _, obs = service.record_entry(
                watch_id=watch_id,
                candidate_id=candidate_id,
                mode=mode_enum,
                price=req.price,
                quantity=req.quantity,
                actual_entry_time_ms=req.actual_entry_time_ms,
                receipt_time_ms=receipt_time,
                idempotency_key=req.idempotency_key,
                recent_lowest_price_since_entry=req.recent_lowest_price,
                notes=req.notes,
            )
        except ActiveReservationConflictError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
        except TradeWatchServiceError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

        return TradeObservationResponse(
            id=obs.id,
            idempotency_key=obs.idempotency_key,
            candidate_id=obs.candidate_id,
            watch_id=obs.watch_id,
            observation_type=obs.observation_type,
            mode=obs.mode,
            price=float(obs.price),
            quantity=float(obs.quantity),
            remaining_quantity=float(obs.remaining_quantity) if obs.remaining_quantity is not None else None,
            fees_paid=float(obs.fees_paid),
            actual_time_ms=obs.actual_time_ms,
            receipt_time_ms=obs.receipt_time_ms,
            is_off_plan=obs.is_off_plan,
            is_risk_breach=obs.is_risk_breach,
            reconciled_sl_breach=obs.reconciled_sl_breach,
            exit_reason=obs.exit_reason,
            realized_pnl_usdt=float(obs.realized_pnl_usdt) if obs.realized_pnl_usdt is not None else None,
            notes=obs.notes,
            created_at=obs.created_at.isoformat(),
        )


@router.post("/trade-plans/{candidate_id}/exit-observations", response_model=TradeObservationResponse, status_code=status.HTTP_201_CREATED)
def record_exit_observation(
    candidate_id: str,
    req: ExitObservationRequest,
    _: str = Depends(verify_admin_key),
):
    import time
    receipt_time = int(time.time() * 1000)

    with get_db_session() as session:
        watch_repo = TradeWatchRepository(session)
        cand_repo = CandidatePlanRepository(session)
        obs_repo = TradeObservationRepository(session)
        service = TradeWatchService(watch_repo, cand_repo, obs_repo)

        plan = cand_repo.get_by_id(candidate_id)
        if not plan:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Candidate {candidate_id} not found.")

        watch_id = plan.watch_id
        if not watch_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Candidate not attached to an active watch.")

        try:
            mode_enum = ExecutionMode(req.mode)
            exit_reason_enum = ExitReason(req.exit_reason)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

        try:
            _, obs = service.record_exit(
                watch_id=watch_id,
                candidate_id=candidate_id,
                mode=mode_enum,
                price=req.price,
                quantity=req.quantity,
                exit_reason=exit_reason_enum,
                actual_exit_time_ms=req.actual_exit_time_ms,
                receipt_time_ms=receipt_time,
                idempotency_key=req.idempotency_key,
                notes=req.notes,
            )
        except ExecutionModeMismatchError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
        except TradeWatchServiceError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

        return TradeObservationResponse(
            id=obs.id,
            idempotency_key=obs.idempotency_key,
            candidate_id=obs.candidate_id,
            watch_id=obs.watch_id,
            observation_type=obs.observation_type,
            mode=obs.mode,
            price=float(obs.price),
            quantity=float(obs.quantity),
            remaining_quantity=float(obs.remaining_quantity) if obs.remaining_quantity is not None else None,
            fees_paid=float(obs.fees_paid),
            actual_time_ms=obs.actual_time_ms,
            receipt_time_ms=obs.receipt_time_ms,
            is_off_plan=obs.is_off_plan,
            is_risk_breach=obs.is_risk_breach,
            reconciled_sl_breach=obs.reconciled_sl_breach,
            exit_reason=obs.exit_reason,
            realized_pnl_usdt=float(obs.realized_pnl_usdt) if obs.realized_pnl_usdt is not None else None,
            notes=obs.notes,
            created_at=obs.created_at.isoformat(),
        )
