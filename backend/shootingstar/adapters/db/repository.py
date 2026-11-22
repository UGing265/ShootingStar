"""Repository implementations for database entities."""

import json
from typing import Any, Dict, List, Optional
from sqlalchemy import and_, or_, select, update
from sqlalchemy.orm import Session

from shootingstar.adapters.db.models import (
    AuditLogModel,
    CanonicalCandleModel,
    ExternalAnalysisJobModel,
    IngestionRunModel,
    RejectedRecordModel,
    SnapshotModel,
    TradeWatchModel,
    CandidatePlanModel,
    TradeObservationModel,
)


class IngestionRunRepository:
    def __init__(self, session: Session):
        self.session = session

    def save(self, run: IngestionRunModel) -> IngestionRunModel:
        self.session.add(run)
        self.session.flush()
        return run

    def get_by_id(self, run_id: str) -> Optional[IngestionRunModel]:
        return self.session.get(IngestionRunModel, run_id)

    def list_all(self, limit: int = 50) -> List[IngestionRunModel]:
        stmt = select(IngestionRunModel).order_by(IngestionRunModel.created_at.desc()).limit(limit)
        return list(self.session.scalars(stmt).all())


class SnapshotRepository:
    def __init__(self, session: Session):
        self.session = session

    def save(self, snapshot: SnapshotModel) -> SnapshotModel:
        self.session.add(snapshot)
        self.session.flush()
        return snapshot

    def get_by_id(self, snapshot_id: str) -> Optional[SnapshotModel]:
        return self.session.get(SnapshotModel, snapshot_id)

    def get_by_sha256(self, sha256_hash: str) -> Optional[SnapshotModel]:
        stmt = select(SnapshotModel).where(SnapshotModel.sha256 == sha256_hash)
        return self.session.scalars(stmt).first()

    def list_all(self, limit: int = 50) -> List[SnapshotModel]:
        stmt = select(SnapshotModel).order_by(SnapshotModel.created_at.desc()).limit(limit)
        return list(self.session.scalars(stmt).all())


class AuditLogRepository:
    def __init__(self, session: Session):
        self.session = session

    def record(self, entity_type: str, entity_id: str, action: str, details: Dict[str, Any]) -> AuditLogModel:
        log = AuditLogModel(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            details_json=json.dumps(details),
        )
        self.session.add(log)
        self.session.flush()
        return log


class CanonicalCandleRepository:
    def __init__(self, session: Session):
        self.session = session

    def save(self, candle: CanonicalCandleModel) -> CanonicalCandleModel:
        self.session.add(candle)
        self.session.flush()
        return candle

    def get_range(self, venue: str, symbol: str, timeframe: str, start_ms: int, end_ms: int) -> List[CanonicalCandleModel]:
        stmt = (
            select(CanonicalCandleModel)
            .where(
                CanonicalCandleModel.venue == venue,
                CanonicalCandleModel.symbol == symbol,
                CanonicalCandleModel.timeframe == timeframe,
                CanonicalCandleModel.open_time_ms >= start_ms,
                CanonicalCandleModel.close_time_ms <= end_ms,
            )
            .order_by(CanonicalCandleModel.open_time_ms.asc())
        )
        return list(self.session.scalars(stmt).all())


class RejectedRecordRepository:
    def __init__(self, session: Session):
        self.session = session

    def record_rejection(
        self,
        venue: str,
        symbol: str,
        timeframe: str,
        rejection_reason: str,
        raw_payload_preview: str,
        ingested_at_ms: int,
        timestamp_ms: Optional[int] = None,
    ) -> RejectedRecordModel:
        rej = RejectedRecordModel(
            venue=venue,
            symbol=symbol,
            timeframe=timeframe,
            timestamp_ms=timestamp_ms,
            rejection_reason=rejection_reason,
            raw_payload_preview=raw_payload_preview,
            ingested_at_ms=ingested_at_ms,
        )
        self.session.add(rej)
        self.session.flush()
        return rej


class ExternalAnalysisJobRepository:
    def __init__(self, session: Session):
        self.session = session

    def save(self, job: ExternalAnalysisJobModel) -> ExternalAnalysisJobModel:
        self.session.add(job)
        self.session.flush()
        return job

    def get_by_id(self, job_id: str) -> Optional[ExternalAnalysisJobModel]:
        return self.session.get(ExternalAnalysisJobModel, job_id)

    def list_jobs(self, limit: int = 20) -> List[ExternalAnalysisJobModel]:
        stmt = select(ExternalAnalysisJobModel).order_by(ExternalAnalysisJobModel.created_at.desc()).limit(limit)
        return list(self.session.scalars(stmt).all())


class TradeWatchRepository:
    def __init__(self, session: Session):
        self.session = session

    def save(self, watch: TradeWatchModel) -> TradeWatchModel:
        self.session.add(watch)
        self.session.flush()
        return watch

    def get_by_id(self, watch_id: str) -> Optional[TradeWatchModel]:
        return self.session.get(TradeWatchModel, watch_id)

    def find_active_reservation(self, operator_id: str, symbol: str) -> Optional[TradeWatchModel]:
        """Finds active watch holding exposure OR active watching session for operator and symbol."""
        stmt = select(TradeWatchModel).where(
            TradeWatchModel.operator_id == operator_id,
            TradeWatchModel.symbol == symbol,
            or_(
                TradeWatchModel.status == "WATCHING",
                TradeWatchModel.position_state.in_(["OPEN", "EXIT_REQUIRED"]),
            ),
        )
        return self.session.scalars(stmt).first()

    def acquire_or_renew_lease(
        self,
        watch_id: str,
        worker_id: str,
        lease_token: str,
        lease_ttl_ms: int,
        current_time_ms: int,
    ) -> bool:
        """Atomic Compare-And-Swap (CAS) lease update with fencing token."""
        stmt = (
            update(TradeWatchModel)
            .where(
                TradeWatchModel.id == watch_id,
                or_(
                    TradeWatchModel.lease_expires_at_ms.is_(None),
                    TradeWatchModel.lease_expires_at_ms < current_time_ms,
                    and_(
                        TradeWatchModel.lease_owner == worker_id,
                        TradeWatchModel.lease_token == lease_token,
                    ),
                ),
            )
            .values(
                lease_owner=worker_id,
                lease_token=lease_token,
                lease_expires_at_ms=current_time_ms + lease_ttl_ms,
            )
        )
        result = self.session.execute(stmt)
        self.session.flush()
        return result.rowcount > 0

class CandidatePlanRepository:
    def __init__(self, session: Session):
        self.session = session

    def save(self, plan: CandidatePlanModel) -> CandidatePlanModel:
        self.session.add(plan)
        self.session.flush()
        return plan

    def get_by_id(self, candidate_id: str) -> Optional[CandidatePlanModel]:
        return self.session.get(CandidatePlanModel, candidate_id)

    def list_by_watch_id(self, watch_id: str) -> List[CandidatePlanModel]:
        stmt = (
            select(CandidatePlanModel)
            .where(CandidatePlanModel.watch_id == watch_id)
            .order_by(CandidatePlanModel.created_at.desc())
        )
        return list(self.session.scalars(stmt).all())


class TradeObservationRepository:
    def __init__(self, session: Session):
        self.session = session

    def save(self, obs: TradeObservationModel) -> TradeObservationModel:
        """Saves observation with strict idempotency by idempotency_key."""
        existing = self.get_by_idempotency_key(obs.idempotency_key)
        if existing is not None:
            return existing
        self.session.add(obs)
        self.session.flush()
        return obs

    def get_by_idempotency_key(self, key: str) -> Optional[TradeObservationModel]:
        stmt = select(TradeObservationModel).where(TradeObservationModel.idempotency_key == key)
        return self.session.scalars(stmt).first()

    def list_by_candidate_id(self, candidate_id: str) -> List[TradeObservationModel]:
        stmt = (
            select(TradeObservationModel)
            .where(TradeObservationModel.candidate_id == candidate_id)
            .order_by(TradeObservationModel.actual_time_ms.asc())
        )
        return list(self.session.scalars(stmt).all())
