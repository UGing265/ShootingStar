"""Pilot ingestion service for market data."""

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional, Tuple
import uuid

from shootingstar.adapters.db.models import IngestionRunModel, SnapshotModel
from shootingstar.adapters.db.repository import IngestionRunRepository, SnapshotRepository
from shootingstar.adapters.db.session import get_db_session
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
                    observed_ingested_at_ms=None,
                    is_backfill=True,
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

        # 3. Inspect quality across requested window
        sorted_candles = sorted(all_candles, key=lambda c: c.open_time_ms)

        report = QualityInspectorService.inspect(
            candles=sorted_candles,
            venue="BINANCE",
            symbol=symbol,
            timeframe=tf,
            start_time_ms=target_start_ms,
            end_time_ms=target_end_ms,
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
                    observed_ingested_at_ms=None,
                    is_backfill=True,
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

def execute_and_persist_ingestion(
    symbol: str = "BTCUSDT",
    timeframe: str = "1m",
    start_time_ms: Optional[int] = None,
    end_time_ms: Optional[int] = None,
    days: int = 30,
) -> Tuple[IngestionResult, str, str]:
    """Runs ingestion from Binance Spot and transactionally persists IngestionRun and Snapshot."""
    service = PilotIngestionService()
    result = service.run_pilot(
        symbol=symbol,
        timeframe_str=timeframe,
        days=days,
        start_time_ms=start_time_ms,
        end_time_ms=end_time_ms,
    )
    report = result.report

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

    return result, run_id, result.snapshot_sha256


def preview_ingestion(
    symbol: str = "BTCUSDT",
    timeframe: str = "1m",
    start_time_ms: int = 0,
    end_time_ms: int = 0,
    client: Optional[BinanceSpotClient] = None,
    sample_limit: int = 50,
) -> Tuple[List[Candle], int, str]:
    """Previews an ingestion window without persisting raw bytes, parquet snapshots, or database records.

    Returns:
        (sample_candles, estimated_total_candles, quality_status)
    """
    client = client or BinanceSpotClient()
    tf = Timeframe(timeframe)
    duration_ms = tf.duration_ms
    expected_intervals = max(1, (end_time_ms - start_time_ms + 1) // duration_ms)

    rows, _, _ = client.fetch_klines_with_raw(
        symbol=symbol,
        interval=tf.value,
        start_time_ms=start_time_ms,
        end_time_ms=end_time_ms,
        limit=sample_limit,
    )

    if not rows:
        return [], expected_intervals, "EMPTY_RESPONSE"

    candles: List[Candle] = []
    for r in rows:
        candles.append(
            BinanceSpotClient.parse_kline_row(
                row=r,
                venue="BINANCE",
                symbol=symbol,
                timeframe=tf.value,
            )
        )

    # Detect sample gaps
    quality_status = "SAMPLE_OK_FULL_RANGE_UNCHECKED"
    for i in range(len(candles) - 1):
        if candles[i + 1].open_time_ms != candles[i].open_time_ms + duration_ms:
            quality_status = "SAMPLE_GAP_DETECTED"
            break
    return candles, expected_intervals, quality_status
