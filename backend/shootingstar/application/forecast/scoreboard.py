"""Retrospective forecast and baseline accuracy on a common scorable cohort."""

import json
import math
import time
from collections import defaultdict

from sqlalchemy import select

from shootingstar.adapters.db.models import ExternalAnalysisJobModel
from shootingstar.adapters.storage import SnapshotStorage, resolve_snapshot_file_path
from shootingstar.application.forecast.candle_window import candle_window
from shootingstar.application.forecast.outcome import evaluate_direction_outcome


def _metric(correct, n):
    """Wilson 95% interval: (p+z²/2n ± z*sqrt(p(1-p)/n+z²/4n²))/(1+z²/n)."""
    if not n:
        return {"n": 0, "correct": 0, "accuracy": None, "wilson_95": None}
    p, z = correct / n, 1.959963984540054
    denominator = 1 + z*z/n
    center = (p + z*z/(2*n)) / denominator
    margin = z * math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / denominator
    return {"n": n, "correct": correct, "accuracy": p,
            "wilson_95": [max(0.0, center-margin), min(1.0, center+margin)]}


def load_forecast_jobs(session, snapshot_id, horizon=360, lookback_days=14):
    """Read only valid forecast envelopes for one snapshot and parameter set."""
    stmt = select(ExternalAnalysisJobModel).where(
        ExternalAnalysisJobModel.snapshot_id == snapshot_id,
        ExternalAnalysisJobModel.horizon_minutes == horizon)
    records = []
    for job in session.scalars(stmt):
        try:
            envelope = json.loads(job.evidence_envelope_json or "{}")
        except (ValueError, TypeError):
            continue
        if isinstance(envelope, dict) and envelope.get("protocol_version") == "forecast-6h-v1" and envelope.get("lookback_days") == lookback_days:
            records.append((job, envelope))
    return records


def score_records(records, candles, horizon=360, lookback_days=14):
    """Score all three directions on the same valid, non-flat cohort at each threshold."""
    n_flat = n_unscorable = n_missing = 0
    scored = []
    threshold_n = {"0.3": 0, "0.5": 0, "1.0": 0}
    now = int(time.time() * 1000)
    for job, envelope in records:
        t = job.prediction_time_t_ms
        window = candle_window(candles, t, lookback_days, horizon)
        if job.mode == "PROSPECTIVE" and now < t + horizon * 60_000:
            n_unscorable += 1
            continue
        result = evaluate_direction_outcome(window, t, horizon, job.purchase_price_p, 0.5)
        outcome = result["outcome"]
        if outcome == "UNSCORABLE":
            n_unscorable += 1
            continue
        answer = envelope.get("answer") or {}
        baseline = envelope.get("baselines") or {}
        directions = {"gemini": answer.get("direction"), "always_up": baseline.get("always_up"),
                      "momentum_6h": baseline.get("momentum_6h")}
        valid = all(x in ("UP", "DOWN") for x in directions.values())
        for threshold in threshold_n:
            alternative = evaluate_direction_outcome(window, t, horizon, job.purchase_price_p, float(threshold))
            if alternative["outcome"] in ("UP", "DOWN"):
                threshold_n[threshold] += 1
        if outcome == "FLAT":
            n_flat += 1
            continue
        if not valid:
            n_missing += 1
            continue
        agreement = envelope.get("agreement_score") or {}
        up, down = agreement.get("up"), agreement.get("down")
        bucket = f"{up}/{down}" if isinstance(up, int) and isinstance(down, int) else "unknown"
        scored.append((outcome, directions, answer.get("confidence", "UNKNOWN"), bucket,
                       str(envelope.get("possible_memorization")).lower()))
    overall = {name: _metric(sum(d[name] == outcome for outcome, d, *_ in scored), len(scored))
               for name in ("gemini", "always_up", "momentum_6h")}
    grouped = {}
    for key, index in (("confidence", 2), ("agreement", 3), ("possible_memorization", 4)):
        groups = defaultdict(list)
        for row in scored:
            groups[str(row[index])].append(row)
        grouped[key] = {name: _metric(sum(r[1]["gemini"] == r[0] for r in rows), len(rows))
                        for name, rows in sorted(groups.items())}
    return {"total": len(records), "flat": n_flat, "unscorable": n_unscorable,
            "missing_baseline_or_direction": n_missing, "scored": len(scored),
            "threshold_n": threshold_n, "accuracy": overall, **grouped}


def build_scoreboard(session, snapshot, horizon=360, lookback_days=14):
    path = resolve_snapshot_file_path(snapshot.file_path)
    if path is None:
        raise ValueError("Snapshot file not found")
    records = load_forecast_jobs(session, snapshot.id, horizon, lookback_days)
    candles = SnapshotStorage().load_snapshot(path)
    candles.sort(key=lambda c: c.open_time_ms)
    return {"snapshot_id": snapshot.id, "horizon_minutes": horizon, "lookback_days": lookback_days,
            **score_records(records, candles, horizon, lookback_days)}
