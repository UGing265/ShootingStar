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
    # Command: serve
    serve_parser = subparsers.add_parser("serve", help="Launch the ShootingStar Research Platform web server")
    serve_parser.add_argument("--host", default="127.0.0.1", help="Host interface (default: 127.0.0.1)")
    serve_parser.add_argument("--port", type=int, default=8000, help="Port (default: 8000)")
    serve_parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")

    # Command: watch-entry
    watch_parser = subparsers.add_parser("watch-entry", help="Run local public watcher for BTCUSDT fast entry setups")
    watch_parser.add_argument("--symbol", default="BTCUSDT", help="Trading pair symbol (default: BTCUSDT)")
    watch_parser.add_argument("--config", required=True, help="Path to JSON risk configuration file")
    watch_parser.add_argument("--once", action="store_true", help="Run a single evaluation cycle and exit")

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

if __name__ == "__main__":
    sys.exit(main())
