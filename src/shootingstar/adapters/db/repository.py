"""Repository implementations for database entities."""

import json
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from shootingstar.adapters.db.models import (
    AuditLogModel,
    ExperimentModel,
    IngestionRunModel,
    ModelArtifactModel,
    SignalOutcomeModel,
    SignalPredictionModel,
    SnapshotModel,
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


class ExperimentRepository:
    def __init__(self, session: Session):
        self.session = session

    def save(self, experiment: ExperimentModel) -> ExperimentModel:
        self.session.add(experiment)
        self.session.flush()
        return experiment

    def get_by_id(self, experiment_id: str) -> Optional[ExperimentModel]:
        return self.session.get(ExperimentModel, experiment_id)

    def list_all(self, limit: int = 50) -> List[ExperimentModel]:
        stmt = select(ExperimentModel).order_by(ExperimentModel.created_at.desc()).limit(limit)
        return list(self.session.scalars(stmt).all())


class SignalRepository:
    def __init__(self, session: Session):
        self.session = session

    def save_prediction(self, prediction: SignalPredictionModel) -> SignalPredictionModel:
        """Saves an immutable append-only prediction record."""
        self.session.add(prediction)
        self.session.flush()
        return prediction

    def get_prediction_by_id(self, prediction_id: str) -> Optional[SignalPredictionModel]:
        return self.session.get(SignalPredictionModel, prediction_id)

    def save_outcome(self, outcome: SignalOutcomeModel) -> SignalOutcomeModel:
        """Appends a separate outcome maturation record linked to a prediction."""
        self.session.add(outcome)
        self.session.flush()
        return outcome

    def get_outcome_by_signal_id(self, signal_id: str) -> Optional[SignalOutcomeModel]:
        stmt = select(SignalOutcomeModel).where(SignalOutcomeModel.signal_id == signal_id)
        return self.session.scalars(stmt).first()


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
