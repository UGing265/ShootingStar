"""Storage adapters for raw market data archives and immutable parquet snapshots."""

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import pyarrow as pa
import pyarrow.parquet as pq

from shootingstar.domain.models import Candle


class StoragePaths:
    """Standard local directory layout."""

    DATA_DIR = Path("data")
    RAW_DIR = DATA_DIR / "raw"
    SNAPSHOTS_DIR = DATA_DIR / "snapshots"
    LITERATURE_DIR = DATA_DIR / "literature"

    @classmethod
    def ensure_directories(cls) -> None:
        cls.RAW_DIR.mkdir(parents=True, exist_ok=True)
        cls.SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        cls.LITERATURE_DIR.mkdir(parents=True, exist_ok=True)


class RawArchiveStorage:
    """Stores exact raw external JSON payloads with checksums and metadata."""

    def __init__(self, raw_dir: Optional[Path] = None):
        self.raw_dir = raw_dir or StoragePaths.RAW_DIR
        self.raw_dir.mkdir(parents=True, exist_ok=True)

    def save_raw_response(
        self,
        venue: str,
        symbol: str,
        timeframe: str,
        page_index: int,
        start_time_ms: int,
        end_time_ms: int,
        raw_bytes: bytes,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Path, str]:
        """Saves exact wire HTTP response bytes and sidecar metadata JSON."""
        sha256_hash = hashlib.sha256(raw_bytes).hexdigest()
        base_name = f"{venue}_{symbol}_{timeframe}_p{page_index:04d}_{sha256_hash[:10]}"

        raw_path = self.raw_dir / f"{base_name}.raw.json"
        meta_path = self.raw_dir / f"{base_name}.meta.json"

        raw_path.write_bytes(raw_bytes)

        meta_payload = {
            "venue": venue,
            "symbol": symbol,
            "timeframe": timeframe,
            "page_index": page_index,
            "start_time_ms": start_time_ms,
            "end_time_ms": end_time_ms,
            "sha256": sha256_hash,
            "byte_size": len(raw_bytes),
            "metadata": metadata or {},
        }
        meta_path.write_text(json.dumps(meta_payload, indent=2, sort_keys=True), encoding="utf-8")
        return raw_path, sha256_hash

    def load_raw_page(self, raw_path: Path) -> Tuple[List[Any], Dict[str, Any]]:
        """Loads parsed JSON from raw wire bytes and associated metadata."""
        raw_bytes = raw_path.read_bytes()
        data = json.loads(raw_bytes.decode("utf-8"))
        meta_path = raw_path.with_name(raw_path.name.replace(".raw.json", ".meta.json"))
        metadata = {}
        if meta_path.exists():
            metadata = json.loads(meta_path.read_text(encoding="utf-8"))
        return data, metadata


class SnapshotStorage:
    """Manages immutable Parquet candle snapshots with SHA-256 provenance."""

    SCHEMA = pa.schema([
        ("venue", pa.string()),
        ("symbol", pa.string()),
        ("timeframe", pa.string()),
        ("open_time_ms", pa.int64()),
        ("close_time_ms", pa.int64()),
        ("open", pa.float64()),
        ("high", pa.float64()),
        ("low", pa.float64()),
        ("close", pa.float64()),
        ("volume", pa.float64()),
        ("quote_volume", pa.float64()),
        ("trades_count", pa.int64()),
        ("taker_buy_base_volume", pa.float64()),
        ("taker_buy_quote_volume", pa.float64()),
        ("observed_ingested_at_ms", pa.int64()),
        ("is_backfill", pa.bool_()),
    ])

    def __init__(self, snapshots_dir: Optional[Path] = None):
        self.snapshots_dir = snapshots_dir or StoragePaths.SNAPSHOTS_DIR
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)

    def save_snapshot(
        self,
        candles: List[Candle],
        venue: str,
        symbol: str,
        timeframe: str,
    ) -> Tuple[Path, str]:
        """Serializes validated candles to an immutable Parquet snapshot."""
        if not candles:
            raise ValueError("Cannot create empty snapshot")

        # Sort strictly by open_time_ms
        sorted_candles = sorted(candles, key=lambda c: c.open_time_ms)
        start_ms = sorted_candles[0].open_time_ms
        end_ms = sorted_candles[-1].close_time_ms

        columns = {
            "venue": [c.venue for c in sorted_candles],
            "symbol": [c.symbol for c in sorted_candles],
            "timeframe": [c.timeframe for c in sorted_candles],
            "open_time_ms": [c.open_time_ms for c in sorted_candles],
            "close_time_ms": [c.close_time_ms for c in sorted_candles],
            "open": [c.open for c in sorted_candles],
            "high": [c.high for c in sorted_candles],
            "low": [c.low for c in sorted_candles],
            "close": [c.close for c in sorted_candles],
            "volume": [c.volume for c in sorted_candles],
            "quote_volume": [c.quote_volume for c in sorted_candles],
            "trades_count": [c.trades_count for c in sorted_candles],
            "taker_buy_base_volume": [c.taker_buy_base_volume for c in sorted_candles],
            "taker_buy_quote_volume": [c.taker_buy_quote_volume for c in sorted_candles],
            "observed_ingested_at_ms": [
                c.observed_ingested_at_ms if c.observed_ingested_at_ms is not None else -1
                for c in sorted_candles
            ],
            "is_backfill": [bool(c.is_backfill) for c in sorted_candles],
        }

        table = pa.Table.from_pydict(columns, schema=self.SCHEMA)

        # Write to temporary file first to compute content hash
        temp_filename = f"temp_{venue}_{symbol}_{timeframe}_{start_ms}_{end_ms}.parquet"
        temp_path = self.snapshots_dir / temp_filename
        pq.write_table(table, temp_path, compression="zstd", row_group_size=1440)

        data_bytes = temp_path.read_bytes()
        sha256_hash = hashlib.sha256(data_bytes).hexdigest()

        final_filename = f"{venue}_{symbol}_{timeframe}_{start_ms}_{end_ms}_{sha256_hash[:10]}.parquet"
        final_path = self.snapshots_dir / final_filename

        if final_path.exists():
            temp_path.unlink()
        else:
            temp_path.rename(final_path)

        return final_path, sha256_hash

    def load_snapshot(self, path: Path) -> List[Candle]:
        """Loads and reconstructs domain Candles from a Parquet snapshot."""
        table = pq.read_table(path)
        pydict = table.to_pydict()
        count = len(pydict["open_time_ms"])
        has_backfill = "is_backfill" in pydict

        candles = []
        for i in range(count):
            ingested_at = pydict["observed_ingested_at_ms"][i]
            is_backfill = (
                bool(pydict["is_backfill"][i])
                if has_backfill
                else (ingested_at == -1 or ingested_at > pydict["close_time_ms"][i] + 60000)
            )
            candles.append(
                Candle(
                    venue=pydict["venue"][i],
                    symbol=pydict["symbol"][i],
                    timeframe=pydict["timeframe"][i],
                    open_time_ms=pydict["open_time_ms"][i],
                    close_time_ms=pydict["close_time_ms"][i],
                    open=pydict["open"][i],
                    high=pydict["high"][i],
                    low=pydict["low"][i],
                    close=pydict["close"][i],
                    volume=pydict["volume"][i],
                    quote_volume=pydict["quote_volume"][i],
                    trades_count=pydict["trades_count"][i],
                    taker_buy_base_volume=pydict["taker_buy_base_volume"][i],
                    taker_buy_quote_volume=pydict["taker_buy_quote_volume"][i],
                    observed_ingested_at_ms=ingested_at if ingested_at != -1 else None,
                    is_backfill=is_backfill,
                )
            )
        return candles

    def load_snapshot_window(
        self,
        path: Path,
        start_ms: Optional[int] = None,
        end_ms: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> List[Candle]:
        """Loads a bounded window of domain Candles using Parquet predicate pushdown."""
        filters = []
        if start_ms is not None:
            filters.append(("open_time_ms", ">=", start_ms))
        if end_ms is not None:
            filters.append(("close_time_ms", "<=", end_ms))

        table = pq.read_table(path, filters=filters if filters else None)
        if limit is not None and limit > 0:
            table = table.slice(0, limit)

        pydict = table.to_pydict()
        count = len(pydict["open_time_ms"])
        has_backfill = "is_backfill" in pydict

        candles = []
        for i in range(count):
            ingested_at = pydict["observed_ingested_at_ms"][i]
            is_backfill = (
                bool(pydict["is_backfill"][i])
                if has_backfill
                else (ingested_at == -1 or ingested_at > pydict["close_time_ms"][i] + 60000)
            )
            candles.append(
                Candle(
                    venue=pydict["venue"][i],
                    symbol=pydict["symbol"][i],
                    timeframe=pydict["timeframe"][i],
                    open_time_ms=pydict["open_time_ms"][i],
                    close_time_ms=pydict["close_time_ms"][i],
                    open=pydict["open"][i],
                    high=pydict["high"][i],
                    low=pydict["low"][i],
                    close=pydict["close"][i],
                    volume=pydict["volume"][i],
                    quote_volume=pydict["quote_volume"][i],
                    trades_count=pydict["trades_count"][i],
                    taker_buy_base_volume=pydict["taker_buy_base_volume"][i],
                    taker_buy_quote_volume=pydict["taker_buy_quote_volume"][i],
                    observed_ingested_at_ms=ingested_at if ingested_at != -1 else None,
                    is_backfill=is_backfill,
                )
            )
        return candles
