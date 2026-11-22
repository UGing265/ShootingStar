"""Construct versioned, JSON-compatible forecast evidence."""

from shootingstar.adapters.model_api.prompts.forecast_6h_prompt import PROMPT_VERSION


def build_report(feed, answer, verification, horizon_minutes, lookback_days, usage):
    return {"protocol_version": "forecast-6h-v1", **feed, "answer": answer,
            "verification": verification, "horizon_minutes": horizon_minutes,
            "lookback_days": lookback_days, "flat_threshold_pct": 0.5,
            "prompt_version": PROMPT_VERSION, "token_usage": usage}
