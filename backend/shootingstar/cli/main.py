"""Command Line Interface for ShootingStar."""

import argparse
from datetime import datetime, timezone
import logging
from pathlib import Path
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
    # Command: research-pattern
    res_parser = subparsers.add_parser("research-pattern", help="Search literature catalogue, inspect with model, and extract verified candidate lessons")
    res_parser.add_argument("--query", required=True, help="Pattern name or technical analysis concept to research")
    res_parser.add_argument("--catalogue-dir", help="Optional path to directory containing literature documents")
    res_parser.add_argument("--live", action="store_true", help="Execute live model extraction with paid Gemini API (default is safe mock mode)")
    serve_parser = subparsers.add_parser("serve", help="Launch the ShootingStar Research Platform web server")
    serve_parser.add_argument("--host", default="127.0.0.1", help="Host interface (default: 127.0.0.1)")
    serve_parser.add_argument("--port", type=int, default=8000, help="Port (default: 8000)")
    serve_parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")

    # Command: watch-entry
    watch_parser = subparsers.add_parser("watch-entry", help="Run local public watcher for BTCUSDT fast entry setups")
    watch_parser.add_argument("--symbol", default="BTCUSDT", help="Trading pair symbol (default: BTCUSDT)")
    watch_parser.add_argument("--config", required=True, help="Path to JSON risk configuration file")
    watch_parser.add_argument("--once", action="store_true", help="Run a single evaluation cycle and exit")

    # Command: research-entry-strategy
    res_entry = subparsers.add_parser("research-entry-strategy", help="Extract causal candidate barrier episodes and compute smoothed probability artifact")
    res_entry.add_argument("--snapshot", required=True, help="Snapshot file path or SHA-256 hash")
    res_entry.add_argument("--min-samples", type=int, default=30, help="Minimum sample size threshold (default: 30)")
    res_entry.add_argument("--alpha", type=float, default=1.0, help="Dirichlet prior smoothing parameter (default: 1.0)")
    res_entry.add_argument("--horizon", type=int, default=30, help="Holding horizon in minutes (default: 30)")
    res_entry.add_argument("--train-ratio", type=float, default=0.70, help="Fraction of candles to use for training cutoff (default: 0.70)")
    res_entry.add_argument("--out-dir", default="models/barrier", help="Directory to save artifact manifest")

    # Command: evaluate-entry-strategy
    eval_entry = subparsers.add_parser("evaluate-entry-strategy", help="Evaluate barrier artifact out-of-sample against snapshot")
    eval_entry.add_argument("--artifact", required=True, help="Path to barrier model manifest JSON")
    eval_entry.add_argument("--snapshot", required=True, help="Snapshot file path or SHA-256 hash")
    eval_entry.add_argument("--horizon", type=int, default=30, help="Holding horizon in minutes (default: 30)")
    eval_entry.add_argument("--out-dir", default="models/barrier", help="Directory to save evaluation report JSON")

    # Command: approve-entry-artifact
    app_entry = subparsers.add_parser("approve-entry-artifact", help="Verify strict validation gates and approve barrier artifact with provenance")
    app_entry.add_argument("--artifact", required=True, help="Path to barrier model manifest JSON")
    app_entry.add_argument("--evaluation-report", required=True, help="Path to evaluation report JSON")
    app_entry.add_argument("--approver", default="admin", help="Approver identity (default: admin)")

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
        from shootingstar.application.training.experiment import ExperimentRunner

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

    if args.command == "research-pattern":
        from shootingstar.adapters.db.repository import LessonRepository
        from shootingstar.application.external_analysis.lessons import LessonService
        from shootingstar.application.external_analysis.research_agent import ResearchAgent

        cat_dir = Path(args.catalogue_dir) if args.catalogue_dir else None
        is_mock = not getattr(args, "live", False)
        if not is_mock:
            print("[LIVE RUN] Calling external Gemini API slots. Model quota/cost applies.")
        else:
            print("[MOCK RUN] Safe mode enabled (no external API calls, no database persistence).")

        with get_db_session() as session:
            repo = LessonRepository(session)
            service = LessonService(repo)
            agent = ResearchAgent(service, catalogue_dir=cat_dir)
            result = agent.orchestrate_research(
                pattern_query=args.query,
                mock_mode=is_mock,
            )
            if is_mock:
                session.rollback()
            else:
                session.commit()
            print(f"Research Pattern '{args.query}' Status: {result.get('status')}")
            print(f"Matches found in catalogue: {result.get('matches_found', 0)}")
            print(f"Candidates extracted: {result.get('candidates_count', 0)}")
            for cand in result.get("candidates", []):
                print(f"  - [{cand.get('status')}] {cand.get('title')} (ID: {cand.get('lesson_id')})")
            if result.get("rejected_count", 0) > 0:
                print(f"Rejected: {result.get('rejected_count')}")
                for rej in result.get("rejected", []):
                    print(f"  x {rej.get('reason')}")
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

    if args.command == "watch-entry":
        import json
        import time
        from decimal import Decimal
        from shootingstar.adapters.binance import BinanceSpotClient
        from shootingstar.adapters.binance_market_events import BinanceMarketEventsClient
        from shootingstar.application.entry_strategy import EntryStrategyEngine
        from shootingstar.domain.trade_plan import RiskConfig

        config_path = Path(args.config)
        if not config_path.is_file():
            print(f"Error: Configuration file not found at {config_path}")
            return 1

        with open(config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)

        required_fields = [
            "max_notional_usdt", "max_planned_loss_usdt", "fee_rate_bps", "slippage_bps",
            "max_wait_duration_ms", "max_entry_deviation_pct", "freshness_tolerance_ms",
            "max_event_lag_ms", "cost_model_source"
        ]
        missing = [f for f in required_fields if f not in cfg]
        if missing:
            print(f"Error: Mandatory risk configuration missing fields: {missing}")
            return 1

        risk_config = RiskConfig(
            max_notional_usdt=Decimal(str(cfg["max_notional_usdt"])),
            max_planned_loss_usdt=Decimal(str(cfg["max_planned_loss_usdt"])),
            fee_rate_bps=Decimal(str(cfg["fee_rate_bps"])),
            slippage_bps=Decimal(str(cfg["slippage_bps"])),
            max_wait_duration_ms=int(cfg["max_wait_duration_ms"]),
            max_entry_deviation_pct=Decimal(str(cfg["max_entry_deviation_pct"])),
            freshness_tolerance_ms=int(cfg["freshness_tolerance_ms"]),
            max_event_lag_ms=int(cfg["max_event_lag_ms"]),
            cost_model_source=str(cfg["cost_model_source"]),
        )

        from shootingstar.adapters.binance_market_events import BinanceMarketEventsClient
        from shootingstar.adapters.db.repository import CandidatePlanRepository, TradeObservationRepository, TradeWatchRepository
        from shootingstar.application.trade_watch import TradeWatchService, run_watch_worker

        events_client = BinanceMarketEventsClient()
        print(f"Connecting to Binance Spot for {args.symbol} exchangeInfo...")
        symbol_filters = events_client.fetch_symbol_filters(args.symbol)
        print(f"Loaded {args.symbol} filters: tick={symbol_filters.tick_size}, step={symbol_filters.step_size}")

        import contextlib
        from shootingstar.adapters.db.session import get_engine, get_session_factory
        engine = get_engine()
        session_factory = get_session_factory(engine)

        @contextlib.contextmanager
        def worker_session_factory():
            session = session_factory()
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

        operator_id = "local_operator"
        with worker_session_factory() as session:
            watch_repo = TradeWatchRepository(session)
            cand_repo = CandidatePlanRepository(session)
            obs_repo = TradeObservationRepository(session)
            service = TradeWatchService(watch_repo, cand_repo, obs_repo)

            active = watch_repo.find_active_reservation(operator_id, args.symbol)
            if active:
                watch_id = active.id
                print(f"Resuming existing active watch {watch_id} (state: {active.position_state})...")
            else:
                new_watch = service.start_watch(
                    operator_id=operator_id,
                    symbol=args.symbol,
                    risk_config=risk_config,
                    symbol_filters=symbol_filters,
                )
                session.commit()
                watch_id = new_watch.id
                print(f"Created new durable watch session {watch_id} on {args.symbol}.")
        return run_watch_worker(
            watch_id=watch_id,
            session_factory=worker_session_factory,
            symbol=args.symbol,
            once=args.once,
        )

    if args.command == "research-entry-strategy":
        from decimal import Decimal
        import hashlib
        from shootingstar.adapters.storage import SnapshotStorage
        from shootingstar.application.barrier_evaluation import (
            BarrierArtifactManager,
            BarrierModelArtifact,
            EmpiricalMultinomialEstimator,
            FirstTouchLabeler,
        )
        from shootingstar.application.entry_strategy import EntryStrategyEngine
        from shootingstar.domain.trade_plan import CandidateState, ObservationDecision, RiskConfig, SymbolFilters

        storage = SnapshotStorage()
        snap_path = Path(args.snapshot)
        if not snap_path.exists():
            snaps = storage.list_snapshots()
            match = next((s for s in snaps if s["sha256"] == args.snapshot or s["snapshot_id"] == args.snapshot), None)
            if match:
                snap_path = Path(match["file_path"])
            else:
                print(f"Error: Snapshot '{args.snapshot}' not found.")
                return 1

        candles = storage.load_snapshot(snap_path)
        if not candles:
            print("Error: Snapshot has no candles.")
            return 1

        engine = EntryStrategyEngine()
        symbol_filters = SymbolFilters(
            symbol=candles[0].symbol,
            tick_size=Decimal("0.01"),
            step_size=Decimal("0.00001"),
            min_notional=Decimal("5.0"),
            min_qty=Decimal("0.00001"),
        )
        risk_config = RiskConfig(
            max_notional_usdt=Decimal("2000.00"),
            max_planned_loss_usdt=Decimal("100.00"),
            fee_rate_bps=Decimal("10.0"),
            slippage_bps=Decimal("5.0"),
            max_wait_duration_ms=args.horizon * 60 * 1000,
            max_entry_deviation_pct=Decimal("0.002"),
            freshness_tolerance_ms=120000,
            max_event_lag_ms=5000,
            cost_model_source="vip0-doc",
        )
        labeler = FirstTouchLabeler()
        estimator = EmpiricalMultinomialEstimator()
        lookback = 60
        horizon_ms = args.horizon * 60 * 1000
        step = 6  # Subsample by step to avoid dense overlapping episodes

        # Strict temporal split: only train on candles up to train_ratio
        n_train = max(lookback + 10, int(len(candles) * args.train_ratio))
        train_candles = candles[:n_train]
        outcomes = []

        for i in range(lookback, len(train_candles) - 1, step):
            vis = train_candles[: i + 1]
            decision_time = vis[-1].close_time_ms
            plan, decision, _ = engine.create_candidate(
                candles=vis,
                decision_time_ms=decision_time,
                available_cutoff_ms=decision_time,
                symbol_filters=symbol_filters,
                risk_config=risk_config,
            )
            confirmed_plan = None
            confirmation_time_ms = 0
            if plan and plan.candidate_state == CandidateState.WAITING:
                curr_p = plan
                for f_idx in range(i + 1, min(i + 6, len(train_candles))):
                    nc = train_candles[f_idx]
                    avail_time = nc.close_time_ms + engine.assumed_latency_ms
                    curr_p, adv_dec, adv_reasons = engine.advance_candidate(
                        locked_plan=curr_p,
                        new_candles=[nc],
                        current_time_ms=avail_time,
                    )
                    if adv_dec in (ObservationDecision.WATCH_ONLY, ObservationDecision.BUY_ELIGIBLE):
                        confirmed_plan = curr_p
                        confirmation_time_ms = avail_time
                        break
                    if adv_dec == ObservationDecision.SKIP or curr_p.candidate_state in (
                        CandidateState.INVALIDATED,
                        CandidateState.EXPIRED,
                    ):
                        break

            if confirmed_plan and confirmation_time_ms > 0:
                deadline_ms = confirmation_time_ms + horizon_ms
                forward = [
                    c for c in train_candles
                    if c.open_time_ms >= confirmation_time_ms and c.open_time_ms < deadline_ms
                ]
                if forward:
                    p_entry = confirmed_plan.entry_zone.proposed_entry
                    in_horizon_candles = [c for c in forward if (c.close_time_ms + 1) <= deadline_ms]
                    fill_idx = next(
                        (idx for idx, c in enumerate(in_horizon_candles) if Decimal(str(c.low)) <= p_entry <= Decimal(str(c.high))),
                        None,
                    )
                    if fill_idx is not None:
                        fill_candle = in_horizon_candles[fill_idx]
                        path_candles = forward[fill_idx:]
                        res = labeler.evaluate_path(
                            entry_price=p_entry,
                            target_price=confirmed_plan.target_price,
                            stop_price=confirmed_plan.stop_price,
                            entry_time_ms=fill_candle.open_time_ms,
                            deadline_ms=deadline_ms,
                            candles=path_candles,
                        )
                        outcomes.append(res.outcome)

        estimate = estimator.estimate(outcomes, min_samples=args.min_samples, alpha=args.alpha)
        print(f"Total evaluated episodes: {len(outcomes)}")
        print(f"Calibrated: {estimate.is_calibrated}")
        if not estimate.is_calibrated:
            print(f"Gating Reason: {estimate.gating_reason}")
            return 1

        art_hash = hashlib.sha256(f"{engine.strategy_version}:{estimate.sample_size}:{estimate.p_tp}".encode()).hexdigest()[:16]
        from datetime import datetime, timezone
        artifact = BarrierModelArtifact(
            artifact_hash=art_hash,
            strategy_version=engine.strategy_version,
            created_at_utc=datetime.now(timezone.utc).isoformat(),
            train_cutoff_ms=train_candles[-1].close_time_ms,
            sample_size=estimate.sample_size,
            alpha_smoothing=estimate.alpha_smoothing,
            p_tp=estimate.p_tp or 0.0,
            p_sl=estimate.p_sl or 0.0,
            p_timeout=estimate.p_timeout or 0.0,
            credible_intervals=estimate.credible_intervals or {},
        )
        out_dir = Path(args.out_dir)
        saved_path = BarrierArtifactManager.save_artifact(artifact, out_dir)
        print(f"Saved barrier artifact: {saved_path}")
        print(f"p_tp: {artifact.p_tp} (90% CI: {artifact.credible_intervals.get('p_tp')})")
        print(f"p_sl: {artifact.p_sl} (90% CI: {artifact.credible_intervals.get('p_sl')})")
        print(f"p_timeout: {artifact.p_timeout} (90% CI: {artifact.credible_intervals.get('p_timeout')})")
        return 0

    if args.command == "evaluate-entry-strategy":
        import json
        from shootingstar.adapters.storage import SnapshotStorage
        from shootingstar.application.barrier_evaluation import BarrierArtifactManager, FirstTouchLabeler
        from shootingstar.application.entry_strategy import EntryStrategyEngine
        from shootingstar.domain.trade_plan import CandidateState, ObservationDecision, RiskConfig, SymbolFilters
        from decimal import Decimal

        art_path = Path(args.artifact)
        if not art_path.exists():
            print(f"Error: Artifact path '{args.artifact}' does not exist.")
            return 1
        artifact = BarrierArtifactManager.load_artifact(art_path)

        storage = SnapshotStorage()
        snap_path = Path(args.snapshot)
        if not snap_path.exists():
            snaps = storage.list_snapshots()
            match = next((s for s in snaps if s["sha256"] == args.snapshot or s["snapshot_id"] == args.snapshot), None)
            if match:
                snap_path = Path(match["file_path"])
            else:
                print(f"Error: Snapshot '{args.snapshot}' not found.")
                return 1

        candles = storage.load_snapshot(snap_path)
        engine = EntryStrategyEngine()
        symbol_filters = SymbolFilters(
            symbol=candles[0].symbol,
            tick_size=Decimal("0.01"),
            step_size=Decimal("0.00001"),
            min_notional=Decimal("5.0"),
            min_qty=Decimal("0.00001"),
        )
        risk_config = RiskConfig(
            max_notional_usdt=Decimal("2000.00"),
            max_planned_loss_usdt=Decimal("100.00"),
            fee_rate_bps=Decimal("10.0"),
            slippage_bps=Decimal("5.0"),
            max_wait_duration_ms=args.horizon * 60 * 1000,
            max_entry_deviation_pct=Decimal("0.002"),
            freshness_tolerance_ms=120000,
            max_event_lag_ms=5000,
            cost_model_source="vip0-doc",
        )
        labeler = FirstTouchLabeler()
        lookback = 60
        horizon_ms = args.horizon * 60 * 1000
        step = 6

        # Strict zero-lookahead: evaluation must strictly be out-of-sample after train_cutoff_ms
        test_candles = [c for c in candles if c.open_time_ms > artifact.train_cutoff_ms]
        if len(test_candles) < lookback + 10:
            print(
                f"Error: Insufficient test candles strictly after artifact train cutoff ({artifact.train_cutoff_ms}). "
                f"Found {len(test_candles)} candles. OOS evaluation requires at least {lookback + 10} candles."
            )
            return 1

        outcomes = []
        eval_start_ms = test_candles[lookback].close_time_ms

        for i in range(lookback, len(test_candles) - 1, step):
            vis = test_candles[: i + 1]
            decision_time = vis[-1].close_time_ms
            plan, _, _ = engine.create_candidate(
                candles=vis,
                decision_time_ms=decision_time,
                available_cutoff_ms=decision_time,
                symbol_filters=symbol_filters,
                risk_config=risk_config,
            )
            confirmed_plan = None
            confirmation_time_ms = 0
            if plan and plan.candidate_state == CandidateState.WAITING:
                curr_p = plan
                for f_idx in range(i + 1, min(i + 6, len(test_candles))):
                    nc = test_candles[f_idx]
                    avail_time = nc.close_time_ms + engine.assumed_latency_ms
                    curr_p, adv_dec, adv_reasons = engine.advance_candidate(
                        locked_plan=curr_p,
                        new_candles=[nc],
                        current_time_ms=avail_time,
                    )
                    if adv_dec in (ObservationDecision.WATCH_ONLY, ObservationDecision.BUY_ELIGIBLE):
                        confirmed_plan = curr_p
                        confirmation_time_ms = avail_time
                        break
                    if adv_dec == ObservationDecision.SKIP or curr_p.candidate_state in (
                        CandidateState.INVALIDATED,
                        CandidateState.EXPIRED,
                    ):
                        break

            if confirmed_plan and confirmation_time_ms > 0:
                deadline_ms = confirmation_time_ms + horizon_ms
                forward = [
                    c for c in test_candles
                    if c.open_time_ms >= confirmation_time_ms and c.open_time_ms < deadline_ms
                ]
                if forward:
                    p_entry = confirmed_plan.entry_zone.proposed_entry
                    in_horizon_candles = [c for c in forward if (c.close_time_ms + 1) <= deadline_ms]
                    fill_idx = next(
                        (idx for idx, c in enumerate(in_horizon_candles) if Decimal(str(c.low)) <= p_entry <= Decimal(str(c.high))),
                        None,
                    )
                    if fill_idx is not None:
                        fill_candle = in_horizon_candles[fill_idx]
                        path_candles = forward[fill_idx:]
                        res = labeler.evaluate_path(
                            entry_price=p_entry,
                            target_price=confirmed_plan.target_price,
                            stop_price=confirmed_plan.stop_price,
                            entry_time_ms=fill_candle.open_time_ms,
                            deadline_ms=deadline_ms,
                            candles=path_candles,
                        )
                        outcomes.append(res.outcome)

        metrics = BarrierArtifactManager.compute_multiclass_metrics(
            p_tp=artifact.p_tp,
            p_sl=artifact.p_sl,
            p_timeout=artifact.p_timeout,
            outcomes=outcomes,
            eval_start_ms=eval_start_ms,
        )
        out_dir = Path(args.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        report_path = out_dir / f"eval_{artifact.artifact_hash}.json"
        report_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
        print(f"Evaluation report written: {report_path}")
        print(f"Brier score: {metrics['brier_score']}")
        print(f"Log loss: {metrics['log_loss']}")
        print(f"Test samples: {metrics['test_samples']}")
        return 0

    if args.command == "approve-entry-artifact":
        import json
        from shootingstar.application.barrier_evaluation import BarrierArtifactManager

        art_path = Path(args.artifact)
        rep_path = Path(args.evaluation_report)
        if not art_path.exists():
            print(f"Error: Artifact path '{args.artifact}' does not exist.")
            return 1
        if not rep_path.exists():
            print(f"Error: Evaluation report '{args.evaluation_report}' does not exist.")
            return 1

        report = json.loads(rep_path.read_text(encoding="utf-8"))
        try:
            approved = BarrierArtifactManager.approve_artifact(
                artifact_path=art_path,
                eval_report=report,
                approver=args.approver,
            )
            print(f"Success: Artifact {approved.artifact_hash} APPROVED.")
            print(f"Verdict: {approved.approval_verdict}")
            return 0
        except ValueError as err:
            print(f"Approval failed: {err}")
            return 1

if __name__ == "__main__":
    sys.exit(main())
