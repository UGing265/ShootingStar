"""Run bounded, resumable forecasts or calculate offline baseline accuracy."""

import json
import os
from bisect import bisect_right
from datetime import datetime, timezone
from operator import attrgetter

from sqlalchemy import select

from shootingstar.adapters.db.models import ExternalAnalysisJobModel
from shootingstar.adapters.db.repository import ExternalAnalysisJobRepository, SnapshotRepository
from shootingstar.adapters.db.session import get_db_session, load_env_file
from shootingstar.adapters.model_api.prompts.forecast_6h_prompt import PROMPT_VERSION
from shootingstar.adapters.storage import SnapshotStorage, resolve_snapshot_file_path
from shootingstar.application.external_analysis.contracts import ExternalAnalysisRequest
from shootingstar.application.external_analysis.service import ExternalAnalysisService
from shootingstar.application.forecast.baselines import momentum_6h
from shootingstar.application.forecast.candle_window import candle_window
from shootingstar.application.forecast.errors import InsufficientHistoryError
from shootingstar.application.forecast.outcome import evaluate_direction_outcome
from shootingstar.application.forecast.scoreboard import _metric, load_forecast_jobs, score_records
from shootingstar.application.forecast.technical_digest import build_technical_digest


def register(subparsers):
    parser = subparsers.add_parser("forecast-batch", help="Evaluate 6h forecast baselines or run Gemini jobs")
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--horizon", type=int, default=360)
    parser.add_argument("--step-hours", type=int, default=6)
    parser.add_argument("--lookback-days", type=int, default=14)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--start")
    parser.add_argument("--end")


def _parse_time(value):
    if value is None:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return int(parsed.timestamp() * 1000)


def _matching_jobs(session, snapshot_id, horizon, lookback):
    stmt = select(ExternalAnalysisJobModel).where(
        ExternalAnalysisJobModel.snapshot_id == snapshot_id,
        ExternalAnalysisJobModel.horizon_minutes == horizon,
        ExternalAnalysisJobModel.prompt_version == PROMPT_VERSION)
    for job in session.scalars(stmt):
        try:
            envelope = json.loads(job.evidence_envelope_json or "{}")
        except (ValueError, TypeError):
            continue
        if isinstance(envelope, dict) and envelope.get("lookback_days") == lookback:
            yield job


def _done_times(session, snapshot_id, horizon, lookback):
    return {job.prediction_time_t_ms for job in _matching_jobs(session, snapshot_id, horizon, lookback)
            if job.status not in ("FAILED", "FAILED_INTERRUPTED")}


def _print_metrics(metrics):
    print(f"{'Baseline':<16} {'n':>6} {'correct':>8} {'accuracy':>10}")
    for name, metric in metrics.items():
        value = f"{metric['accuracy'] * 100:.2f}%" if metric['accuracy'] is not None else "N/A"
        print(f"{name:<16} {metric['n']:>6} {metric['correct']:>8} {value:>10}")


def run(args):
    load_env_file()
    if min(args.horizon, args.step_hours, args.lookback_days, args.limit) <= 0:
        print("Error: horizon, step, lookback and limit must be positive")
        return 1
    if args.step_hours * 60 < args.horizon:
        print("Error: step must be at least the forecast horizon")
        return 1
    if not args.dry_run and os.environ.get("SHOOTINGSTAR_EXTERNAL_API_ENABLED", "").lower() not in ("true", "1", "yes"):
        print("Error: external API disabled")
        return 1
    try:
        start, end = _parse_time(args.start), _parse_time(args.end)
    except ValueError:
        print("Error: --start/--end must be ISO timestamps")
        return 1
    if start is not None and end is not None and start > end:
        print("Error: --start exceeds --end")
        return 1
    with get_db_session() as session:
        snapshots = SnapshotRepository(session)
        snapshot = snapshots.get_by_id(args.snapshot) or snapshots.get_by_sha256(args.snapshot)
        if snapshot is None:
            print("Error: snapshot not found")
            return 1
        path = resolve_snapshot_file_path(snapshot.file_path)
        if path is None:
            print("Error: snapshot file not found")
            return 1
        candles = SnapshotStorage().load_snapshot(path)
        candles.sort(key=attrgetter("open_time_ms"))
        if not candles:
            print("Error: snapshot empty")
            return 1
        jobs = [] if args.dry_run else list(_matching_jobs(session, snapshot.id, args.horizon, args.lookback_days))
        done = {job.prediction_time_t_ms for job in jobs if job.status not in ("FAILED", "FAILED_INTERRUPTED")}
        failed = {job.prediction_time_t_ms: job.id for job in jobs if job.status in ("FAILED", "FAILED_INTERRUPTED")}
        step = args.step_hours * 3_600_000
        earliest = candles[0].open_time_ms + max(args.lookback_days, 9) * 86_400_000 + 4 * 3_600_000
        start = max(earliest, start if start is not None else earliest)
        last = min(candles[-1].close_time_ms - args.horizon * 60_000, end if end is not None else candles[-1].close_time_ms)
        t = ((start + 1 + step - 1) // step) * step - 1
        selected = errors = flat = missing = 0
        up_correct = momentum_correct = 0
        service = None if args.dry_run else ExternalAnalysisService(ExternalAnalysisJobRepository(session), snapshots, SnapshotStorage())
        while t <= last and selected < args.limit:
            if t in done:
                t += step
                continue
            index = bisect_right(candles, t, key=attrgetter("open_time_ms")) - 1
            if index < 0 or candles[index].close_time_ms != t:
                t += step
                continue
            window = candle_window(candles, t, args.lookback_days, args.horizon)
            price = candles[index].close
            outcome = evaluate_direction_outcome(window, t, args.horizon, price)
            if outcome["outcome"] == "UNSCORABLE":
                t += step
                continue
            try:
                build_technical_digest(window, t, args.lookback_days)
            except InsufficientHistoryError:
                t += step
                continue
            selected += 1
            if args.dry_run:
                momentum = momentum_6h(window, t)
                if outcome["outcome"] == "FLAT":
                    flat += 1
                elif momentum is None:
                    missing += 1
                else:
                    up_correct += outcome["outcome"] == "UP"
                    momentum_correct += outcome["outcome"] == momentum
            else:
                try:
                    request = ExternalAnalysisRequest(snapshot.id, t, price, horizon_minutes=args.horizon, lookback_days=args.lookback_days)
                    result = (service.run_pipeline(failed[t], snapshot_candles=candles)
                              if t in failed else service.create_analysis_job(request, snapshot_candles=candles))
                    session.commit()
                    print(f"{selected}/{args.limit} t={t} status={result.status}")
                    if result.status != "READY":
                        errors += 1
                        if "quota" in (result.error_message or "").lower() or "429" in (result.error_message or "") or errors >= 3:
                            break
                    else:
                        errors = 0
                except Exception as error:
                    session.rollback()
                    errors += 1
                    print(f"Job error: {type(error).__name__}")
                    if errors >= 3:
                        break
            t += step
        if args.dry_run:
            n = selected - flat - missing
            print(f"Selected: {selected}; FLAT: {flat}; missing baseline: {missing}")
            _print_metrics({"always_up": _metric(up_correct, n), "momentum_6h": _metric(momentum_correct, n)})
        else:
            board = score_records(load_forecast_jobs(session, snapshot.id, args.horizon, args.lookback_days), candles, args.horizon, args.lookback_days)
            print(f"Jobs attempted: {selected}; scored: {board['scored']}")
            _print_metrics(board["accuracy"])
            resume = datetime.fromtimestamp(t / 1000, tz=timezone.utc).isoformat()
            print(f"Resume: shootingstar forecast-batch --snapshot {args.snapshot} --horizon {args.horizon} --step-hours {args.step_hours} --lookback-days {args.lookback_days} --limit {args.limit} --start {resume}")
        return 0
