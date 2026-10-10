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
    PREPARING_FEED = "PREPARING_FEED"
    ANALYZING = "ANALYZING"
    RESEARCHING = "RESEARCHING"
    MATCHING = "MATCHING"
    SYNTHESIZING = "SYNTHESIZING"
    CALLING = "CALLING"
    READY = "READY"
    ABSTAIN = "ABSTAIN"
    RESEARCH_INCOMPLETE = "RESEARCH_INCOMPLETE"
    FAILED = "FAILED"
    FAILED_INTERRUPTED = "FAILED_INTERRUPTED"
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
class FeedCoverage:
    required_span_ms: int
    observed_span_ms: int
    gaps_count: int
    invalid_rows_count: int
    status: str  # "COMPLETE" | "INSUFFICIENT_HISTORY"


@dataclass(frozen=True)
class FeedFeature:
    feature_id: str
    value: float
    unit: str
    formula_version: str
    source_candle_ids: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class FeedCandle:
    candle_id: str
    open_time_ms: int
    close_time_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class FeedContract:
    feed_id: str
    feed_version: str
    feed_hash: str
    snapshot_id: str
    snapshot_checksum: str
    symbol: str
    timeframe: str
    prediction_time_t_ms: int
    purchase_price_p: float
    horizon_minutes: int
    context_start_open_time_ms: int
    context_end_close_time_ms: int
    assumed_latency_ms: int
    candles: List[FeedCandle]
    coverage: FeedCoverage
    features: List[FeedFeature]


@dataclass(frozen=True)
class HypothesisObservation:
    claim_id: str
    description: str
    feature_ids: List[str] = field(default_factory=list)
    candle_ids: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class HypothesisCandidate:
    pattern_name: str
    candle_ids: List[str]
    rationale: str
    unresolved_context: str


@dataclass(frozen=True)
class HypothesisContract:
    hypothesis_id: str
    feed_id: str
    feed_hash: str
    observations: List[HypothesisObservation]
    candidates: List[HypothesisCandidate]
    missing_information: List[str] = field(default_factory=list)
    questions_for_research: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class PatternCriterion:
    criterion_id: str
    description: str
    source_id_or_locator: str
    rule_origin: str  # "SOURCE_EXPLICIT" | "SYSTEM_OPERATIONAL"
    formula_or_params: str
    measured_value: float
    expected_relation: str
    status: str  # "PASS" | "FAIL" | "UNKNOWN"
    reason: str


@dataclass(frozen=True)
class PatternDiagnosticContract:
    pattern_id: str
    candidate_id: str
    rule_version: str
    feed_hash: str
    candle_ids: List[str]
    criteria: List[PatternCriterion]
    shape_status: str  # "PASS" | "FAIL" | "UNKNOWN"
    context_status: str  # "PASS" | "FAIL" | "UNKNOWN"
    confirmation_status: str  # "PASS" | "FAIL" | "UNKNOWN" | "CHỜ_XÁC_NHẬN"
    overall_match_status: str  # "KHỚP_THEO_RULE_VERSION" | "KHÔNG_KHỚP" | "CHƯA_ĐỦ_TIÊU_CHÍ"
    conflicts: List[str] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)
    predictive_evidence_status: str = "PATTERN_SHAPE_ONLY_NO_FUTURE_RETURN_CLAIM"


@dataclass(frozen=True)
class ResearchSource:
    source_id: str
    url: str
    title: str
    author_or_publisher: str
    source_type: str  # "GLOSSARY" | "ACADEMIC" | "PRACTITIONER" | "WEB_SEARCH"
    publication_date_or_unknown: str
    access_status: str  # "ACCESSIBLE" | "FAILED" | "PAYWALL" | "SNIPPET_ONLY"
    section_locator: str
    excerpt: str
    content_hash: str
    tool_trace_id: str
    review_status: str = "JOB_PRIVATE_EVIDENCE"


@dataclass(frozen=True)
class ResearchDefinition:
    pattern_name: str
    criterion_ids: List[str]
    source_ids: List[str]
    required_context: str
    required_confirmation: str
    scope_and_limitations: str


@dataclass(frozen=True)
class ResearchAgentContract:
    research_id: str
    job_id: str
    feed_hash: str
    search_provider: str
    queries_executed: List[str]
    query_receipts: List[Dict[str, Any]]
    retrieved_at_iso: str
    sources: List[ResearchSource]
    pattern_definitions: List[ResearchDefinition]
    contradictory_sources_or_facts: List[str]
    unresolved_questions: List[str]
    research_status: str  # "COMPLETE" | "PARTIAL" | "INSUFFICIENT"


@dataclass(frozen=True)
class StageRecord:
    stage_name: str
    role: str
    status: str  # "PENDING" | "RUNNING" | "COMPLETED" | "FAILED" | "SKIPPED"
    started_at_iso: Optional[str] = None
    ended_at_iso: Optional[str] = None
    model: Optional[str] = None
    prompt_version: Optional[str] = None
    input_hash: Optional[str] = None
    output_hash: Optional[str] = None
    usage: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@dataclass(frozen=True)
class EvidenceEnvelope:
    protocol_version: str = "evidence-pipeline-v1"
    feed: Optional[Dict[str, Any]] = None
    stages: List[Dict[str, Any]] = field(default_factory=list)
    hypothesis: Optional[Dict[str, Any]] = None
    research: Optional[Dict[str, Any]] = None
    diagnostics: List[Dict[str, Any]] = field(default_factory=list)
    report_sections: Optional[Dict[str, Any]] = None
    final_direction: Optional[str] = None
    probability_up: Optional[float] = None
    probability_down: Optional[float] = None

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
    evidence_envelope: Optional[Dict[str, Any]] = None
    stages: Optional[List[Dict[str, Any]]] = None
