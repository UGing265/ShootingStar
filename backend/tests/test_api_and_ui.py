"""Tests for FastAPI read endpoints, schema validation, and Research UI.

Verifies strict security invariants and Phase 1 B1 contracts:
- Sanitized /health with DB offline, never leaking DB URL or credentials.
- Strict omission of raw file_path, artifact_path, and sensitive internal details.
- Validated candle extraction with SHA-256 integrity verification.
- Snapshot quality handling for both linked ingestion runs and legacy unlinked runs.
"""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from unittest.mock import patch
import uuid

import pytest
from starlette.testclient import TestClient


def _resolve_pilot_path() -> str:
    p = Path("data/snapshots/BINANCE_BTCUSDT_5m_1788894000000_1791485999999_97f6323ad2.parquet")
    if p.exists():
        return str(p)
    parent_p = Path("..") / p
    if parent_p.exists():
        return str(parent_p)
    
    # Create synthetic pilot snapshot deterministically if absent
    from shootingstar.adapters.storage import SnapshotStorage
    from shootingstar.domain.models import Candle
    target_dir = p.parent
    target_dir.mkdir(parents=True, exist_ok=True)
    candles = [
        Candle(
            venue="BINANCE",
            symbol="BTCUSDT",
            timeframe="5m",
            open_time_ms=1788894000000 + i * 300000,
            close_time_ms=1788894000000 + (i + 1) * 300000 - 1,
            open=42000.0 + i,
            high=42100.0 + i,
            low=41900.0 + i,
            close=42050.0 + i,
            volume=10.0,
            quote_volume=420000.0,
            trades_count=100,
            taker_buy_base_volume=5.0,
            taker_buy_quote_volume=210000.0,
        )
        for i in range(10)
    ]
    storage = SnapshotStorage(snapshots_dir=target_dir)
    saved_path, _ = storage.save_snapshot(candles, "BINANCE", "BTCUSDT", "5m")
    if saved_path.exists() and saved_path != p:
        try:
            saved_path.replace(p)
        except Exception:
            return str(saved_path)
    return str(p)
from shootingstar.adapters.db.models import (
    AuditLogModel,
    IngestionRunModel,
    SnapshotModel,
)
from shootingstar.adapters.db.repository import SnapshotRepository
from shootingstar.api.app import app


@pytest.fixture
def client(migrated_test_engine):
    """Provides a TestClient with migrated test DB."""
    return TestClient(app)


def test_api_health_endpoint_connected(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"
    assert data["database_status"] == "connected"
    assert "PostgreSQL" in data["engine"]
    assert "timestamp_utc" in data


def test_api_health_endpoint_db_offline_sanitized_no_secret_leak(client):
    secret_url = "postgresql://secret_user:super_secret_password_12345@127.0.0.1:5432/shootingstar_prod"

    # Simulate DB connection failure that would normally raise an exception containing secret URL
    with patch("shootingstar.api.read_routes.get_db_session") as mock_session:
        mock_session.side_effect = RuntimeError(f"Connection failed to {secret_url}")
        response = client.get("/health")

        # Must return 503 Service Unavailable
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "degraded"
        assert data["database"] == "offline"
        assert data["database_status"] == "offline"

        # Strict invariant: Response text must NEVER contain secret_user, password, or URL
        raw_text = response.text
        assert "super_secret_password" not in raw_text
        assert "secret_user" not in raw_text
        assert "shootingstar_prod" not in raw_text


def test_api_snapshots_omits_file_path(client, db_session):
    snap_repo = SnapshotRepository(db_session)
    sha = "test_snap_sha_" + uuid.uuid4().hex[:16]
    snap = SnapshotModel(
        id=sha,
        venue="BINANCE",
        symbol="BTCUSDT",
        timeframe="5m",
        start_time_ms=1000000,
        end_time_ms=2000000,
        candle_count=200,
        file_path="C:/sensitive/path/to/data.parquet",
        sha256=sha,
    )
    snap_repo.save(snap)
    db_session.commit()

    try:
        response = client.get("/snapshots?limit=50")
        assert response.status_code == 200
        snaps = response.json()
        assert isinstance(snaps, list)
        for s in snaps:
            # Invariant: file_path must NEVER be returned in SnapshotSummary
            assert "file_path" not in s
            assert "sha256" in s
            assert "candle_count" in s
    finally:
        db_session.delete(snap)
        db_session.commit()


def test_api_snapshot_quality_with_and_without_run(client, db_session):
    now = datetime.now(timezone.utc)

    # 1. Snapshot WITH linked IngestionRun
    run_id = "run_" + uuid.uuid4().hex[:12]
    run = IngestionRunModel(
        id=run_id,
        venue="BINANCE",
        symbol="BTCUSDT",
        timeframe="5m",
        start_time_ms=1000,
        end_time_ms=2000,
        valid_candles_count=100,
        missing_intervals_count=2,
        duplicate_candles_count=1,
        coverage_ratio=0.98,
        is_pristine=False,
        raw_files_count=1,
        created_at=now,
    )
    db_session.add(run)
    db_session.commit()

    sha_linked = "sha_linked_" + uuid.uuid4().hex[:16]
    snap_linked = SnapshotModel(
        id=sha_linked,
        ingestion_run_id=run_id,
        venue="BINANCE",
        symbol="BTCUSDT",
        timeframe="5m",
        start_time_ms=1000,
        end_time_ms=2000,
        candle_count=100,
        file_path="dummy.parquet",
        sha256=sha_linked,
        created_at=now,
    )
    db_session.add(snap_linked)

    # 2. Snapshot WITHOUT linked IngestionRun (legacy snapshot)
    sha_legacy = "sha_legacy_" + uuid.uuid4().hex[:16]
    snap_legacy = SnapshotModel(
        id=sha_legacy,
        ingestion_run_id=None,
        venue="BINANCE",
        symbol="BTCUSDT",
        timeframe="5m",
        start_time_ms=1000,
        end_time_ms=2000,
        candle_count=100,
        file_path="dummy.parquet",
        sha256=sha_legacy,
        created_at=now,
    )
    db_session.add(snap_legacy)
    db_session.commit()

    try:
        # Check linked quality
        res_linked = client.get(f"/snapshots/{sha_linked}/quality")
        assert res_linked.status_code == 200
        q_linked = res_linked.json()
        assert q_linked["quality_status"] == "VERIFIED_WITH_GAPS"
        assert q_linked["is_pristine"] is False
        assert q_linked["coverage_ratio"] == 0.98
        assert q_linked["missing_intervals_count"] == 2
        assert q_linked["duplicate_candles_count"] == 1
        assert q_linked["gap_list_status"] == "UNAVAILABLE_NOT_PERSISTED"

        # Check legacy quality (must not synthesize zero or pristine)
        res_legacy = client.get(f"/snapshots/{sha_legacy}/quality")
        assert res_legacy.status_code == 200
        q_legacy = res_legacy.json()
        assert q_legacy["quality_status"] == "UNAVAILABLE_NO_INGESTION_RUN"
        assert q_legacy["is_pristine"] is None
        assert q_legacy["coverage_ratio"] is None
        assert q_legacy["missing_intervals_count"] is None
        assert q_legacy["duplicate_candles_count"] is None
        assert q_legacy["gap_list_status"] == "UNAVAILABLE_NOT_PERSISTED"

        # Check non-existent snapshot
        res_404 = client.get("/snapshots/non_existent_sha/quality")
        assert res_404.status_code == 404
    finally:
        db_session.delete(snap_linked)
        db_session.delete(snap_legacy)
        db_session.delete(run)
        db_session.commit()


def test_api_snapshot_candles_extraction_and_checksum_verification(client, db_session):
    pilot_path = _resolve_pilot_path()
    real_sha = hashlib.sha256(Path(pilot_path).read_bytes()).hexdigest()

    # Valid registered snapshot: reuse existing if already present
    snap_repo = SnapshotRepository(db_session)
    existing_snap = snap_repo.get_by_sha256(real_sha)
    if existing_snap:
        snap = existing_snap
        snap_id = snap.id
        created_snap = False
    else:
        snap_id = "test_candle_snap_" + uuid.uuid4().hex[:12]
        snap = SnapshotModel(
            id=snap_id,
            venue="BINANCE",
            symbol="BTCUSDT",
            timeframe="5m",
            start_time_ms=1788894000000,
            end_time_ms=1791485999999,
            candle_count=8640,
            file_path=pilot_path,
            sha256=real_sha,
        )
        db_session.add(snap)
        created_snap = True

    # Snapshot with invalid checksum
    bad_snap_id = "bad_checksum_snap_" + uuid.uuid4().hex[:12]
    bad_snap = SnapshotModel(
        id=bad_snap_id,
        venue="BINANCE",
        symbol="BTCUSDT",
        timeframe="5m",
        start_time_ms=1788894000000,
        end_time_ms=1791485999999,
        candle_count=8640,
        file_path=pilot_path,
        sha256="ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
    )
    db_session.add(bad_snap)
    db_session.commit()

    try:
        # 1. Valid extraction with limit
        res = client.get(f"/snapshots/{snap_id}/candles?limit=10")
        assert res.status_code == 200
        candles = res.json()
        assert len(candles) == 10
        c0 = candles[0]
        assert "open_time_ms" in c0
        assert "open" in c0
        assert "high" in c0
        assert "low" in c0
        assert "close" in c0
        assert "volume" in c0

        # Limit upper bound (up to 1500 accepted, > 1500 rejected with 422)
        res_max = client.get(f"/snapshots/{snap_id}/candles?limit=1500")
        assert res_max.status_code == 200
        res_over = client.get(f"/snapshots/{snap_id}/candles?limit=1501")
        assert res_over.status_code == 422

        # 2. Bounds validation start_ms > end_ms -> 422
        res_inv = client.get(f"/snapshots/{snap_id}/candles?start_ms=2000&end_ms=1000")
        assert res_inv.status_code == 422

        # 3. Checksum mismatch -> 422
        res_mismatch = client.get(f"/snapshots/{bad_snap_id}/candles")
        assert res_mismatch.status_code == 422
        assert "checksum mismatch" in res_mismatch.json()["detail"].lower()

        # 4. Unknown snapshot -> 404
        res_404 = client.get("/snapshots/unknown_id/candles")
        assert res_404.status_code == 404
    finally:
        if created_snap:
            db_session.delete(snap)
        db_session.delete(bad_snap)
        db_session.commit()


def test_api_ingestion_runs_pagination_and_ordering(client, db_session):
    now = datetime.now(timezone.utc)
    r1_id = "run_p1_" + uuid.uuid4().hex[:8]
    r2_id = "run_p2_" + uuid.uuid4().hex[:8]
    r1 = IngestionRunModel(
        id=r1_id,
        venue="BINANCE",
        symbol="BTCUSDT",
        timeframe="5m",
        start_time_ms=1000,
        end_time_ms=2000,
        valid_candles_count=100,
        created_at=now,
    )
    r2 = IngestionRunModel(
        id=r2_id,
        venue="BINANCE",
        symbol="BTCUSDT",
        timeframe="5m",
        start_time_ms=2000,
        end_time_ms=3000,
        valid_candles_count=100,
        created_at=now,
    )
    db_session.add_all([r1, r2])
    db_session.commit()

    try:
        res = client.get("/ingestion-runs?limit=10")
        assert res.status_code == 200
        runs = res.json()
        assert len(runs) >= 2
        # Cursor test
        cursor = f"{runs[0]['created_at']}|{runs[0]['id']}"
        res_cursor = client.get(f"/ingestion-runs?limit=10&cursor={cursor}")
        assert res_cursor.status_code == 200
    finally:
        db_session.delete(r1)
        db_session.delete(r2)
        db_session.commit()


def test_api_narrative_endpoint(client):
    response = client.get("/narrative")
    assert response.status_code == 200
    data = response.json()
    assert "markdown" in data
    assert "ShootingStar" in data["markdown"]


def test_research_ui_manifesto_and_cost_gating(client):
    response = client.get("/")
    assert response.status_code == 200
    html = response.text
    assert "ShootingStar Research Platform" in html


def test_ingestion_jobs_validation(client):
    # Missing preview_token -> 422
    res_no_tok = client.post("/ingestion/jobs", json={
        "symbol": "BTCUSDT",
        "timeframe": "1m",
        "start_time_ms": 1000,
        "end_time_ms": 2000,
    })
    assert res_no_tok.status_code == 422

    # Invalid symbol
    res = client.post("/ingestion/jobs", json={
        "symbol": "ETHUSDT",
        "timeframe": "1m",
        "start_time_ms": 1000,
        "end_time_ms": 2000,
        "preview_token": "dummy_token",
    })
    assert res.status_code == 400
    assert "Only BTCUSDT" in res.json()["detail"]

    # Invalid timeframe
    res = client.post("/ingestion/jobs", json={
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "start_time_ms": 1000,
        "end_time_ms": 2000,
        "preview_token": "dummy_token",
    })
    assert res.status_code == 400

    # Inverted timestamps
    res = client.post("/ingestion/jobs", json={
        "symbol": "BTCUSDT",
        "timeframe": "1m",
        "start_time_ms": 2000,
        "end_time_ms": 1000,
        "preview_token": "dummy_token",
    })
    assert res.status_code == 400

    # Span > 65 days
    res = client.post("/ingestion/jobs", json={
        "symbol": "BTCUSDT",
        "timeframe": "1m",
        "start_time_ms": 1000,
        "end_time_ms": 1000 + (70 * 86400 * 1000),
        "preview_token": "dummy_token",
    })
    assert res.status_code == 400
    assert "Time range cannot exceed 65 days" in res.json()["detail"]

def test_ingestion_job_lifecycle(client):
    start_ms = 1704067200000  # 2024-01-01
    end_ms = 1704153600000    # 2024-01-02

    from shootingstar.api.ingestion_routes import preview_token_manager
    tok1 = preview_token_manager.register_preview("BTCUSDT", "1m", start_ms, end_ms, 100)
    tok2 = preview_token_manager.register_preview("BTCUSDT", "1m", start_ms, end_ms, 100)
    tok3 = preview_token_manager.register_preview("BTCUSDT", "1m", start_ms, end_ms, 100)

    with patch("shootingstar.api.ingestion_routes._run_ingestion_background") as mock_bg:
        res = client.post("/ingestion/jobs", json={
            "symbol": "BTCUSDT",
            "timeframe": "1m",
            "start_time_ms": start_ms,
            "end_time_ms": end_ms,
            "preview_token": tok1,
        })
        assert res.status_code == 202
        job = res.json()
        job_id = job["job_id"]
        assert job["status"] == "RUNNING"
        assert job["symbol"] == "BTCUSDT"

        # Concurrency 409 test
        res_conflict = client.post("/ingestion/jobs", json={
            "symbol": "BTCUSDT",
            "timeframe": "1m",
            "start_time_ms": start_ms,
            "end_time_ms": end_ms,
            "preview_token": tok2,
        })
        assert res_conflict.status_code == 409

        # GET by ID
        res_get = client.get(f"/ingestion/jobs/{job_id}")
        assert res_get.status_code == 200
        assert res_get.json()["job_id"] == job_id

        # List jobs
        res_list = client.get("/ingestion/jobs")
        assert res_list.status_code == 200
        assert any(j["job_id"] == job_id for j in res_list.json())

        # Simulate job completion
        from shootingstar.api.ingestion_routes import job_manager
        job_manager.update_job_success(
            job_id=job_id,
            snapshot_id="mock_snapshot_sha",
            valid_candles_count=1440,
            coverage_ratio=1.0,
            is_pristine=True,
        )

        res_completed = client.get(f"/ingestion/jobs/{job_id}")
        assert res_completed.status_code == 200
        assert res_completed.json()["status"] == "COMPLETED"
        assert res_completed.json()["snapshot_id"] == "mock_snapshot_sha"
        assert res_completed.json()["valid_candles_count"] == 1440

        # Now a new job can be submitted
        res_new = client.post("/ingestion/jobs", json={
            "symbol": "BTCUSDT",
            "timeframe": "1m",
            "start_time_ms": start_ms,
            "end_time_ms": end_ms,
            "preview_token": tok3,
        })
        assert res_new.status_code == 202
        # Cleanup
        job_manager.update_job_success(res_new.json()["job_id"], "snap2", 1440, 1.0, True)


def test_ingestion_preview_contract_and_non_persistence(client, db_session):
    from unittest.mock import patch
    from shootingstar.adapters.db.models import SnapshotModel

    snap_count_before = db_session.query(SnapshotModel).count()

    # Validation errors
    res_bad = client.post("/ingestion/preview", json={
        "symbol": "ETHUSDT",
        "timeframe": "1m",
        "start_time_ms": 1704067200000,
        "end_time_ms": 1704153600000,
    })
    assert res_bad.status_code == 400

    # Successful preview with mock klines
    mock_rows = [
        [1704067200000, "42000.0", "42100.0", "41900.0", "42050.0", "12.5", 1704067259999, "525000.0", 150, "6.0", "252000.0", "0"],
        [1704067260000, "42050.0", "42150.0", "42000.0", "42100.0", "10.0", 1704067319999, "421000.0", 120, "5.0", "210500.0", "0"],
    ]
    with patch("shootingstar.adapters.binance.BinanceSpotClient.fetch_klines_with_raw", return_value=(mock_rows, b"[]", {})):
        res = client.post("/ingestion/preview", json={
            "symbol": "BTCUSDT",
            "timeframe": "1m",
            "start_time_ms": 1704067200000,
            "end_time_ms": 1704153600000,
        })
        assert res.status_code == 200
        data = res.json()
        assert data["symbol"] == "BTCUSDT"
        assert data["timeframe"] == "1m"
        assert data["estimated_candle_count"] > 0
        assert data["sampled_candles_count"] == 2
        assert len(data["sample_candles"]) == 2
        assert data["sample_candles"][0]["open"] == 42000.0
        assert data["preview_token"] != ""
        assert data["quality_status"] == "SAMPLE_OK_FULL_RANGE_UNCHECKED"
        assert data["is_bounded"] is True
    # Assert no snapshot was persisted in DB
    snap_count_after = db_session.query(SnapshotModel).count()
    assert snap_count_after == snap_count_before


def test_preview_token_validation_and_tamper_rejection(client):
    from unittest.mock import patch
    from shootingstar.api.ingestion_routes import job_manager

    start_ms = 1704067200000
    end_ms = 1704153600000

    mock_rows = [
        [start_ms, "42000.0", "42100.0", "41900.0", "42050.0", "12.5", start_ms + 59999, "525000.0", 150, "6.0", "252000.0", "0"],
    ]

    with patch("shootingstar.adapters.binance.BinanceSpotClient.fetch_klines_with_raw", return_value=(mock_rows, b"[]", {})):
        res_prev = client.post("/ingestion/preview", json={
            "symbol": "BTCUSDT",
            "timeframe": "1m",
            "start_time_ms": start_ms,
            "end_time_ms": end_ms,
        })
        assert res_prev.status_code == 200
        token = res_prev.json()["preview_token"]

    # 1. Tampered parameters with original token -> rejected with 400
    res_tampered = client.post("/ingestion/jobs", json={
        "symbol": "BTCUSDT",
        "timeframe": "5m",
        "start_time_ms": start_ms,
        "end_time_ms": end_ms,
        "preview_token": token,
    })
    assert res_tampered.status_code == 400
    assert "Parameters were modified" in res_tampered.json()["detail"]

    # 2. Non-existent token -> rejected with 400
    res_fake = client.post("/ingestion/jobs", json={
        "symbol": "BTCUSDT",
        "timeframe": "1m",
        "start_time_ms": start_ms,
        "end_time_ms": end_ms,
        "preview_token": "non_existent_token_12345",
    })
    assert res_fake.status_code == 400
    assert "invalid or expired" in res_fake.json()["detail"]

    # 3. Matching parameters with token -> accepted (202)
    with patch("shootingstar.api.ingestion_routes._run_ingestion_background"):
        res_ok = client.post("/ingestion/jobs", json={
            "symbol": "BTCUSDT",
            "timeframe": "1m",
            "start_time_ms": start_ms,
            "end_time_ms": end_ms,
            "preview_token": token,
        })
        assert res_ok.status_code == 202
        job_manager.update_job_success(res_ok.json()["job_id"], "snap_test", 1440, 1.0, True)


def test_api_snapshot_disk_tampering_detection(client, db_session, tmp_path):
    import os
    from shootingstar.adapters.db.models import SnapshotModel
    from shootingstar.adapters.storage import SnapshotStorage
    from shootingstar.domain.models import Candle

    storage = SnapshotStorage(snapshots_dir=tmp_path)
    candle = Candle(
        venue="BINANCE",
        symbol="BTCUSDT",
        timeframe="1m",
        open_time_ms=1704067200000,
        close_time_ms=1704067259999,
        open=42000.0,
        high=42100.0,
        low=41900.0,
        close=42050.0,
        volume=10.0,
        quote_volume=420000.0,
        trades_count=100,
        taker_buy_base_volume=5.0,
        taker_buy_quote_volume=210000.0,
        observed_ingested_at_ms=1704067261000,
    )
    snap_file, orig_sha = storage.save_snapshot([candle], "BINANCE", "BTCUSDT", "1m")
    orig_stat = snap_file.stat()
    snap_id = "test_tamper_snap_" + uuid.uuid4().hex[:8]
    snap = SnapshotModel(
        id=snap_id,
        venue="BINANCE",
        symbol="BTCUSDT",
        timeframe="1m",
        start_time_ms=1704067200000,
        end_time_ms=1704067259999,
        candle_count=1,
        file_path=str(snap_file),
        sha256=orig_sha,
    )
    db_session.add(snap)
    db_session.commit()

    try:
        # First extraction: valid
        res = client.get(f"/snapshots/{snap_id}/candles")
        assert res.status_code == 200
        assert res.headers["X-Snapshot-Id"] == snap_id
        assert res.headers["X-Snapshot-Sha256"] == orig_sha

        # Now tamper with file on disk while keeping exact file size and restoring mtime
        raw_bytes = bytearray(snap_file.read_bytes())
        raw_bytes[10] = (raw_bytes[10] + 1) % 256
        snap_file.write_bytes(bytes(raw_bytes))
        os.utime(snap_file, (orig_stat.st_atime, orig_stat.st_mtime))

        # Second extraction: MUST fail with 422 Checksum mismatch
        res_tampered = client.get(f"/snapshots/{snap_id}/candles")
        assert res_tampered.status_code == 422
        assert "checksum mismatch" in res_tampered.json()["detail"].lower()
    finally:
        db_session.delete(snap)
        db_session.commit()


def test_simulation_api_endpoints_workflow(client, db_session, tmp_path):
    from shootingstar.adapters.db.models import SnapshotModel
    from shootingstar.adapters.storage import SnapshotStorage
    from shootingstar.domain.models import Candle

    # Create 50 candles
    candles = []
    base_time = 1704067200000
    for i in range(50):
        open_t = base_time + (i * 300000)
        close_t = open_t + 299999
        c_open = 42000.0
        c_close = 42050.0 + (i * 10.0)
        c_high = max(c_open, c_close) + 50.0
        c_low = min(c_open, c_close) - 50.0
        candles.append(
            Candle(
                venue="BINANCE",
                symbol="BTCUSDT",
                timeframe="5m",
                open_time_ms=open_t,
                close_time_ms=close_t,
                open=c_open,
                high=c_high,
                low=c_low,
                close=c_close,
                volume=10.0,
                quote_volume=420000.0,
                trades_count=100,
                taker_buy_base_volume=5.0,
                taker_buy_quote_volume=210000.0,
                observed_ingested_at_ms=close_t + 1000,
            )
        )
    storage = SnapshotStorage(snapshots_dir=tmp_path)
    snap_file, orig_sha = storage.save_snapshot(candles, "BINANCE", "BTCUSDT", "5m")

    snap_id = "test_sim_snap_" + uuid.uuid4().hex[:8]
    snap = SnapshotModel(
        id=snap_id,
        venue="BINANCE",
        symbol="BTCUSDT",
        timeframe="5m",
        start_time_ms=candles[0].open_time_ms,
        end_time_ms=candles[-1].close_time_ms,
        candle_count=len(candles),
        file_path=str(snap_file),
        sha256=orig_sha,
    )
    db_session.add(snap)
    db_session.commit()

    try:
        buy_t = candles[20].close_time_ms
        # 1. Create simulation job
        res_create = client.post("/replay/jobs", json={
            "snapshot_id": snap_id,
            "buy_time_ms": buy_t,
            "buy_price": 42200.0,
            "horizon_minutes": 30,
        })
        assert res_create.status_code == 201
        job_data = res_create.json()
        job_id = job_data["job_id"]
        assert job_data["status"] == "AI_PREDICTED"
        assert job_data["outcome"] is None  # Zero-lookahead: outcome must be null

        # 2. Get simulation job
        res_get = client.get(f"/replay/jobs/{job_id}")
        assert res_get.status_code == 200
        assert res_get.json()["outcome"] is None

        # 3. User Vote
        res_vote = client.post(f"/replay/jobs/{job_id}/vote", json={
            "user_direction": "UP",
        })
        assert res_vote.status_code == 200
        voted_data = res_vote.json()
        assert voted_data["status"] == "VOTED"
        assert voted_data["user_vote"]["user_direction"] == "UP"
        assert voted_data["outcome"] is None

        # 4. Reveal outcome
        res_reveal = client.post(f"/replay/jobs/{job_id}/reveal")
        assert res_reveal.status_code == 200
        revealed_data = res_reveal.json()
        assert revealed_data["status"] == "REVEALED"
        assert revealed_data["outcome"] is not None
        assert revealed_data["outcome"]["status"] == "EVALUATED"
        assert isinstance(revealed_data["outcome"]["user_is_correct"], bool)
    finally:
        db_session.delete(snap)
        db_session.commit()

def test_snapshot_path_resolution_and_candles_retrieval(client, db_session, tmp_path, monkeypatch):
    """Verifies robust snapshot path resolution across directory layouts, cwd independence, and 404 handling."""
    from shootingstar.adapters.storage import resolve_snapshot_file_path as _resolve_snapshot_file_path
    from shootingstar.adapters.db.models import SnapshotModel
    from shootingstar.adapters.storage import SnapshotStorage
    from shootingstar.domain.models import Candle

    # 1. Test helper with missing relative file
    assert _resolve_snapshot_file_path("non_existent_file.parquet") is None

    # 2. Strict absolute check: missing absolute path must return None without fallback
    missing_abs = tmp_path / "deleted_subdir" / "missing_file.parquet"
    assert _resolve_snapshot_file_path(str(missing_abs)) is None

    # 3. Test helper with existing file in tmp_path
    test_snap_file = tmp_path / "test_sample.parquet"
    test_snap_file.write_bytes(b"dummy")
    assert _resolve_snapshot_file_path(str(test_snap_file)) == test_snap_file

    # 4. CWD independence test: change working directory to tmp_path and resolve relative repo path
    monkeypatch.chdir(tmp_path)
    known_rel_path = "data/snapshots/BINANCE_BTCUSDT_5m_1788894000000_1791485999999_97f6323ad2.parquet"
    resolved_from_foreign_cwd = _resolve_snapshot_file_path(known_rel_path)
    assert resolved_from_foreign_cwd is not None
    assert resolved_from_foreign_cwd.exists()

    # 5. Test API returns 404 when file is missing from disk
    missing_snap = SnapshotModel(
        id="missing_snap_sha256_hash",
        venue="BINANCE",
        symbol="BTCUSDT",
        timeframe="5m",
        start_time_ms=1700000000000,
        end_time_ms=1700030000000,
        candle_count=100,
        file_path="non_existent_snapshot.parquet",
        sha256="missing_snap_sha256_hash",
    )
    db_session.add(missing_snap)
    db_session.commit()

    try:
        res_missing = client.get("/snapshots/missing_snap_sha256_hash/candles")
        assert res_missing.status_code == 404
        assert res_missing.json()["detail"] == "Snapshot data file not found on disk"
    finally:
        db_session.delete(missing_snap)
        db_session.commit()


def test_replay_and_analysis_reject_snapshot_with_missing_file(client, db_session):
    """A snapshot row whose parquet is gone gives a clear 404 / ValueError, never a raw FileNotFoundError."""
    import pytest
    from shootingstar.adapters.db.models import SnapshotModel
    from shootingstar.application.external_analysis.service import ExternalAnalysisService

    snap = SnapshotModel(
        id="missing_replay_snap",
        venue="BINANCE",
        symbol="BTCUSDT",
        timeframe="1m",
        start_time_ms=1700000000000,
        end_time_ms=1700030000000,
        candle_count=100,
        file_path="data/snapshots/does_not_exist.parquet",
        sha256="missing_replay_snap",
    )
    db_session.add(snap)
    db_session.commit()
    try:
        res = client.post(
            "/replay/jobs",
            json={"snapshot_id": snap.id, "buy_time_ms": 1700020000000, "buy_price": 100.0},
        )
        assert res.status_code == 404
        assert res.json()["detail"] == "Snapshot data file not found on disk"
        with pytest.raises(ValueError, match="not found on disk"):
            ExternalAnalysisService._snapshot_path(snap)
    finally:
        db_session.delete(snap)
        db_session.commit()
