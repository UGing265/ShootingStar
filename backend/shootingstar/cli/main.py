"""Command Line Interface for ShootingStar."""

import argparse
from datetime import datetime, timezone
import logging
import sys
import uuid
from shootingstar import __version__
from shootingstar.adapters.binance import BinanceBannedError, BinanceRateLimitError
from shootingstar.adapters.db.models import IngestionRunModel, SnapshotModel
from shootingstar.adapters.db.repository import IngestionRunRepository, SnapshotRepository
from shootingstar.adapters.db.session import get_db_session
from shootingstar.application.ingestion import PilotIngestionService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("shootingstar.cli")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="shootingstar",
        description="ShootingStar: BTCUSDT 30-minute research platform",
    )
    parser.add_argument(
        "-v", "--version",
        action="version",
        version=f"ShootingStar {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Command: info
    subparsers.add_parser("info", help="Print system information and configuration")

    # Command: fetch-pilot
    pilot_parser = subparsers.add_parser("fetch-pilot", help="Run bounded Binance Spot pilot ingestion")
    pilot_parser.add_argument("--symbol", default="BTCUSDT", help="Trading pair symbol (default: BTCUSDT)")
    pilot_parser.add_argument("--timeframe", default="1m", choices=["1m", "5m"], help="Candle timeframe (default: 1m)")
    pilot_parser.add_argument("--days", type=int, default=30, help="Number of pilot days (default: 30)")
    pilot_parser.add_argument("--start", help="Start time in ms or ISO format (e.g. 2024-03-01T00:00:00)")
    pilot_parser.add_argument("--end", help="End time in ms or ISO format (e.g. 2024-04-30T23:59:59)")

    # Command: fetch-history
    hist_parser = subparsers.add_parser("fetch-history", help="Run bounded Binance Spot historical ingestion for an arbitrary date window")
    hist_parser.add_argument("--symbol", default="BTCUSDT", help="Trading pair symbol (default: BTCUSDT)")
    hist_parser.add_argument("--timeframe", default="1m", choices=["1m", "5m"], help="Candle timeframe (default: 1m)")
    hist_parser.add_argument("--start", required=True, help="Start time in ms or ISO format (e.g. 2024-03-01T00:00:00)")
    hist_parser.add_argument("--end", required=True, help="End time in ms or ISO format (e.g. 2024-04-30T23:59:59)")
    # Command: list-snapshots
    subparsers.add_parser("list-snapshots", help="List snapshots stored in PostgreSQL database")

    # Command: show-snapshot
    show_parser = subparsers.add_parser("show-snapshot", help="Show snapshot metadata from PostgreSQL database")
    show_parser.add_argument("--id", required=True, help="Snapshot SHA-256 hash or ID")
    # Command: run-experiment
    exp_parser = subparsers.add_parser("run-experiment", help="Run 30-minute research experiment on a candle snapshot")
    exp_parser.add_argument("--snapshot", required=True, help="Snapshot file path or SHA-256 hash")
    exp_parser.add_argument("--id", default="exp_lr_30m_pilot", help="Experiment ID")
    # Command: scan-patterns
    pattern_parser = subparsers.add_parser("scan-patterns", help="Scan declarative candle patterns and measure forward 30m returns")
    pattern_parser.add_argument("--snapshot", required=True, help="Snapshot file path or SHA-256 hash")
    pattern_parser.add_argument("--horizon", type=int, default=30, help="Forward return horizon in minutes (default: 30)")
    # Command: list-signals
    sig_parser = subparsers.add_parser("list-signals", help="List recent signal predictions and their maturation outcomes")
    sig_parser.add_argument("--limit", type=int, default=20, help="Maximum number of signals to list (default: 20)")
    # Command: mature-signals
    mature_parser = subparsers.add_parser("mature-signals", help="Evaluate pending signals against closed snapshot candles")
    mature_parser.add_argument("--snapshot", required=True, help="Snapshot file path or SHA-256 hash containing recent candles")
    # Command: serve
    serve_parser = subparsers.add_parser("serve", help="Launch the ShootingStar Research Platform web server")
    serve_parser.add_argument("--host", default="127.0.0.1", help="Host interface (default: 127.0.0.1)")
    serve_parser.add_argument("--port", type=int, default=8000, help="Port (default: 8000)")
    serve_parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")

    return parser


def parse_time_arg(val: str | None) -> int | None:
    if not val:
        return None
    s = val.strip()
    if s.isdigit():
        return int(s)
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    except ValueError as err:
        raise argparse.ArgumentTypeError(
            f"Invalid timestamp or ISO 8601 date format: '{val}'. Expected epoch milliseconds or ISO format (e.g. 2024-03-01T00:00:00Z)"
        ) from err


def _execute_ingestion(symbol: str, timeframe: str, days: int = 30, start_time_ms: int | None = None, end_time_ms: int | None = None) -> int:
    window_desc = f"{days} days" if start_time_ms is None else f"{start_time_ms} -> {end_time_ms}"
    print(f"=== Starting Binance Ingestion: {symbol} {timeframe} ({window_desc}) ===")
    service = PilotIngestionService()
    try:
        result = service.run_pilot(
            symbol=symbol,
            timeframe_str=timeframe,
            days=days,
            start_time_ms=start_time_ms,
            end_time_ms=end_time_ms,
        )
        report = result.report
        print("\n=== Ingestion & Quality Report ===")
        print(f"Symbol:               {report.symbol}")
        print(f"Timeframe:            {report.timeframe}")
        print(f"Expected intervals:   {report.total_expected_intervals}")
        print(f"Received candles:     {report.total_received_candles}")
        print(f"Valid candles:        {report.valid_candles_count}")
        print(f"Missing intervals:    {report.missing_intervals_count}")
        print(f"Duplicates:           {report.duplicate_candles_count}")
        print(f"Coverage ratio:       {report.coverage_ratio * 100:.2f}%")
        print(f"Pristine series:      {'YES' if report.is_pristine else 'NO (contains gaps/dups)'}")
        print(f"Raw archive files:    {result.raw_files_count}")
        print(f"Snapshot path:        {result.snapshot_path}")
        print(f"Snapshot SHA-256:     {result.snapshot_sha256}")

        # Persist to database
        with get_db_session() as session:
            run_repo = IngestionRunRepository(session)
            snap_repo = SnapshotRepository(session)

            run_id = str(uuid.uuid4())
            db_run = IngestionRunModel(
                id=run_id,
                venue="BINANCE",
                symbol=report.symbol,
                timeframe=report.timeframe,
                start_time_ms=report.start_time_ms,
                end_time_ms=report.end_time_ms,
                valid_candles_count=report.valid_candles_count,
                missing_intervals_count=report.missing_intervals_count,
                duplicate_candles_count=report.duplicate_candles_count,
                coverage_ratio=report.coverage_ratio,
                is_pristine=report.is_pristine,
                raw_files_count=result.raw_files_count,
            )
            run_repo.save(db_run)

            db_snap = SnapshotModel(
                id=result.snapshot_sha256,
                ingestion_run_id=run_id,
                venue="BINANCE",
                symbol=report.symbol,
                timeframe=report.timeframe,
                start_time_ms=report.start_time_ms,
                end_time_ms=report.end_time_ms,
                candle_count=report.valid_candles_count,
                file_path=str(result.snapshot_path),
                sha256=result.snapshot_sha256,
            )
            snap_repo.save(db_snap)
            print(f"Database Record:      SAVED & COMMITTED (run_id={run_id[:8]}..., snapshot_id={result.snapshot_sha256[:8]}...)")

        print("\n[NOTE] Historical snapshot verifies data quality only; it does NOT constitute model evaluation.")
        return 0
    except BinanceBannedError as e:
        logger.critical("HALTING: %s", e)
        return 2
    except BinanceRateLimitError as e:
        logger.error("Rate limit error: %s", e)
        return 1
    except Exception as e:
        logger.error("Ingestion failed: %s", e)
        return 1
def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "info":
        print(f"ShootingStar v{__version__} - Evidence-first 30-minute research platform")
        print("Status: Local-first research engine with PostgreSQL persistence")
        return 0

    if args.command == "fetch-pilot":
        start_ms = parse_time_arg(getattr(args, "start", None))
        end_ms = parse_time_arg(getattr(args, "end", None))
        return _execute_ingestion(
            symbol=args.symbol,
            timeframe=args.timeframe,
            days=args.days,
            start_time_ms=start_ms,
            end_time_ms=end_ms,
        )

    if args.command == "fetch-history":
        start_ms = parse_time_arg(args.start)
        end_ms = parse_time_arg(args.end)
        if start_ms is None or end_ms is None:
            print("Error: Both --start and --end must be valid timestamps or ISO dates.")
            return 1
        return _execute_ingestion(
            symbol=args.symbol,
            timeframe=args.timeframe,
            days=0,
            start_time_ms=start_ms,
            end_time_ms=end_ms,
        )

    if args.command == "list-snapshots":
        try:
            with get_db_session() as session:
                snap_repo = SnapshotRepository(session)
                snapshots = snap_repo.list_all()
                if not snapshots:
                    print("No snapshots stored in database yet.")
                    return 0
                print(f"Total Snapshots: {len(snapshots)}\n")
                print(f"{'SHA-256':<20} {'Symbol':<10} {'TF':<5} {'Candles':<10} {'File Path'}")
                print("-" * 80)
                for s in snapshots:
                    print(f"{s.sha256[:16]+'...':<20} {s.symbol:<10} {s.timeframe:<5} {s.candle_count:<10} {s.file_path}")
                return 0
        except Exception as e:
            logger.error("Failed to list snapshots: %s", e)
            return 1

    if args.command == "show-snapshot":
        try:
            with get_db_session() as session:
                snap_repo = SnapshotRepository(session)
                snap = snap_repo.get_by_sha256(args.id) or snap_repo.get_by_id(args.id)
                if not snap:
                    print(f"Snapshot not found: {args.id}")
                    return 1
                print(f"=== Snapshot Details ===")
                print(f"ID / SHA-256:     {snap.sha256}")
                print(f"Symbol:           {snap.symbol}")
                print(f"Timeframe:        {snap.timeframe}")
                print(f"Candles Count:    {snap.candle_count}")
                print(f"Start Time (ms):  {snap.start_time_ms}")
                print(f"End Time (ms):    {snap.end_time_ms}")
                print(f"File Path:        {snap.file_path}")
                print(f"Created At:       {snap.created_at}")
                return 0
        except Exception as e:
            logger.error("Failed to show snapshot: %s", e)
            return 1
    if args.command == "run-experiment":
        from pathlib import Path
        from shootingstar.application.experiment import ExperimentRunner

        snap_arg = Path(args.snapshot)
        if not snap_arg.exists():
            matches = list(Path("data/snapshots").glob(f"*{args.snapshot}*.parquet"))
            if matches:
                snap_arg = matches[0]
            else:
                print(f"Snapshot file not found: {args.snapshot}")
                return 1

        print(f"=== Running Experiment: {args.id} on {snap_arg.name} ===")
        runner = ExperimentRunner()
        try:
            report, artifact_path, artifact_hash = runner.run_experiment(
                snapshot_path=snap_arg,
                experiment_id=args.id,
            )
            print("\n" + report.to_markdown())
            print(f"\nModel Artifact:  {artifact_path} (SHA-256: {artifact_hash})")
            print(f"Markdown Report: data/reports/{args.id}_report.md")
            print(f"JSON Report:     data/reports/{args.id}_report.json")
            return 0
        except Exception as e:
            logger.error("Experiment failed: %s", e)
            return 1


    if args.command == "scan-patterns":
        from pathlib import Path
        from shootingstar.adapters.storage import SnapshotStorage
        from shootingstar.application.patterns import PatternLabService

        snap_arg = Path(args.snapshot)
        if not snap_arg.exists():
            matches = list(Path("data/snapshots").glob(f"*{args.snapshot}*.parquet"))
            if matches:
                snap_arg = matches[0]
            else:
                print(f"Snapshot file not found: {args.snapshot}")
                return 1

        snap_storage = SnapshotStorage()
        candles = snap_storage.load_snapshot(snap_arg)
        print(f"=== Scanning Patterns on {snap_arg.name} ({len(candles)} candles) ===\n")

        lab = PatternLabService()
        reports = lab.analyze_all(candles, horizon_minutes=args.horizon)

        print(f"{'Pattern Name':<20} {'Target':<7} {'Hits':<6} {'Win Rate':<10} {'Mean 30m Ret':<14} {'Statistical Power'}")
        print("-" * 80)
        for r in reports:
            power_str = "WARNING (N<30)" if r.statistical_power_warning else "OK (N>=30)"
            print(f"{r.rule_name:<20} {r.expected_direction:<7} {r.sample_count:<6} {r.win_rate*100:<9.1f}% {r.mean_return_30m*100:<13.3f}% {power_str}")

        print("\n[NOTE] Pattern Lab is a separate hypothesis track and is NOT mixed into classifier features.")
        return 0

    if args.command == "list-signals":
        from shootingstar.adapters.db.repository import SignalRepository

        with get_db_session() as session:
            repo = SignalRepository(session)
            predictions = repo.list_predictions(limit=args.limit)
            if not predictions:
                print("No signals recorded in database.")
                return 0

            print(f"{'Signal ID':<22} {'Pred Time (UTC)':<20} {'Symbol':<8} {'Pred':<5} {'Dec':<9} {'P(UP)':<7} {'Status':<11} {'Outcome'}")
            print("-" * 95)
            for p in predictions:
                outcome = repo.get_outcome_by_signal_id(p.id)
                dt_str = datetime.fromtimestamp(p.prediction_time_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
                status = outcome.status if outcome else "PENDING"
                outcome_detail = f"{outcome.realized_label} ({outcome.realized_return*100:+.2f}%)" if (outcome and outcome.realized_return is not None) else "-"
                print(f"{p.id:<22} {dt_str:<20} {p.symbol:<8} {p.predicted_class:<5} {p.decision:<9} {p.probability_up:<7.3f} {status:<11} {outcome_detail}")
        return 0

    if args.command == "mature-signals":
        import time
        from pathlib import Path
        from shootingstar.adapters.storage import SnapshotStorage
        from shootingstar.adapters.db.repository import SignalRepository
        from shootingstar.application.signals import SignalLifecycleService

        snap_arg = Path(args.snapshot)
        if not snap_arg.exists():
            matches = list(Path("data/snapshots").glob(f"*{args.snapshot}*.parquet"))
            if matches:
                snap_arg = matches[0]
            else:
                print(f"Snapshot file not found: {args.snapshot}")
                return 1

        storage = SnapshotStorage()
        candles = storage.load_snapshot(snap_arg)
        candles_by_time = {c.open_time_ms: c for c in candles}
        now_ms = max(c.close_time_ms for c in candles) + 1000

        with get_db_session() as session:
            repo = SignalRepository(session)
            service = SignalLifecycleService(repo)
            unresolved = repo.get_unresolved_predictions()
            print(f"Checking {len(unresolved)} unresolved signal(s) against snapshot {snap_arg.name}...")
            matured_count = 0
            for sig in unresolved:
                res = service.mature_signal(sig, candles_by_time, now_ms=now_ms)
                if res:
                    matured_count += 1
                    print(f"  Signal {sig.id}: status -> {res.status} (realized: {res.realized_label}, return: {res.realized_return})")
            print(f"Matured {matured_count} signal(s).")
        return 0

    if args.command == "serve":
        import uvicorn

        print(f"Starting ShootingStar Research Platform on http://{args.host}:{args.port}")
        if getattr(args, "reload", False):
            uvicorn.run("shootingstar.api.app:app", host=args.host, port=args.port, reload=True)
        else:
            from shootingstar.api.app import app
            uvicorn.run(app, host=args.host, port=args.port)
        return 0


if __name__ == "__main__":
    sys.exit(main())
