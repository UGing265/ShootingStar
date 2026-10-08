"""Command Line Interface for ShootingStar."""

import argparse
import logging
import sys
from shootingstar import __version__
from shootingstar.adapters.binance import BinanceBannedError, BinanceRateLimitError
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

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "info":
        print(f"ShootingStar v{__version__} - Evidence-first 30-minute research platform")
        print("Status: Local-first research engine")
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

    return 0


if __name__ == "__main__":
    sys.exit(main())
