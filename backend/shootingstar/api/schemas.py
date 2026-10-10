"""Pydantic schemas for ShootingStar read contracts.

Strict security invariant: No credentials, raw file paths, raw payloads,
or sensitive internal details are exposed in API responses.
"""

from decimal import Decimal
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    database: str
    database_status: str
    engine: str = "PostgreSQL"
    timestamp_utc: str


class IngestionRunSummary(BaseModel):
    id: str
    venue: str
    symbol: str
    timeframe: str
    start_time_ms: int
    end_time_ms: int
    valid_candles_count: int
    missing_intervals_count: int
    duplicate_candles_count: int
    coverage_ratio: float
    is_pristine: bool
    raw_files_count: int
    created_at: str


class SnapshotSummary(BaseModel):
    id: str
    ingestion_run_id: Optional[str] = None
    venue: str
    symbol: str
    timeframe: str
    candle_count: int
    start_time_ms: int
    end_time_ms: int
    sha256: str
    created_at: str


class SnapshotQualityResponse(BaseModel):
    snapshot_id: str
    sha256: str
    venue: str
    symbol: str
    timeframe: str
    candle_count: int
    start_time_ms: int
    end_time_ms: int
    ingestion_run_id: Optional[str] = None
    coverage_ratio: Optional[float] = None
    missing_intervals_count: Optional[int] = None
    duplicate_candles_count: Optional[int] = None
    is_pristine: Optional[bool] = None
    quality_status: str
    gap_list_status: str = "UNAVAILABLE_NOT_PERSISTED"
    missing_timestamps: List[int] = Field(default_factory=list)
    created_at: str


class CandleDTO(BaseModel):
    open_time_ms: int
    close_time_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    quote_volume: float
    trades_count: int


class ExperimentSummary(BaseModel):
    id: str
    name: str
    config_hash: str
    snapshot_id: str
    parameters: Dict[str, Any]
    created_at: str


class ExperimentSplitDTO(BaseModel):
    id: str
    split_type: str
    start_time_ms: int
    end_time_ms: int
    sample_count: int


class ModelArtifactDTO(BaseModel):
    id: str
    model_type: str
    artifact_hash: str
    created_at: str


class CalibrationBinDTO(BaseModel):
    bin_index: int
    bin_range: str
    sample_count: int
    mean_predicted_prob: float
    empirical_frequency: float


class CalibrationReportDTO(BaseModel):
    bins: List[CalibrationBinDTO] = Field(default_factory=list)


class MetricReportDTO(BaseModel):
    id: str
    split_type: str
    report_type: str
    metrics: Dict[str, Any]
    calibration: Optional[CalibrationReportDTO] = None
    created_at: str


class ExperimentDetailResponse(BaseModel):
    id: str
    name: str
    config_hash: str
    snapshot_id: str
    snapshot_sha256: Optional[str] = None
    parameters: Dict[str, Any]
    created_at: str
    splits: List[ExperimentSplitDTO]
    artifacts: List[ModelArtifactDTO] = Field(default_factory=list)
    reports: List[MetricReportDTO] = Field(default_factory=list)

class PatternRuleDTO(BaseModel):
    id: str
    name: str
    version: int
    description: str
    definition: Dict[str, Any]
    created_at: str


class PatternHitDTO(BaseModel):
    id: str
    rule_id: str
    detected_time_ms: int
    symbol: str
    timeframe: str
    outcome_return_30m: Optional[float] = None
    outcome_label: Optional[str] = None
    created_at: str


class SignalSummary(BaseModel):
    id: str
    prediction_time_ms: int
    symbol: str
    timeframe: str
    horizon_minutes: int
    predicted_class: str
    decision: str
    decision_reason: str
    probability_up: float
    probability_down: float
    probability_no_trade: float
    status: str
    realized_label: Optional[str] = None
    realized_return: Optional[float] = None
    is_match: Optional[bool] = None
    unscorable_reason: Optional[str] = None
    created_at: str


class SignalPredictionDTO(BaseModel):
    id: str
    prediction_time_ms: int
    experiment_id: str
    symbol: str
    timeframe: str
    horizon_minutes: int
    probability_up: float
    probability_down: float
    probability_no_trade: float
    predicted_class: str
    decision: str
    decision_reason: str
    created_at: str


class SignalOutcomeDTO(BaseModel):
    id: str
    status: str
    evaluated_at_ms: int
    realized_return: Optional[float] = None
    realized_label: Optional[str] = None
    is_match: Optional[bool] = None
    unscorable_reason: Optional[str] = None
    created_at: str


class ReviewOverrideDTO(BaseModel):
    id: str
    reviewer_id: str
    override_decision: str
    notes: str
    created_at: str


class AuditLogDTO(BaseModel):
    id: int
    action: str
    details: Dict[str, Any]
    created_at: str


class SignalDetailResponse(BaseModel):
    prediction: SignalPredictionDTO
    outcome: Optional[SignalOutcomeDTO] = None
    reviews: List[ReviewOverrideDTO] = Field(default_factory=list)
    audit_logs: List[AuditLogDTO] = Field(default_factory=list)


class PreviewIngestionRequest(BaseModel):
    symbol: str = "BTCUSDT"
    timeframe: str = "1m"
    start_time_ms: int
    end_time_ms: int


class PreviewIngestionResponse(BaseModel):
    symbol: str
    timeframe: str
    start_time_ms: int
    end_time_ms: int
    estimated_candle_count: int
    sampled_candles_count: int
    data_source: str = "Binance Spot REST API (GET /api/v3/klines)"
    is_bounded: bool = True
    quality_status: str
    sample_candles: List[CandleDTO] = Field(default_factory=list)
    preview_token: str


class CreateIngestionJobRequest(BaseModel):
    symbol: str = "BTCUSDT"
    timeframe: str = "1m"
    start_time_ms: int
    end_time_ms: int
    preview_token: str
class IngestionJobResponse(BaseModel):
    job_id: str
    symbol: str
    timeframe: str
    start_time_ms: int
    end_time_ms: int
    status: str
    created_at: str
    completed_at: Optional[str] = None
    snapshot_id: Optional[str] = None
    valid_candles_count: Optional[int] = None
    coverage_ratio: Optional[float] = None
    is_pristine: Optional[bool] = None
    error_message: Optional[str] = None



class CreateSimulationJobRequest(BaseModel):
    snapshot_id: str
    buy_time_ms: int
    buy_price: float
    horizon_minutes: int = 30
    model_artifact_hash: Optional[str] = None


class SimulationAIPredictionDTO(BaseModel):
    predicted_direction: str
    probability_up: Optional[float] = None
    probability_down: Optional[float] = None
    model_version: Optional[str] = None
    model_cutoff_ms: Optional[int] = None
    evidence_summary: Optional[str] = None
    is_calibrated: bool = False


class SimulationUserVoteRequest(BaseModel):
    user_direction: str


class SimulationUserVoteDTO(BaseModel):
    user_direction: str
    voted_at_utc: str
    is_locked: bool = True


class SimulationOutcomeDTO(BaseModel):
    status: str
    horizon_time_ms: int
    future_price: Optional[float] = None
    price_change_pct: Optional[float] = None
    market_direction: Optional[str] = None
    ai_is_correct: Optional[bool] = None
    user_is_correct: Optional[bool] = None
    unscorable_reason: Optional[str] = None
    revealed_at_utc: Optional[str] = None


class SimulationJobResponse(BaseModel):
    job_id: str
    snapshot_id: str
    symbol: str
    timeframe: str
    buy_time_ms: int
    buy_price: float
    candle_close_at_buy: float
    price_offset_pct: float
    horizon_minutes: int
    status: str
    created_at_utc: str
    ai_prediction: Optional[SimulationAIPredictionDTO] = None
    user_vote: Optional[SimulationUserVoteDTO] = None
    outcome: Optional[SimulationOutcomeDTO] = None
    strategy_evaluation: Optional[Dict[str, Any]] = None
    strategy_outcome: Optional[Dict[str, Any]] = None




class TradeWatchCreateRequest(BaseModel):
    symbol: str = Field("BTCUSDT", description="Target trading pair")
    max_notional_usdt: Decimal = Field(..., description="Mandatory maximum position notional in USDT")
    max_planned_loss_usdt: Decimal = Field(..., description="Mandatory maximum planned loss in USDT")
    fee_rate_bps: Decimal = Field(..., description="Mandatory fee rate in basis points")
    slippage_bps: Decimal = Field(..., description="Mandatory slippage allowance in basis points")
    max_wait_duration_ms: int = Field(..., description="Mandatory candidate wait expiration duration in ms")
    max_entry_deviation_pct: Decimal = Field(..., description="Mandatory max entry deviation percentage")
    freshness_tolerance_ms: int = Field(..., description="Mandatory live freshness tolerance in ms")
    max_event_lag_ms: int = Field(..., description="Mandatory max event lag in ms")
    cost_model_source: str = Field(..., description="Mandatory fee/slippage evidence reference")
    strategy_version: str = Field("v1-support-reclaim-30m", description="Strategy rule version")


class TradeWatchResponse(BaseModel):
    id: str
    operator_id: str
    symbol: str
    status: str
    position_state: str
    strategy_version: str
    risk_config: Dict[str, Any]
    symbol_filters: Dict[str, Any]
    active_candidate_id: Optional[str] = None
    execution_mode: Optional[str] = None
    opened_at_ms: Optional[int] = None
    deadline_ms: Optional[int] = None
    closed_at_ms: Optional[int] = None
    created_at: str
    updated_at: str


class EntryObservationRequest(BaseModel):
    mode: str = Field(..., description="PAPER or MANUAL_REPORTED")
    price: Decimal = Field(..., description="Actual or paper fill price")
    quantity: Decimal = Field(..., description="Actual or paper fill quantity")
    actual_entry_time_ms: int = Field(..., description="Timestamp of entry execution")
    idempotency_key: str = Field(..., description="Client-provided idempotency key")
    recent_lowest_price: Optional[Decimal] = Field(None, description="Lowest price observed since actual entry time")
    notes: Optional[str] = None


class ExitObservationRequest(BaseModel):
    mode: str = Field(..., description="PAPER or MANUAL_REPORTED")
    price: Decimal = Field(..., description="Actual or paper exit price")
    quantity: Decimal = Field(..., description="Actual or paper exit quantity")
    exit_reason: str = Field(..., description="TP_HIT, SL_HIT, TIMEOUT, or MANUAL_CANCEL")
    actual_exit_time_ms: int = Field(..., description="Timestamp of exit execution")
    idempotency_key: str = Field(..., description="Client-provided idempotency key")
    notes: Optional[str] = None


class TradeObservationResponse(BaseModel):
    id: str
    idempotency_key: str
    candidate_id: str
    watch_id: Optional[str] = None
    observation_type: str
    mode: str
    price: float
    quantity: float
    remaining_quantity: Optional[float] = None
    fees_paid: float
    actual_time_ms: int
    receipt_time_ms: int
    is_off_plan: bool
    is_risk_breach: bool
    reconciled_sl_breach: bool
    exit_reason: Optional[str] = None
    realized_pnl_usdt: Optional[float] = None
    notes: Optional[str] = None
    created_at: str


class CandidatePlanResponse(BaseModel):
    id: str
    watch_id: Optional[str] = None
    strategy_version: str
    rule_config_hash: str
    decision_time_ms: int
    available_cutoff_ms: int
    entry_zone: Dict[str, Any]
    confirmation: Dict[str, Any]
    invalidation: Dict[str, Any]
    stop_price: float
    target_price: float
    wait_expires_at_ms: int
    horizon_ms: int
    probability: Optional[Dict[str, Any]] = None
    reasons: List[str]
    candidate_state: str
    observations: List[TradeObservationResponse] = []
    created_at: str
