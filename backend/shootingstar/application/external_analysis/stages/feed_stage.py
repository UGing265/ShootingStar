"""Prepare causal forecast features and independent baselines."""

from shootingstar.application.forecast.agreement_score import agreement_score
from shootingstar.application.forecast.baselines import always_up, momentum_6h
from shootingstar.application.forecast.technical_digest import build_technical_digest
from shootingstar.application.forecast.outcome import possible_memorization


def build_feed(candles, t_ms, lookback_days, model_id):
    digest = build_technical_digest(candles, t_ms, lookback_days)
    return {"digest": digest, "agreement_score": agreement_score(digest),
            "baselines": {"always_up": always_up(), "momentum_6h": momentum_6h(candles, t_ms)},
            "possible_memorization": possible_memorization(t_ms, model_id)}
