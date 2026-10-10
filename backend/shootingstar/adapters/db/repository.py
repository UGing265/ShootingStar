"""Repository implementations for database entities."""

import json
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from shootingstar.adapters.db.models import (
    AuditLogModel,
    CanonicalCandleModel,
    ExperimentModel,
    ExperimentSplitModel,
    ExternalAnalysisJobModel,
    IngestionRunModel,
    LabelRecordModel,
    MetricReportModel,
    ModelArtifactModel,
    PatternHitModel,
    PatternRuleModel,
    RejectedRecordModel,
    ReviewOverrideModel,
    SignalOutcomeModel,
    SignalPredictionModel,
    SnapshotModel,
    LessonModel,
    LessonRevisionModel,
    LessonReviewEventModel,
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

    def list_predictions(self, limit: int = 50) -> List[SignalPredictionModel]:
        stmt = (
            select(SignalPredictionModel)
            .order_by(SignalPredictionModel.prediction_time_ms.desc())
            .limit(limit)
        )
        return list(self.session.scalars(stmt).all())

    def get_unresolved_predictions(self) -> List[SignalPredictionModel]:
        """Returns predictions that have not yet matured to an outcome record."""
        subquery = select(SignalOutcomeModel.signal_id)
        stmt = (
            select(SignalPredictionModel)
            .where(SignalPredictionModel.id.not_in(subquery))
            .order_by(SignalPredictionModel.prediction_time_ms.asc())
        )
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


class ExperimentSplitRepository:
    def __init__(self, session: Session):
        self.session = session

    def save(self, split: ExperimentSplitModel) -> ExperimentSplitModel:
        self.session.add(split)
        self.session.flush()
        return split

    def get_by_experiment_and_type(self, experiment_id: str, split_type: str) -> Optional[ExperimentSplitModel]:
        stmt = select(ExperimentSplitModel).where(
            ExperimentSplitModel.experiment_id == experiment_id,
            ExperimentSplitModel.split_type == split_type,
        )
        return self.session.scalars(stmt).first()


class LabelRecordRepository:
    def __init__(self, session: Session):
        self.session = session

    def save(self, label: LabelRecordModel) -> LabelRecordModel:
        self.session.add(label)
        self.session.flush()
        return label

    def get_labels_for_snapshot(self, snapshot_id: str) -> List[LabelRecordModel]:
        stmt = select(LabelRecordModel).where(LabelRecordModel.snapshot_id == snapshot_id).order_by(LabelRecordModel.time_t_ms.asc())
        return list(self.session.scalars(stmt).all())


class MetricReportRepository:
    def __init__(self, session: Session):
        self.session = session

    def save(self, report: MetricReportModel) -> MetricReportModel:
        self.session.add(report)
        self.session.flush()
        return report

    def get_by_experiment(self, experiment_id: str) -> List[MetricReportModel]:
        stmt = select(MetricReportModel).where(MetricReportModel.experiment_id == experiment_id)
        return list(self.session.scalars(stmt).all())


class ModelArtifactRepository:
    def __init__(self, session: Session):
        self.session = session

    def save(self, artifact: ModelArtifactModel) -> ModelArtifactModel:
        self.session.add(artifact)
        self.session.flush()
        return artifact

    def get_by_id(self, artifact_id: str) -> Optional[ModelArtifactModel]:
        return self.session.get(ModelArtifactModel, artifact_id)

    def get_by_experiment(self, experiment_id: str) -> List[ModelArtifactModel]:
        stmt = select(ModelArtifactModel).where(ModelArtifactModel.experiment_id == experiment_id)
        return list(self.session.scalars(stmt).all())

class ReviewOverrideRepository:
    def __init__(self, session: Session):
        self.session = session

    def save(self, override: ReviewOverrideModel) -> ReviewOverrideModel:
        self.session.add(override)
        self.session.flush()
        return override

    def get_by_signal_id(self, signal_id: str) -> List[ReviewOverrideModel]:
        stmt = select(ReviewOverrideModel).where(ReviewOverrideModel.signal_id == signal_id).order_by(ReviewOverrideModel.created_at.desc())
        return list(self.session.scalars(stmt).all())


class PatternRuleRepository:
    def __init__(self, session: Session):
        self.session = session

    def save(self, rule: PatternRuleModel) -> PatternRuleModel:
        self.session.add(rule)
        self.session.flush()
        return rule

    def get_by_id(self, rule_id: str) -> Optional[PatternRuleModel]:
        return self.session.get(PatternRuleModel, rule_id)

    def list_all(self) -> List[PatternRuleModel]:
        stmt = select(PatternRuleModel).order_by(PatternRuleModel.created_at.asc())
        return list(self.session.scalars(stmt).all())


class PatternHitRepository:
    def __init__(self, session: Session):
        self.session = session

    def save(self, hit: PatternHitModel) -> PatternHitModel:
        self.session.add(hit)
        self.session.flush()
        return hit

    def get_hits_for_rule(self, rule_id: str) -> List[PatternHitModel]:
        stmt = select(PatternHitModel).where(PatternHitModel.rule_id == rule_id).order_by(PatternHitModel.detected_time_ms.asc())
        return list(self.session.scalars(stmt).all())


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


class LessonRepository:
    def __init__(self, session: Session):
        self.session = session

    def save_lesson(self, lesson: LessonModel) -> LessonModel:
        self.session.add(lesson)
        self.session.flush()
        return lesson

    def get_lesson(self, lesson_id: str) -> Optional[LessonModel]:
        return self.session.get(LessonModel, lesson_id)

    def list_lessons_by_status(self, status: Optional[str] = None) -> List[LessonModel]:
        stmt = select(LessonModel)
        if status:
            stmt = stmt.where(LessonModel.status == status)
        stmt = stmt.order_by(LessonModel.created_at.desc())
        return list(self.session.scalars(stmt).all())

    def save_revision(self, rev: LessonRevisionModel) -> LessonRevisionModel:
        self.session.add(rev)
        self.session.flush()
        return rev

    def get_revision(self, revision_id: str) -> Optional[LessonRevisionModel]:
        return self.session.get(LessonRevisionModel, revision_id)

    def list_revisions_for_lesson(self, lesson_id: str) -> List[LessonRevisionModel]:
        stmt = select(LessonRevisionModel).where(LessonRevisionModel.lesson_id == lesson_id).order_by(LessonRevisionModel.revision_number.desc())
        return list(self.session.scalars(stmt).all())

    def save_review_event(self, event: LessonReviewEventModel) -> LessonReviewEventModel:
        self.session.add(event)
        self.session.flush()
        return event

    def list_review_events(self, lesson_id: str) -> List[LessonReviewEventModel]:
        stmt = select(LessonReviewEventModel).where(LessonReviewEventModel.lesson_id == lesson_id).order_by(LessonReviewEventModel.created_at.desc())
        return list(self.session.scalars(stmt).all())
