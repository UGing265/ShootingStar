"""SQLAlchemy 2 declarative models for persistence and experiment provenance."""

from datetime import datetime, timezone
import uuid
from typing import Any, Dict, Optional
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, relationship


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class IngestionRunModel(Base):
    __tablename__ = "ingestion_runs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    venue = Column(String(32), nullable=False, default="BINANCE")
    symbol = Column(String(32), nullable=False)
    timeframe = Column(String(16), nullable=False)
    start_time_ms = Column(BigInteger, nullable=False)
    end_time_ms = Column(BigInteger, nullable=False)
    valid_candles_count = Column(Integer, nullable=False)
    missing_intervals_count = Column(Integer, nullable=False, default=0)
    duplicate_candles_count = Column(Integer, nullable=False, default=0)
    coverage_ratio = Column(Float, nullable=False, default=1.0)
    is_pristine = Column(Boolean, nullable=False, default=True)
    raw_files_count = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    snapshots = relationship("SnapshotModel", back_populates="ingestion_run")


class SnapshotModel(Base):
    __tablename__ = "snapshots"

    id = Column(String(64), primary_key=True)  # sha256 hash of snapshot content
    ingestion_run_id = Column(String(36), ForeignKey("ingestion_runs.id"), nullable=True)
    venue = Column(String(32), nullable=False, default="BINANCE")
    symbol = Column(String(32), nullable=False)
    timeframe = Column(String(16), nullable=False)
    start_time_ms = Column(BigInteger, nullable=False)
    end_time_ms = Column(BigInteger, nullable=False)
    candle_count = Column(Integer, nullable=False)
    file_path = Column(String(512), nullable=False)
    sha256 = Column(String(64), nullable=False, unique=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    ingestion_run = relationship("IngestionRunModel", back_populates="snapshots")
    experiments = relationship("ExperimentModel", back_populates="snapshot")


class ExperimentModel(Base):
    __tablename__ = "experiments"

    id = Column(String(64), primary_key=True)  # experiment name or uuid
    name = Column(String(128), nullable=False)
    config_hash = Column(String(64), nullable=False, index=True)
    snapshot_id = Column(String(64), ForeignKey("snapshots.id"), nullable=False)
    parameters_json = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    snapshot = relationship("SnapshotModel", back_populates="experiments")
    artifacts = relationship("ModelArtifactModel", back_populates="experiment")
    predictions = relationship("SignalPredictionModel", back_populates="experiment")


class ModelArtifactModel(Base):
    __tablename__ = "model_artifacts"

    id = Column(String(64), primary_key=True)  # artifact checksum
    experiment_id = Column(String(64), ForeignKey("experiments.id"), nullable=False)
    model_type = Column(String(64), nullable=False)
    artifact_path = Column(String(512), nullable=False)
    artifact_hash = Column(String(64), nullable=False)
    metrics_json = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    experiment = relationship("ExperimentModel", back_populates="artifacts")


class SignalPredictionModel(Base):
    """IMMUTABLE APPEND-ONLY PREDICTION RECORD.
    
    INVARIANT: Once written, never updated or deleted.
    """
    __tablename__ = "signal_predictions"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    prediction_time_ms = Column(BigInteger, nullable=False, index=True)
    experiment_id = Column(String(64), ForeignKey("experiments.id"), nullable=False)
    symbol = Column(String(32), nullable=False)
    timeframe = Column(String(16), nullable=False)
    horizon_minutes = Column(Integer, nullable=False, default=30)
    probability_up = Column(Float, nullable=False)
    probability_down = Column(Float, nullable=False)
    probability_no_trade = Column(Float, nullable=False)
    predicted_class = Column(String(16), nullable=False)  # UP, DOWN, NO_TRADE
    decision = Column(String(16), nullable=False)  # UP, DOWN, NO_TRADE (separate policy decision)
    decision_reason = Column(String(256), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    experiment = relationship("ExperimentModel", back_populates="predictions")
    outcome = relationship("SignalOutcomeModel", back_populates="prediction", uselist=False)


class SignalOutcomeModel(Base):
    """SEPARATE OUTCOME RECORD FOR MATURED SIGNALS."""
    __tablename__ = "signal_outcomes"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    signal_id = Column(String(64), ForeignKey("signal_predictions.id"), nullable=False, unique=True)
    status = Column(String(24), nullable=False)  # EVALUATED, UNSCORABLE
    evaluated_at_ms = Column(BigInteger, nullable=False)
    realized_return = Column(Float, nullable=True)
    realized_label = Column(String(16), nullable=True)
    is_match = Column(Boolean, nullable=True)
    unscorable_reason = Column(String(256), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    prediction = relationship("SignalPredictionModel", back_populates="outcome")


class PatternRuleModel(Base):
    __tablename__ = "pattern_rules"

    id = Column(String(64), primary_key=True)
    name = Column(String(64), nullable=False)
    version = Column(Integer, nullable=False, default=1)
    description = Column(Text, nullable=False)
    definition_json = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    hits = relationship("PatternHitModel", back_populates="rule")


class PatternHitModel(Base):
    __tablename__ = "pattern_hits"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    rule_id = Column(String(64), ForeignKey("pattern_rules.id"), nullable=False)
    detected_time_ms = Column(BigInteger, nullable=False, index=True)
    symbol = Column(String(32), nullable=False)
    timeframe = Column(String(16), nullable=False)
    outcome_return_30m = Column(Float, nullable=True)
    outcome_label = Column(String(16), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    rule = relationship("PatternRuleModel", back_populates="hits")


class AuditLogModel(Base):
    __tablename__ = "audit_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    entity_type = Column(String(64), nullable=False, index=True)
    entity_id = Column(String(64), nullable=False, index=True)
    action = Column(String(64), nullable=False)
    details_json = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
