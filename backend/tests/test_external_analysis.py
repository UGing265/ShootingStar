"""Unit and integration tests for external model analysis, causal context, key manager, and fail-closed API."""

import os
import tempfile
from pathlib import Path
from typing import List
import pytest
from fastapi.testclient import TestClient

from shootingstar.adapters.db.models import ExternalAnalysisJobModel, SnapshotModel
from shootingstar.adapters.db.repository import ExternalAnalysisJobRepository, SnapshotRepository
from shootingstar.adapters.db.session import get_db_session
from shootingstar.adapters.model_api.gemini_adapter import GeminiAuthError, GeminiModelAdapter
from shootingstar.adapters.model_api.key_manager import GeminiKeyManager, mask_secret
from shootingstar.adapters.storage import SnapshotStorage
from shootingstar.api.app import app
from shootingstar.application.external_analysis.contracts import (
    AnalysisDirection,
    AnalysisMode,
    AnalysisStatus,
    ContextVariant,
    ExternalAnalysisRequest,
)
from shootingstar.application.external_analysis.context import (
    InsufficientHistoryError,
    build_context_a,
    build_context_b,
    extract_causal_window,
)
from shootingstar.application.external_analysis.service import ExternalAnalysisService
from shootingstar.application.external_analysis.verifier import ExternalAnalysisVerifier
from shootingstar.domain.models import Candle


def create_candles(count: int, start_time_ms: int = 1700000000000, tf_ms: int = 300000) -> List[Candle]:
    """Generates continuous synthetic candles."""
    candles = []
    for i in range(count):
        o_t = start_time_ms + i * tf_ms
        c_t = o_t + tf_ms - 1
        candles.append(
            Candle(
                venue="BINANCE",
                symbol="BTCUSDT",
                timeframe="5m",
                open_time_ms=o_t,
                close_time_ms=c_t,
                open=50000.0 + (i * 10),
                high=50050.0 + (i * 10),
                low=49950.0 + (i * 10),
                close=50020.0 + (i * 10),
                volume=100.0,
                quote_volume=5000000.0,
                trades_count=1000,
                taker_buy_base_volume=50.0,
                taker_buy_quote_volume=2500000.0,
            )
        )
    return candles


# 1. Causal Window & Insufficient History Tests
def test_causal_6h_window_extraction_and_invariants():
    tf_ms = 300000  # 5m
    # 6 hours of 5m = 72 candles
    candles = create_candles(100, start_time_ms=1700000000000, tf_ms=tf_ms)
    # Target t at candle 80
    t_target = candles[80].close_time_ms + 1000  # + latency

    window = extract_causal_window(candles, t_ms=t_target, window_hours=6.0, assumed_latency_ms=1000)
    assert len(window) >= 72
    # Verify no candle closing after t
    for c in window:
        assert (c.close_time_ms + 1000) <= t_target
        assert c.close_time_ms <= t_target

    # Test insufficient history (only 10 candles = 50m < 6h)
    short_candles = create_candles(10, start_time_ms=1700000000000, tf_ms=tf_ms)
    with pytest.raises(InsufficientHistoryError, match="Insufficient history duration"):
        extract_causal_window(short_candles, t_ms=short_candles[-1].close_time_ms + 1000, window_hours=6.0)

    # Test gap detection: 45 candles (3.75h), gap of 1h, then 45 candles (3.75h)
    gapped_candles = create_candles(45, start_time_ms=1700000000000, tf_ms=tf_ms)
    gap_start = gapped_candles[-1].close_time_ms + 1 + 3600000  # 1 hour gap
    gapped_candles += create_candles(45, start_time_ms=gap_start, tf_ms=tf_ms)
    with pytest.raises(InsufficientHistoryError, match="Time-series gap detected"):
        extract_causal_window(gapped_candles, t_ms=gapped_candles[-1].close_time_ms + 1000, window_hours=6.0)

# 2. Context Serializers Tests
def test_context_serializers_a_and_b():
    candles = create_candles(75, start_time_ms=1700000000000, tf_ms=300000)
    ctx_a = build_context_a(candles, snapshot_hash="sha_test_123")
    assert ctx_a["variant"] == "A"
    assert ctx_a["snapshot_hash"] == "sha_test_123"
    assert len(ctx_a["candles"]) == 75

    ctx_b = build_context_b(candles, purchase_price_p=50500.0, snapshot_hash="sha_test_123")
    assert ctx_b["variant"] == "B"
    assert "returns" in ctx_b
    assert "ret_15m" in ctx_b["returns"]
    assert "ret_1h" in ctx_b["returns"]
    assert "price_deviation_vs_p" in ctx_b
    assert len(ctx_b["tail_candles"]) == 6


# 3. Verifier Allowlist & Sanitization Tests
def test_external_analysis_verifier_sanitization():
    valid_times = {1700000000000, 1700000300000, 1700000600000}
    approved_lessons = {"lesson_head_and_shoulders", "lesson_double_bottom"}

    raw_payload = {
        "direction": "UP",
        "rationale": "Strong support bounce",
        "evidence_candle_times": [1700000000000, 9999999999999],  # 9999... is outside 6h
        "lesson_ids": ["lesson_head_and_shoulders", "fake_unapproved_lesson"],
        "probability_up": 0.85,  # Fake uncalibrated probability
    }

    pred = ExternalAnalysisVerifier.verify(
        raw_payload=raw_payload,
        valid_candle_times=valid_times,
        approved_lesson_ids=approved_lessons,
    )

    assert pred.direction == AnalysisDirection.UP
    assert pred.evidence_candle_times == [1700000000000]  # Hallucinated timestamp stripped!
    assert pred.lesson_ids == ["lesson_head_and_shoulders"]  # Unapproved lesson stripped!
    assert pred.probability_up is None  # Probability strictly forced to None!
    assert pred.probability_down is None

    # Invalid direction fallback to ABSTAIN
    pred_bad_dir = ExternalAnalysisVerifier.verify(
        raw_payload={"direction": "MAYBE", "rationale": "Uncertain"},
        valid_candle_times=valid_times,
    )
    assert pred_bad_dir.direction == AnalysisDirection.ABSTAIN


# 4. Key Manager and Quota Invariant Tests
def test_gemini_key_manager_quota_and_masking():
    configs = [
        ("AIzaSyD1234567890ABCDEF1", "proj-alpha"),
        ("AIzaSyD1234567890ABCDEF2", "proj-alpha"),  # same project
        ("AIzaSyD1234567890ABCDEF1", "proj-alpha"),  # duplicate key
    ]
    km = GeminiKeyManager(key_configs=configs)
    assert km.total_slots == 2  # Deduplicated from 3 to 2
    assert km.active_slots == 2

    # Secret masking check
    masked = mask_secret("AIzaSyD1234567890ABCDEF1")
    assert "AIza" in masked
    assert "DEF1" in masked
    assert "1234567890" not in masked

    slot1 = km.get_next_slot()
    slot2 = km.get_next_slot()
    assert slot1.index != slot2.index  # Round-robin rotation

    # 401/403 test disables key
    km.record_401_403(slot1.index, "API_KEY_INVALID")
    assert km.active_slots == 1

    # 429 quota exhaustion test: MUST NOT rotate key
    active_slot = km.get_next_slot()
    km.record_429_quota_exhausted(active_slot.index)
    # The active slot remains active, rate limit is handled per-project with backoff
    assert active_slot.is_active is True


def test_gemini_key_manager_cooldown_and_colonless_parsing(monkeypatch):
    import time
    monkeypatch.setenv("SHOOTINGSTAR_GEMINI_KEYS", "AIzaSyKeyAAA,AIzaSyKeyBBB")
    monkeypatch.setenv("SHOOTINGSTAR_GEMINI_COOLDOWN_SECONDS", "30")

    km = GeminiKeyManager()
    assert km.total_slots == 2
    assert km._slots[0].project_id == "project-0"
    assert km._slots[1].project_id == "project-1"
    assert km.cooldown_seconds == 30.0

    # Round-robin picks slot 0, then slot 1
    s0 = km.get_next_slot()
    s1 = km.get_next_slot()
    assert s0.index == 0
    assert s1.index == 1

    # Slot 0 hits 429 -> project-0 in cooldown
    km.record_429_quota_exhausted(s0.index)
    assert s0.is_available() is False
    assert s1.is_available() is True

    # Next selection rotates only to available slot 1
    next_s = km.get_next_slot()
    assert next_s.index == 1

    # Slot 1 also hits 429 -> all slots cooling -> None
    km.record_429_quota_exhausted(s1.index)
    assert km.get_next_slot() is None

    # When cooldown expires, slots are available again
    future_time = time.time() + 35.0
    s_revived = km.get_next_slot(current_time=future_time)
    assert s_revived is not None

# 5. Service End-to-End Orchestration Tests
def test_external_analysis_service_workflow(tmp_path, migrated_test_engine):
    import time, uuid
    from sqlalchemy import delete
    storage_dir = tmp_path / "snapshots"
    storage = SnapshotStorage(storage_dir)

    unique_start = 1800000000000 + int(uuid.uuid4().int % 10000000000)
    candles = create_candles(100, start_time_ms=unique_start, tf_ms=300000)
    snap_path, snap_hash = storage.save_snapshot(candles, "BINANCE", "BTCUSDT", "5m")

    created_job_ids = []
    created_snap_id = None
    try:
        with get_db_session() as session:
            snap_repo = SnapshotRepository(session)
            snap_rec = SnapshotModel(
                id=snap_hash,
                venue="BINANCE",
                symbol="BTCUSDT",
                timeframe="5m",
                start_time_ms=candles[0].open_time_ms,
                end_time_ms=candles[-1].close_time_ms,
                candle_count=len(candles),
                file_path=str(snap_path),
                sha256=snap_hash,
            )
            snap_repo.save(snap_rec)
            session.commit()
            created_snap_id = snap_hash

            job_repo = ExternalAnalysisJobRepository(session)
            adapter = GeminiModelAdapter()
            service = ExternalAnalysisService(
                job_repository=job_repo,
                snapshot_repository=snap_repo,
                snapshot_storage=storage,
                gemini_adapter=adapter,
            )

            # Target at candle 80
            t_target = candles[80].close_time_ms + 1000
            req = ExternalAnalysisRequest(
                snapshot_id=snap_hash,
                prediction_time_t_ms=t_target,
                purchase_price_p=candles[80].close,
                horizon_minutes=30,
                context_variant=ContextVariant.A,
                mode=AnalysisMode.RETROSPECTIVE,
            )

            job_dto = service.create_analysis_job(req, mock_mode=True)
            created_job_ids.append(job_dto.id)
            assert job_dto.status in ("READY", "ABSTAIN")
            assert job_dto.ai_prediction is not None
            assert job_dto.leakage_risk_banner is True
            assert job_dto.outcome is None

            # User vote (isolated)
            voted_dto = service.record_user_vote(job_dto.id, "UP")
            assert voted_dto.user_vote == "UP"
            assert voted_dto.outcome is None

            # Reveal outcome
            revealed_dto = service.reveal_outcome(job_dto.id)
            assert revealed_dto.outcome in ("UP", "DOWN", "FLAT")
            assert revealed_dto.target_price is not None
    finally:
        with get_db_session() as s:
            if created_job_ids:
                s.execute(delete(ExternalAnalysisJobModel).where(ExternalAnalysisJobModel.id.in_(created_job_ids)))
            if created_snap_id:
                s.execute(delete(SnapshotModel).where(SnapshotModel.id == created_snap_id))
            s.commit()

# 6. Fail-Closed API Security Tests
def test_fail_closed_api_protection(monkeypatch):
    client = TestClient(app)

    # 1. Without SHOOTINGSTAR_EXTERNAL_API_ENABLED: write and read fail closed (503)
    monkeypatch.delenv("SHOOTINGSTAR_EXTERNAL_API_ENABLED", raising=False)

    res_write = client.post(
        "/external-analysis/jobs",
        json={
            "snapshot_id": "dummy_snap",
            "prediction_time_t_ms": 1700000000000,
            "purchase_price_p": 50000.0,
        },
    )
    assert res_write.status_code == 503
    assert "gated pending operator authentication" in res_write.json()["detail"]

    res_read = client.get("/external-analysis/jobs/some_job_id")
    assert res_read.status_code == 503

    # 2. Enabled but missing or invalid X-Admin-Key fails closed (403)
    monkeypatch.setenv("SHOOTINGSTAR_EXTERNAL_API_ENABLED", "true")
    monkeypatch.setenv("SHOOTINGSTAR_ADMIN_KEY", "super-secret-admin-token")

    res_unauth_write = client.post(
        "/external-analysis/jobs",
        headers={"X-Admin-Key": "wrong-key"},
        json={
            "snapshot_id": "dummy_snap",
            "prediction_time_t_ms": 1700000000000,
            "purchase_price_p": 50000.0,
        },
    )
    assert res_unauth_write.status_code == 403
    assert "Administrator authentication required" in res_unauth_write.json()["detail"]

    res_unauth_read = client.get(
        "/external-analysis/jobs/some_job_id",
        headers={"X-Admin-Key": "wrong-key"},
    )
    assert res_unauth_read.status_code == 403

    # 3. With valid X-Admin-Key: GET on non-existent job returns 404 (not 500 or 403)
    res_auth_get = client.get(
        "/external-analysis/jobs/non_existent_job_123",
        headers={"X-Admin-Key": "super-secret-admin-token"},
    )
    assert res_auth_get.status_code == 404

def test_outcome_evaluation_with_t_between_candle_boundaries(tmp_path, migrated_test_engine):
    import time, uuid
    from sqlalchemy import delete
    storage_dir = tmp_path / "snapshots"
    storage = SnapshotStorage(storage_dir)

    unique_start = 1850000000000 + int(uuid.uuid4().int % 10000000000)
    candles = create_candles(100, start_time_ms=unique_start, tf_ms=300000)
    snap_path, snap_hash = storage.save_snapshot(candles, "BINANCE", "BTCUSDT", "5m")

    created_job_ids = []
    created_snap_id = None
    try:
        with get_db_session() as session:
            snap_repo = SnapshotRepository(session)
            snap_rec = SnapshotModel(
                id=snap_hash,
                venue="BINANCE",
                symbol="BTCUSDT",
                timeframe="5m",
                start_time_ms=candles[0].open_time_ms,
                end_time_ms=candles[-1].close_time_ms,
                candle_count=len(candles),
                file_path=str(snap_path),
                sha256=snap_hash,
            )
            snap_repo.save(snap_rec)
            session.commit()
            created_snap_id = snap_hash

            job_repo = ExternalAnalysisJobRepository(session)
            adapter = GeminiModelAdapter()
            service = ExternalAnalysisService(
                job_repository=job_repo,
                snapshot_repository=snap_repo,
                snapshot_storage=storage,
                gemini_adapter=adapter,
            )

            # Target t between candle 80 boundaries
            t_between = candles[80].open_time_ms + 123456
            purchase_price_p = 50000.0
            req = ExternalAnalysisRequest(
                snapshot_id=snap_hash,
                prediction_time_t_ms=t_between,
                purchase_price_p=purchase_price_p,
                horizon_minutes=30,
                context_variant=ContextVariant.A,
                mode=AnalysisMode.RETROSPECTIVE,
            )

            job_dto = service.create_analysis_job(req, mock_mode=True)
            created_job_ids.append(job_dto.id)
            assert job_dto.outcome is None

            revealed_dto = service.reveal_outcome(job_dto.id)
            assert revealed_dto.target_price == candles[86].close
            assert revealed_dto.outcome == "UP"
    finally:
        with get_db_session() as s:
            if created_job_ids:
                s.execute(delete(ExternalAnalysisJobModel).where(ExternalAnalysisJobModel.id.in_(created_job_ids)))
            if created_snap_id:
                s.execute(delete(SnapshotModel).where(SnapshotModel.id == created_snap_id))
            s.commit()
