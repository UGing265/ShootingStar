"""Run one forecast over a bounded snapshot window."""

from shootingstar.application.forecast.candle_window import candle_window
from shootingstar.application.external_analysis.stages.feed_stage import build_feed
from shootingstar.application.external_analysis.stages.analyst_stage import analyze
from shootingstar.application.external_analysis.stages.verify_stage import verify
from shootingstar.application.external_analysis.stages.report_stage import build_report


def run_forecast_pipeline(candles, t_ms, horizon_minutes, purchase_price, lookback_days, adapter):
    window = candle_window(candles, t_ms, lookback_days, horizon_minutes)
    feed = build_feed(window, t_ms, lookback_days, adapter.model_name)
    answer, usage = analyze(adapter, feed["digest"], horizon_minutes, purchase_price)
    return build_report(feed, answer, verify(answer, feed["digest"], purchase_price, horizon_minutes),
                        horizon_minutes, lookback_days, usage)
