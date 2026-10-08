"""Command Line Interface for ShootingStar."""

import argparse
import sys
from shootingstar import __version__


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

    # Command: quality-check
    quality_parser = subparsers.add_parser("quality-check", help="Run local data quality verification")
    quality_parser.add_argument("--symbol", default="BTCUSDT", help="Trading pair symbol")
    quality_parser.add_argument("--timeframe", default="1m", choices=["1m", "5m"], help="Candle timeframe")

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "info":
        print(f"ShootingStar v{__version__} - Evidence-first 30-minute research platform")
        print("Status: Phase 1 Local foundation operational")
        return 0

    if args.command == "quality-check":
        print(f"Data quality inspector ready for symbol={args.symbol}, timeframe={args.timeframe}")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
