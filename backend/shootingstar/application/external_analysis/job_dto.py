"""Serialize persisted forecast and legacy analysis jobs without revealing outcomes early."""

import json

from shootingstar.application.external_analysis.contracts import AnalysisDirection, ExternalAnalysisJobDTO, ModelPredictionOutput


def model_to_dto(job, leakage_banner=False):
    evidence_times = json.loads(job.evidence_times_json) if job.evidence_times_json else []
    try:
        envelope = json.loads(job.evidence_envelope_json) if job.evidence_envelope_json else None
    except (TypeError, ValueError):
        envelope = None
    prediction = None
    if job.direction:
        prediction = ModelPredictionOutput(
            direction=AnalysisDirection(job.direction), rationale=job.rationale or "",
            evidence_candle_times=evidence_times, probability_up=None, probability_down=None,
            model_id=job.model_id, prompt_version=job.prompt_version, key_index=job.key_index,
            prompt_tokens=job.prompt_tokens, completion_tokens=job.completion_tokens,
            estimated_cost_usd=job.estimated_cost_usd)
    return ExternalAnalysisJobDTO(
        id=job.id, snapshot_id=job.snapshot_id, snapshot_hash=job.snapshot_hash,
        symbol=job.symbol, timeframe=job.timeframe, prediction_time_t_ms=job.prediction_time_t_ms,
        purchase_price_p=job.purchase_price_p, horizon_minutes=job.horizon_minutes,
        mode=job.mode, context_variant=job.context_variant, status=job.status,
        created_at_iso=job.created_at.isoformat() if job.created_at else "", ai_prediction=prediction,
        user_vote=job.user_vote, outcome=job.outcome if job.is_revealed else None,
        target_price=job.target_price if job.is_revealed else None,
        outcome_evaluated_at_ms=job.outcome_evaluated_at_ms if job.is_revealed else None,
        error_message=job.error_message, leakage_risk_banner=leakage_banner,
        evidence_envelope=envelope, stages=envelope.get("stages") if isinstance(envelope, dict) else None)
