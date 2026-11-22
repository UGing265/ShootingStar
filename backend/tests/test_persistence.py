"""Integration tests for PostgreSQL persistence, migrations, and provenance constraints.

Executes strictly against the Alembic-migrated database schema.
"""

import os
import uuid
import pytest
from alembic.config import Config
from alembic import command
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from shootingstar.adapters.db.models import (
    AuditLogModel,
    CanonicalCandleModel,
    IngestionRunModel,
    RejectedRecordModel,
    SnapshotModel,
)
from shootingstar.adapters.db.repository import (
    AuditLogRepository,
    CanonicalCandleRepository,
    IngestionRunRepository,
    RejectedRecordRepository,
    SnapshotRepository,
)
from shootingstar.adapters.db.session import get_database_url



def test_canonical_candle_repository(db_session: Session):
    repo = CanonicalCandleRepository(db_session)
    open_time = 1700000000000
    c1 = CanonicalCandleModel(
        venue="BINANCE",
        symbol="BTCUSDT",
        timeframe="5m",
        open_time_ms=open_time,
        close_time_ms=open_time + 300000 - 1,
        open=50000.0,
        high=50100.0,
        low=49900.0,
        close=50050.0,
        volume=10.0,
        quote_volume=500000.0,
        trades_count=100,
        taker_buy_base_volume=5.0,
        taker_buy_quote_volume=250000.0,
        observed_ingested_at_ms=open_time + 300500,
    )
    repo.save(c1)

    candles = repo.get_range("BINANCE", "BTCUSDT", "5m", open_time, open_time + 300000)
    assert len(candles) >= 1
    assert candles[0].close == 50050.0

    # Test uniqueness
    dup = CanonicalCandleModel(
        venue="BINANCE",
        symbol="BTCUSDT",
        timeframe="5m",
        open_time_ms=open_time,
        close_time_ms=open_time + 300000 - 1,
        open=50000.0,
        high=50100.0,
        low=49900.0,
        close=50050.0,
        volume=10.0,
        quote_volume=500000.0,
        trades_count=100,
        taker_buy_base_volume=5.0,
        taker_buy_quote_volume=250000.0,
    )
    with pytest.raises(IntegrityError):
        repo.save(dup)


def test_rejected_record_repository(db_session: Session):
    repo = RejectedRecordRepository(db_session)
    rej = repo.record_rejection(
        venue="BINANCE",
        symbol="BTCUSDT",
        timeframe="5m",
        rejection_reason="high < low invariant violation",
        raw_payload_preview="[1700000000000, 100, 90, 110, 105...]",
        ingested_at_ms=1700000301000,
        timestamp_ms=1700000000000,
    )
    assert rej.id is not None
    assert rej.rejection_reason == "high < low invariant violation"


def test_ingestion_run_and_snapshot_repositories(db_session: Session):
    run_repo = IngestionRunRepository(db_session)
    snap_repo = SnapshotRepository(db_session)

    run_id = str(uuid.uuid4())
    run = IngestionRunModel(
        id=run_id,
        venue="BINANCE",
        symbol="BTCUSDT",
        timeframe="5m",
        start_time_ms=1700000000000,
        end_time_ms=1700086400000,
        valid_candles_count=288,
        missing_intervals_count=0,
        duplicate_candles_count=0,
        coverage_ratio=1.0,
        is_pristine=True,
        raw_files_count=1,
    )
    run_repo.save(run)

    loaded_run = run_repo.get_by_id(run_id)
    assert loaded_run is not None
    assert loaded_run.valid_candles_count == 288
    all_runs = run_repo.list_all(limit=10)
    assert any(r.id == run_id for r in all_runs)

    snap_hash = uuid.uuid4().hex + uuid.uuid4().hex
    snapshot = SnapshotModel(
        id=snap_hash,
        ingestion_run_id=run_id,
        venue="BINANCE",
        symbol="BTCUSDT",
        timeframe="5m",
        start_time_ms=1700000000000,
        end_time_ms=1700086400000,
        candle_count=288,
        file_path="data/snapshots/sample.parquet",
        sha256=snap_hash,
    )
    snap_repo.save(snapshot)

    loaded_snap = snap_repo.get_by_sha256(snap_hash)
    assert loaded_snap is not None
    assert loaded_snap.ingestion_run_id == run_id
    assert loaded_snap.candle_count == 288
    all_snaps = snap_repo.list_all(limit=10)
    assert any(s.id == snap_hash for s in all_snaps)




def test_audit_log_repository(db_session: Session):
    audit_repo = AuditLogRepository(db_session)
    log = audit_repo.record(
        entity_type="EXPERIMENT",
        entity_id="exp_test_001",
        action="CREATE",
        details={"user": "operator", "reason": "model validation"},
    )
    assert log.id is not None
    assert log.entity_type == "EXPERIMENT"
    assert log.action == "CREATE"
