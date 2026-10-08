"""Pilot ingestion service for market data."""

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional, Tuple

from shootingstar.adapters.binance import BinanceSpotClient
from shootingstar.adapters.storage import RawArchiveStorage, SnapshotStorage
from shootingstar.application.contracts import QualityInspectorService
from shootingstar.domain.exceptions import DomainError
from shootingstar.domain.models import Candle, DataQualityReport, Timeframe

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IngestionResult:
    report: DataQualityReport
    snapshot_path: Path
    snapshot_sha256: str
    raw_files_count: int
    raw_file_paths: List[Path]


class PilotIngestionService:
    """Orchestrates bounded ingestion, raw archiving, quality validation, and immutable snapshots."""

    def __init__(
        self,
        client: Optional[BinanceSpotClient] = None,
        raw_storage: Optional[RawArchiveStorage] = None,
        snapshot_storage: Optional[SnapshotStorage] = None,
    ):
        self.client = client or BinanceSpotClient()
        self.raw_storage = raw_storage or RawArchiveStorage()
        self.snapshot_storage = snapshot_storage or SnapshotStorage()
    def run_pilot(
        self,
        symbol: str = "BTCUSDT",
        timeframe_str: str = "1m",
        days: int = 30,
        start_time_ms: Optional[int] = None,
        end_time_ms: Optional[int] = None,
    ) -> IngestionResult:
        """Fetches bounded pilot history from Binance Spot public API.
        
        Strictly excludes any currently forming/unclosed candles.
        """
        tf = Timeframe(timeframe_str)
        now_ms = int(time.time() * 1000)

        if start_time_ms is not None or end_time_ms is not None:
            if start_time_ms is None or end_time_ms is None:
                raise DomainError("Both start_time_ms and end_time_ms must be provided for an explicit window.")
            target_start_ms = start_time_ms
            target_end_ms = min(end_time_ms, now_ms - (now_ms % tf.duration_ms) - 1)
        else:
            if days <= 0:
                raise DomainError(f"days must be positive when using relative window: {days}")
            target_end_ms = now_ms - (now_ms % tf.duration_ms) - 1
            target_start_ms = target_end_ms - (days * 24 * 60 * 60 * 1000)

        if target_start_ms > target_end_ms:
            raise DomainError(f"target_start_ms ({target_start_ms}) cannot be after target_end_ms ({target_end_ms})")
        logger.info(
            "Starting pilot ingestion for %s %s from %s to %s (%d days)",
            symbol, tf.value, target_start_ms, target_end_ms, days,
        )

        all_candles: List[Candle] = []
        raw_file_paths: List[Path] = []
        current_cursor_start = target_start_ms
        page_index = 0

        while current_cursor_start <= target_end_ms:
            page_index += 1
            raw_rows, raw_bytes, headers = self.client.fetch_klines_with_raw(
                symbol=symbol,
                interval=tf.value,
                start_time_ms=current_cursor_start,
                end_time_ms=target_end_ms,
                limit=1000,
            )

            if not raw_rows:
                logger.info("No more klines returned by API.")
                break

            ingested_receipt_ms = int(time.time() * 1000)

            # 1. Archive exact wire bytes and metadata
            raw_path, raw_hash = self.raw_storage.save_raw_response(
                venue="BINANCE",
                symbol=symbol,
                timeframe=tf.value,
                page_index=page_index,
                start_time_ms=current_cursor_start,
                end_time_ms=target_end_ms,
                raw_bytes=raw_bytes,
                metadata={
                    "client_used_weight_1m": self.client.last_used_weight_1m,
                    "ingested_at_ms": ingested_receipt_ms,
                    "headers": headers,
                },
            )
            raw_file_paths.append(raw_path)

            # 2. Parse and filter
            highest_received_open_time = max(int(row[0]) for row in raw_rows)
            for row in raw_rows:
                candle = self.client.parse_kline_row(
                    row=row,
                    venue="BINANCE",
                    symbol=symbol,
                    timeframe=tf.value,
                )
                candle = Candle(
                    venue=candle.venue,
                    symbol=candle.symbol,
                    timeframe=candle.timeframe,
                    open_time_ms=candle.open_time_ms,
                    close_time_ms=candle.close_time_ms,
                    open=candle.open,
                    high=candle.high,
                    low=candle.low,
                    close=candle.close,
                    volume=candle.volume,
                    quote_volume=candle.quote_volume,
                    trades_count=candle.trades_count,
                    taker_buy_base_volume=candle.taker_buy_base_volume,
                    taker_buy_quote_volume=candle.taker_buy_quote_volume,
                    observed_ingested_at_ms=ingested_receipt_ms,
                )

                # Strictly drop out-of-bound or forming candles
                if candle.open_time_ms < target_start_ms or candle.close_time_ms > target_end_ms:
                    continue

                all_candles.append(candle)

            # Advance cursor: Binance open times are inclusive
            next_cursor = highest_received_open_time + 1
            if next_cursor <= current_cursor_start:
                # No forward progress
                break
            current_cursor_start = next_cursor

            # Bounded sleep to prevent aggressive API hammering
            time.sleep(0.05)

        if not all_candles:
            raise DomainError(f"No valid candles obtained for {symbol} {tf.value} in target window.")

        # 3. Inspect quality
        sorted_candles = sorted(all_candles, key=lambda c: c.open_time_ms)
        first_ms = sorted_candles[0].open_time_ms
        last_ms = sorted_candles[-1].close_time_ms

        report = QualityInspectorService.inspect(
            candles=sorted_candles,
            venue="BINANCE",
            symbol=symbol,
            timeframe=tf,
            start_time_ms=first_ms,
            end_time_ms=last_ms,
        )

        # 4. Save immutable snapshot
        snapshot_path, snapshot_sha256 = self.snapshot_storage.save_snapshot(
            candles=sorted_candles,
            venue="BINANCE",
            symbol=symbol,
            timeframe=tf.value,
        )

        logger.info(
            "Pilot complete: %d valid candles, coverage %.2f%%, snapshot %s (sha256 %s)",
            report.valid_candles_count,
            report.coverage_ratio * 100,
            snapshot_path.name,
            snapshot_sha256[:10],
        )

        return IngestionResult(
            report=report,
            snapshot_path=snapshot_path,
            snapshot_sha256=snapshot_sha256,
            raw_files_count=len(raw_file_paths),
            raw_file_paths=raw_file_paths,
        )

    def rebuild_snapshot_from_raw_archive(
        self,
        raw_paths: List[Path],
        venue: str,
        symbol: str,
        timeframe_str: str,
        start_time_ms: int,
        end_time_ms: int,
    ) -> Tuple[Path, str]:
        """Rebuilds an immutable snapshot bit-for-bit from archived raw JSON payloads."""
        tf = Timeframe(timeframe_str)
        all_candles: List[Candle] = []

        for p in raw_paths:
            rows, meta = self.raw_storage.load_raw_page(p)
            receipt_ms = meta.get("metadata", {}).get("ingested_at_ms")
            for row in rows:
                candle = self.client.parse_kline_row(row, venue, symbol, tf.value)
                candle = Candle(
                    venue=candle.venue,
                    symbol=candle.symbol,
                    timeframe=candle.timeframe,
                    open_time_ms=candle.open_time_ms,
                    close_time_ms=candle.close_time_ms,
                    open=candle.open,
                    high=candle.high,
                    low=candle.low,
                    close=candle.close,
                    volume=candle.volume,
                    quote_volume=candle.quote_volume,
                    trades_count=candle.trades_count,
                    taker_buy_base_volume=candle.taker_buy_base_volume,
                    taker_buy_quote_volume=candle.taker_buy_quote_volume,
                    observed_ingested_at_ms=receipt_ms,
                )
                if candle.open_time_ms < start_time_ms or candle.close_time_ms > end_time_ms:
                    continue
                all_candles.append(candle)

        seen_keys = set()
        unique_candles = []
        for c in sorted(all_candles, key=lambda x: x.open_time_ms):
            if c.key not in seen_keys:
                seen_keys.add(c.key)
                unique_candles.append(c)

        return self.snapshot_storage.save_snapshot(
            candles=unique_candles,
            venue=venue,
            symbol=symbol,
            timeframe=tf.value,
        )
