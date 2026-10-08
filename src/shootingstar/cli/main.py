"""Command Line Interface for ShootingStar."""

import argparse
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

    # Command: list-snapshots
    subparsers.add_parser("list-snapshots", help="List snapshots stored in PostgreSQL database")

    # Command: show-snapshot
    show_parser = subparsers.add_parser("show-snapshot", help="Show snapshot metadata from PostgreSQL database")
    show_parser.add_argument("--id", required=True, help="Snapshot SHA-256 hash or ID")

    return parser


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
        print(f"=== Starting Binance Pilot Ingestion: {args.symbol} {args.timeframe} ({args.days} days) ===")
        service = PilotIngestionService()
        try:
            result = service.run_pilot(
                symbol=args.symbol,
                timeframe_str=args.timeframe,
                days=args.days,
            )
            report = result.report
            print("\n=== Pilot Ingestion & Quality Report ===")
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

            # Persist to PostgreSQL
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
                print(f"Database Record:      SAVED & COMMITTED in PostgreSQL (run_id={run_id[:8]}..., snapshot_id={result.snapshot_sha256[:8]}...)")

            print("\n[NOTE] 30-day pilot verifies data quality only; it does NOT constitute model evaluation.")
            return 0
        except BinanceBannedError as e:
            logger.critical("HALTING: %s", e)
            return 2
        except BinanceRateLimitError as e:
            logger.error("Rate limit error: %s", e)
            return 1
        except Exception as e:
            logger.error("Pilot ingestion failed: %s", e)
            return 1

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

    return 0


if __name__ == "__main__":
    sys.exit(main())
