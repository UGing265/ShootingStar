"""Contracts and data models for external model API analysis."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class AnalysisDirection(str, Enum):
    UP = "UP"
    DOWN = "DOWN"
    ABSTAIN = "ABSTAIN"


class AnalysisStatus(str, Enum):
    PREPARING = "PREPARING"
    CALLING = "CALLING"
    READY = "READY"
    ABSTAIN = "ABSTAIN"
    FAILED = "FAILED"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    UNSCORABLE = "UNSCORABLE"


class ContextVariant(str, Enum):
    A = "A"  # 6 hours of clean ordered OHLCV
    B = "B"  # Deterministic summary features + tail candles


class AnalysisMode(str, Enum):
    RETROSPECTIVE = "RETROSPECTIVE"  # Historical replay (potential lookahead risk)
    PROSPECTIVE = "PROSPECTIVE"      # Forward-looking real-time lock before outcome


@dataclass(frozen=True)
class ModelPredictionOutput:
    direction: AnalysisDirection
    rationale: str
    evidence_candle_times: List[int] = field(default_factory=list)
    lesson_ids: List[str] = field(default_factory=list)
    probability_up: Optional[float] = None  # Strictly None pending probability calibration
    probability_down: Optional[float] = None
    model_id: str = "gemini-2.5-flash"
    prompt_version: str = "v1"
    key_index: Optional[int] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    estimated_cost_usd: Optional[float] = None


@dataclass(frozen=True)
class ExternalAnalysisRequest:
    snapshot_id: str
    prediction_time_t_ms: int
    purchase_price_p: float
    horizon_minutes: int = 30
    context_variant: ContextVariant = ContextVariant.A
    mode: AnalysisMode = AnalysisMode.RETROSPECTIVE


@dataclass
class ExternalAnalysisJobDTO:
    id: str
    snapshot_id: str
    snapshot_hash: str
    symbol: str
    timeframe: str
    prediction_time_t_ms: int
    purchase_price_p: float
    horizon_minutes: int
    mode: str
    context_variant: str
    status: str
    created_at_iso: str
    ai_prediction: Optional[ModelPredictionOutput] = None
    user_vote: Optional[str] = None
    outcome: Optional[str] = None  # Strictly hidden before reveal!
    target_price: Optional[float] = None
    outcome_evaluated_at_ms: Optional[int] = None
    error_message: Optional[str] = None
    leakage_risk_banner: bool = False
