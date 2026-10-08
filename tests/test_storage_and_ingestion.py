"""Tests for storage adapters, pilot ingestion service, and reproducible snapshot hashing."""

import json
from pathlib import Path
import pytest
from shootingstar.adapters.binance import BinanceSpotClient
from shootingstar.adapters.storage import RawArchiveStorage, SnapshotStorage
from shootingstar.application.ingestion import PilotIngestionService
from shootingstar.domain.models import Candle, Timeframe


def test_raw_archive_storage_exact_wire_bytes(tmp_path: Path):
    storage = RawArchiveStorage(raw_dir=tmp_path)
    wire_bytes = b'[[1700000000000, "100.0", "105.0", "99.0", "102.0", "10.0", 1700000059999]]'

    raw_path, sha_hash = storage.save_raw_response(
        venue="BINANCE",
        symbol="BTCUSDT",
        timeframe="1m",
        page_index=1,
        start_time_ms=1700000000000,
        end_time_ms=1700000059999,
        raw_bytes=wire_bytes,
        metadata={"client_used_weight_1m": 2},
    )

    assert raw_path.exists()
    assert raw_path.read_bytes() == wire_bytes
    assert len(sha_hash) == 64

    # Load back
    loaded_data, metadata = storage.load_raw_page(raw_path)
    assert len(loaded_data) == 1
    assert loaded_data[0][0] == 1700000000000
    assert metadata["metadata"]["client_used_weight_1m"] == 2


def test_snapshot_storage_roundtrip_and_checksum(tmp_path: Path):
    storage = SnapshotStorage(snapshots_dir=tmp_path)
    candle = Candle(
        venue="BINANCE",
        symbol="BTCUSDT",
        timeframe="1m",
        open_time_ms=1700000000000,
        close_time_ms=1700000059999,
        open=50000.0,
        high=50100.0,
        low=49900.0,
        close=50050.0,
        volume=5.0,
        quote_volume=250000.0,
        trades_count=50,
        taker_buy_base_volume=2.5,
        taker_buy_quote_volume=125000.0,
        observed_ingested_at_ms=1700000061000,
    )

    file_path, sha_hash = storage.save_snapshot([candle], "BINANCE", "BTCUSDT", "1m")
    assert file_path.exists()
    assert len(sha_hash) == 64

    loaded = storage.load_snapshot(file_path)
    assert len(loaded) == 1
    c = loaded[0]
    assert c.open_time_ms == candle.open_time_ms
    assert c.close_time_ms == candle.close_time_ms
    assert c.open == candle.open
    assert c.high == candle.high
    assert c.low == candle.low
    assert c.close == candle.close
    assert c.observed_ingested_at_ms == 1700000061000


class MockBinanceClient:
    def __init__(self, rows):
        self.rows = rows
        self.last_used_weight_1m = 2

    def fetch_klines_with_raw(self, symbol, interval, start_time_ms, end_time_ms=None, limit=1000):
        matched = [r for r in self.rows if r[0] >= start_time_ms and (end_time_ms is None or r[0] <= end_time_ms)]
        raw_bytes = json.dumps(matched).encode("utf-8")
        return matched, raw_bytes, {"x-mbx-used-weight-1m": "2"}

    def parse_kline_row(self, row, venue, symbol, timeframe):
        return BinanceSpotClient.parse_kline_row(row, venue, symbol, timeframe)


def test_pilot_ingestion_service_with_mock(tmp_path: Path):
    raw_dir = tmp_path / "raw"
    snap_dir = tmp_path / "snapshots"
    raw_storage = RawArchiveStorage(raw_dir=raw_dir)
    snap_storage = SnapshotStorage(snapshots_dir=snap_dir)

    mock_rows = [
        [1700000000000, "100.0", "101.0", "99.0", "100.5", "10.0", 1700000059999, "1005.0", 10, "5.0", "502.5", "0"],
        [1700000060000, "100.5", "102.0", "100.0", "101.5", "12.0", 1700000119999, "1218.0", 12, "6.0", "609.0", "0"],
        [1700000120000, "101.5", "103.0", "101.0", "102.5", "8.0", 1700000179999, "820.0", 8, "4.0", "410.0", "0"],
    ]
    mock_client = MockBinanceClient(rows=mock_rows)

    service = PilotIngestionService(
        client=mock_client,
        raw_storage=raw_storage,
        snapshot_storage=snap_storage,
    )

    result = service.run_pilot(
        symbol="BTCUSDT",
        timeframe_str="1m",
        start_time_ms=1700000000000,
        end_time_ms=1700000179999,
    )

    assert result.report.valid_candles_count == 3
    assert result.report.missing_intervals_count == 0
    assert result.report.is_pristine is True
    assert result.snapshot_path.exists()
    assert result.raw_files_count >= 1


def test_exact_snapshot_hash_reproducibility_from_raw_archive(tmp_path: Path):
    raw_dir = tmp_path / "raw"
    snap_dir = tmp_path / "snapshots"
    raw_storage = RawArchiveStorage(raw_dir=raw_dir)
    snap_storage = SnapshotStorage(snapshots_dir=snap_dir)

    mock_rows = [
        [1700000000000, "100.0", "101.0", "99.0", "100.5", "10.0", 1700000059999, "1005.0", 10, "5.0", "502.5", "0"],
        [1700000060000, "100.5", "102.0", "100.0", "101.5", "12.0", 1700000119999, "1218.0", 12, "6.0", "609.0", "0"],
    ]
    mock_client = MockBinanceClient(rows=mock_rows)

    service = PilotIngestionService(
        client=mock_client,
        raw_storage=raw_storage,
        snapshot_storage=snap_storage,
    )

    # 1. First run creates initial snapshot
    original_result = service.run_pilot(
        symbol="BTCUSDT",
        timeframe_str="1m",
        start_time_ms=1700000000000,
        end_time_ms=1700000119999,
    )

    # 2. Replay/rebuild solely from the archived raw JSON files
    rebuilt_path, rebuilt_sha256 = service.rebuild_snapshot_from_raw_archive(
        raw_paths=original_result.raw_file_paths,
        venue="BINANCE",
        symbol="BTCUSDT",
        timeframe_str="1m",
        start_time_ms=1700000000000,
        end_time_ms=1700000119999,
    )

    # 3. Invariant: Checksum and file content must match identically
    assert rebuilt_sha256 == original_result.snapshot_sha256
    assert rebuilt_path.read_bytes() == original_result.snapshot_path.read_bytes()
