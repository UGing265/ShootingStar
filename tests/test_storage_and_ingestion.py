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
    assert c.is_backfill is False

    # Round-trip backfilled candle
    backfill_candle = Candle(
        venue="BINANCE",
        symbol="BTCUSDT",
        timeframe="1m",
        open_time_ms=1700000060000,
        close_time_ms=1700000119999,
        open=50050.0,
        high=50100.0,
        low=50000.0,
        close=50080.0,
        volume=3.0,
        quote_volume=150000.0,
        trades_count=30,
        taker_buy_base_volume=1.5,
        taker_buy_quote_volume=75000.0,
        observed_ingested_at_ms=None,
        is_backfill=True,
    )
    bf_path, _ = storage.save_snapshot([backfill_candle], "BINANCE", "BTCUSDT", "1m")
    bf_loaded = storage.load_snapshot(bf_path)
    assert len(bf_loaded) == 1
    assert bf_loaded[0].is_backfill is True
    assert bf_loaded[0].observed_ingested_at_ms is None

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

    base_time = 1700000000000
    mock_rows = [
        [base_time, "100.0", "101.0", "99.0", "100.5", "10.0", base_time + 59999, "1005.0", 10, "5.0", "502.5", "0"],
        [base_time + 60000, "100.5", "102.0", "100.0", "101.5", "12.0", base_time + 119999, "1218.0", 12, "6.0", "609.0", "0"],
        [base_time + 120000, "101.5", "103.0", "101.0", "102.5", "8.0", base_time + 179999, "820.0", 8, "4.0", "410.0", "0"],
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
        start_time_ms=base_time,
        end_time_ms=base_time + 179999,
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

def test_pilot_ingestion_requested_window_missing_edge_candles_detection(tmp_path: Path):
    """Verifies that missing leading and trailing candles in requested window are detected."""
    raw_dir = tmp_path / "raw"
    snap_dir = tmp_path / "snapshots"
    raw_storage = RawArchiveStorage(raw_dir=raw_dir)
    snap_storage = SnapshotStorage(snapshots_dir=snap_dir)

    # Window requests 5 candles (0, 60k, 120k, 180k, 240k), but client only returns middle 3 (60k, 120k, 180k)
    base_time = 1700000000000
    mock_rows = [
        [base_time + 60000, "100.5", "102.0", "100.0", "101.5", "12.0", base_time + 119999, "1218.0", 12, "6.0", "609.0", "0"],
        [base_time + 120000, "101.5", "103.0", "101.0", "102.5", "8.0", base_time + 179999, "820.0", 8, "4.0", "410.0", "0"],
        [base_time + 180000, "102.5", "104.0", "102.0", "103.0", "15.0", base_time + 239999, "1545.0", 15, "7.0", "721.0", "0"],
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
        start_time_ms=base_time,
        end_time_ms=base_time + 299999,
    )

    # Expected 5 candles, returned 3 -> 2 missing (1 leading at 0, 1 trailing at 240k)
    assert result.report.total_expected_intervals == 5
    assert result.report.valid_candles_count == 3
    assert result.report.missing_intervals_count == 2
    assert result.report.is_pristine is False
    assert result.report.coverage_ratio == 0.60

def test_snapshot_storage_load_snapshot_window(tmp_path: Path):
    storage = SnapshotStorage(snapshots_dir=tmp_path)
    base_time = 1700000000000
    candles = [
        Candle(
            venue="BINANCE",
            symbol="BTCUSDT",
            timeframe="1m",
            open_time_ms=base_time + i * 60000,
            close_time_ms=base_time + (i + 1) * 60000 - 1,
            open=50000.0 + i,
            high=50010.0 + i,
            low=49990.0 + i,
            close=50005.0 + i,
            volume=1.0 + i,
            quote_volume=50000.0,
            trades_count=10,
            taker_buy_base_volume=0.5,
            taker_buy_quote_volume=25000.0,
        )
        for i in range(10)
    ]

    snap_path, sha_hash = storage.save_snapshot(candles, "BINANCE", "BTCUSDT", "1m")
    assert snap_path.exists()

    # Test window with start and end
    window = storage.load_snapshot_window(
        snap_path,
        start_ms=base_time + 2 * 60000,
        end_ms=base_time + 5 * 60000 - 1,
    )
    assert len(window) == 3
    assert window[0].open_time_ms == base_time + 2 * 60000
    assert window[-1].open_time_ms == base_time + 4 * 60000

    # Test limit
    limited = storage.load_snapshot_window(
        snap_path,
        start_ms=base_time,
        limit=2,
    )
    assert len(limited) == 2
    assert limited[0].open_time_ms == base_time
    assert limited[1].open_time_ms == base_time + 60000


def test_cli_time_parsing():
    from shootingstar.cli.main import parse_time_arg

    assert parse_time_arg(None) is None
    assert parse_time_arg("") is None
    assert parse_time_arg("1700000000000") == 1700000000000
    iso_ms = parse_time_arg("2024-03-01T00:00:00Z")
    assert iso_ms == 1709251200000
    iso_naive_ms = parse_time_arg("2024-03-01T00:00:00")
    assert iso_naive_ms == 1709251200000


def test_binance_client_418_ip_banned_halts_immediately():
    from unittest.mock import MagicMock, patch
    import httpx
    from shootingstar.adapters.binance import BinanceSpotClient, BinanceBannedError

    client = BinanceSpotClient(base_url="https://mock.binance.test")
    mock_resp = MagicMock()
    mock_resp.status_code = 418
    mock_resp.headers = {"x-mbx-used-weight-1m": "100"}

    with patch("httpx.Client.get", return_value=mock_resp) as mock_get:
        import pytest
        with pytest.raises(BinanceBannedError, match="HTTP 418"):
            client.fetch_klines_with_raw("BTCUSDT", "1m", start_time_ms=1700000000000)
        # Must halt immediately without retrying
        assert mock_get.call_count == 1


def test_binance_client_429_retries_and_exhausts():
    from unittest.mock import MagicMock, patch
    import pytest
    from shootingstar.adapters.binance import BinanceSpotClient, BinanceRateLimitError

    client = BinanceSpotClient(base_url="https://mock.binance.test")
    mock_resp = MagicMock()
    mock_resp.status_code = 429
    mock_resp.headers = {"x-mbx-used-weight-1m": "1200", "Retry-After": "1"}

    with patch("httpx.Client.get", return_value=mock_resp) as mock_get, \
         patch("time.sleep") as mock_sleep:
        with pytest.raises(BinanceRateLimitError, match="HTTP 429"):
            client.fetch_klines_with_raw("BTCUSDT", "1m", start_time_ms=1700000000000)
        assert mock_get.call_count == 3
        assert mock_sleep.call_count == 2


def test_binance_client_429_recovers_on_retry():
    from unittest.mock import MagicMock, patch
    import json
    from shootingstar.adapters.binance import BinanceSpotClient

    client = BinanceSpotClient(base_url="https://mock.binance.test")
    mock_429 = MagicMock()
    mock_429.status_code = 429
    mock_429.headers = {"x-mbx-used-weight-1m": "1200", "Retry-After": "2"}

    mock_200 = MagicMock()
    mock_200.status_code = 200
    mock_200.headers = {"x-mbx-used-weight-1m": "50"}
    mock_rows = [[1700000000000, "100", "101", "99", "100.5", "10", 1700000059999, "1005", 10, "5", "502.5", "0"]]
    mock_200.json.return_value = mock_rows
    mock_200.content = json.dumps(mock_rows).encode("utf-8")
    mock_200.raise_for_status.return_value = None

    with patch("httpx.Client.get", side_effect=[mock_429, mock_200]) as mock_get, \
         patch("time.sleep") as mock_sleep:
        rows, raw_bytes, headers = client.fetch_klines_with_raw("BTCUSDT", "1m", start_time_ms=1700000000000)
        assert len(rows) == 1
        assert mock_get.call_count == 2
        mock_sleep.assert_called_once_with(2)


def test_preview_ingestion_non_persistent(tmp_path: Path):
    from unittest.mock import MagicMock
    from shootingstar.application.ingestion import preview_ingestion

    base_time = 1700000000000
    mock_rows = [
        [base_time, "100.0", "105.0", "99.0", "102.0", "10.0", base_time + 59999, "1020.0", 10, "5.0", "510.0", "0"],
        [base_time + 60000, "102.0", "106.0", "101.0", "104.0", "12.0", base_time + 119999, "1248.0", 12, "6.0", "624.0", "0"],
    ]

    mock_client = MagicMock()
    mock_client.fetch_klines_with_raw.return_value = (mock_rows, b"[]", {})

    candles, est_count, quality = preview_ingestion(
        symbol="BTCUSDT",
        timeframe="1m",
        start_time_ms=base_time,
        end_time_ms=base_time + 180000,
        client=mock_client,
        sample_limit=10,
    )

    assert len(candles) == 2
    assert candles[0].open == 100.0
    assert candles[1].close == 104.0
    assert est_count >= 3
    assert quality == "SAMPLE_OK_FULL_RANGE_UNCHECKED"
    mock_client.fetch_klines_with_raw.assert_called_once()


def test_snapshot_tampering_caught_by_direct_sha256(tmp_path: Path):
    import hashlib
    import os
    from shootingstar.api.read_routes import _verify_snapshot_checksum

    test_file = tmp_path / "tamper_test.bin"
    original_bytes = b"abcdefghijklmnopqrstuvwxyz0123456789"
    test_file.write_bytes(original_bytes)
    orig_sha = hashlib.sha256(original_bytes).hexdigest()
    orig_stat = test_file.stat()

    assert _verify_snapshot_checksum(test_file, orig_sha) is True

    # Tamper with content but keep exact same size and restore mtime
    tampered_bytes = b"xbcdefghijklmnopqrstuvwxyz0123456789"
    assert len(tampered_bytes) == len(original_bytes)
    test_file.write_bytes(tampered_bytes)
    os.utime(test_file, (orig_stat.st_atime, orig_stat.st_mtime))

    # Must detect tampering immediately
    assert _verify_snapshot_checksum(test_file, orig_sha) is False


def test_binance_client_timeout_retries_and_exhausts():
    from unittest.mock import MagicMock, patch
    import httpx
    import pytest
    from shootingstar.adapters.binance import BinanceSpotClient, BinanceTimeoutError

    client = BinanceSpotClient(base_url="https://mock.binance.test")

    with patch("httpx.Client.get", side_effect=httpx.ReadTimeout("Connection read timed out")) as mock_get, \
         patch("time.sleep") as mock_sleep:
        with pytest.raises(BinanceTimeoutError, match="timed out after 3 attempts"):
            client.fetch_klines_with_raw("BTCUSDT", "1m", start_time_ms=1700000000000)
        assert mock_get.call_count == 3
        assert mock_sleep.call_count == 2


def test_binance_client_timeout_recovers_on_retry():
    from unittest.mock import MagicMock, patch
    import httpx
    import json
    from shootingstar.adapters.binance import BinanceSpotClient

    client = BinanceSpotClient(base_url="https://mock.binance.test")
    mock_200 = MagicMock()
    mock_200.status_code = 200
    mock_200.headers = {"x-mbx-used-weight-1m": "10"}
    mock_rows = [[1700000000000, "100", "101", "99", "100.5", "10", 1700000059999, "1005", 10, "5", "502.5", "0"]]
    mock_200.json.return_value = mock_rows
    mock_200.content = json.dumps(mock_rows).encode("utf-8")
    mock_200.raise_for_status.return_value = None

    with patch("httpx.Client.get", side_effect=[httpx.ReadTimeout("timeout"), mock_200]) as mock_get, \
         patch("time.sleep") as mock_sleep:
        rows, _, _ = client.fetch_klines_with_raw("BTCUSDT", "1m", start_time_ms=1700000000000)
        assert len(rows) == 1
        assert mock_get.call_count == 2
        mock_sleep.assert_called_once_with(1.0)
