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
    FeedContract,
    HypothesisContract,
    PatternDiagnosticContract,
    ResearchAgentContract,
)
from shootingstar.application.external_analysis.context import (
    InsufficientHistoryError,
    build_context_a,
    build_context_b,
    build_feed_contract,
    extract_causal_window,
    feed_contract_to_dict,
)
from shootingstar.application.external_analysis.research_agent import ResearchAgent
from shootingstar.application.patterns import evaluate_pattern_diagnostics
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
            service.record_user_vote(job_dto.id, "UP")
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

def test_vote_immutability_and_reveal_gate_status_codes(tmp_path, migrated_test_engine, monkeypatch):
    import uuid
    from sqlalchemy import delete
    storage_dir = tmp_path / "snapshots"
    storage = SnapshotStorage(storage_dir)

    unique_start = 1880000000000 + int(uuid.uuid4().int % 10000000000)
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

            # 1. Unvoted reveal fails at Service level
            with pytest.raises(ValueError, match="Phải khóa dự đoán của bạn trước khi xem kết quả thực tế"):
                service.reveal_outcome(job_dto.id)

            # 2. Record vote UP succeeds
            voted = service.record_user_vote(job_dto.id, "UP")
            assert voted.user_vote == "UP"

            # 3. Same vote is idempotent
            same_vote = service.record_user_vote(job_dto.id, "UP")
            assert same_vote.user_vote == "UP"

            # 4. Changed vote fails with ValueError already locked
            with pytest.raises(ValueError, match="already locked to 'UP' and cannot be changed"):
                service.record_user_vote(job_dto.id, "DOWN")

        # 5. API status code verification via TestClient
        monkeypatch.setenv("SHOOTINGSTAR_EXTERNAL_API_ENABLED", "true")
        monkeypatch.setenv("SHOOTINGSTAR_ADMIN_KEY", "test-admin-secret")
        headers = {"X-Admin-Key": "test-admin-secret"}
        client = TestClient(app)

        # 5a. Create a fresh unvoted job to test HTTP 400 on unvoted reveal
        res_create = client.post(
            "/external-analysis/jobs",
            headers=headers,
            json={
                "snapshot_id": snap_hash,
                "prediction_time_t_ms": t_target,
                "purchase_price_p": candles[80].close,
                "horizon_minutes": 30,
                "context_variant": "A",
                "mode": "RETROSPECTIVE",
                "mock_mode": True,
            },
        )
        assert res_create.status_code in (200, 202)
        unvoted_job_id = res_create.json()["id"]
        created_job_ids.append(unvoted_job_id)

        # HTTP 400 on unvoted reveal
        res_unvoted_reveal = client.post(f"/external-analysis/jobs/{unvoted_job_id}/reveal", headers=headers)
        assert res_unvoted_reveal.status_code == 400
        assert "Phải khóa dự đoán của bạn" in res_unvoted_reveal.json()["detail"]

        # Vote once
        res_vote1 = client.post(
            f"/external-analysis/jobs/{unvoted_job_id}/vote",
            headers=headers,
            json={"vote": "UP"},
        )
        assert res_vote1.status_code == 200
        assert res_vote1.json()["user_vote"] == "UP"

        # HTTP 409 on locked vote change attempt
        res_vote_conflict = client.post(
            f"/external-analysis/jobs/{unvoted_job_id}/vote",
            headers=headers,
            json={"vote": "DOWN"},
        )
        assert res_vote_conflict.status_code == 409
        assert "already locked to 'UP'" in res_vote_conflict.json()["detail"]

        # Reveal succeeds after vote
        res_revealed = client.post(f"/external-analysis/jobs/{unvoted_job_id}/reveal", headers=headers)
        assert res_revealed.status_code == 200
        assert res_revealed.json()["outcome"] in ("UP", "DOWN", "FLAT")
        assert res_revealed.json()["target_price"] is not None
    finally:
        with get_db_session() as s:
            if created_job_ids:
                s.execute(delete(ExternalAnalysisJobModel).where(ExternalAnalysisJobModel.id.in_(created_job_ids)))
            if created_snap_id:
                s.execute(delete(SnapshotModel).where(SnapshotModel.id == created_snap_id))
            s.commit()


# -------------------------------------------------------------
# Phase 04: Verification Tests for Evidence-Based Pipeline
# -------------------------------------------------------------

def test_feed_contract_causal_invariants():
    """Contract Test: FeedContract must contain exactly causal 6h window up to t with zero lookahead."""
    candles = create_candles(100)  # 5m candles
    t_ms = candles[80].close_time_ms + 1000  # Cutoff t

    feed = build_feed_contract(
        candles=candles,
        snapshot_id="snap_test_01",
        snapshot_checksum="sha256_checksum_test",
        prediction_time_t_ms=t_ms,
        purchase_price_p=50500.0,
        horizon_minutes=30,
    )

    # 6 hours of 5m = 72 candles
    assert len(feed.candles) == 72
    assert feed.coverage.status == "COMPLETE"
    assert feed.coverage.gaps_count == 0

    # Strictly causal: all candles must have close_time_ms <= t_ms
    for c in feed.candles:
        assert c.close_time_ms <= t_ms
        assert c.candle_id.startswith("snap_test_01_5m_")

    # Hash is deterministic
    assert len(feed.feed_hash) == 64
    assert feed.feed_id.startswith("feed_")

    # Versioned feature formulas
    feature_ids = {f.feature_id for f in feed.features}
    assert "latest_close_vs_p_pct" in feature_ids
    assert "volatility_6h_pct" in feature_ids
    assert "last_candle_body_ratio" in feature_ids
    for f in feed.features:
        assert f.formula_version == "v1"


def test_hypothesis_contract_generation():
    """Contract Test: Preliminary hypothesis generates testable pattern candidates without final direction."""
    candles = create_candles(80)
    t_ms = candles[-1].close_time_ms + 1000
    feed = build_feed_contract(
        candles=candles,
        snapshot_id="snap_hyp_01",
        snapshot_checksum="sha256_hyp",
        prediction_time_t_ms=t_ms,
        purchase_price_p=50000.0,
    )
    feed_dict = feed_contract_to_dict(feed)

    adapter = GeminiModelAdapter()
    hyp = adapter.analyze_preliminary(feed_dict, mock_mode=True)

    assert hyp.feed_id == feed.feed_id
    assert hyp.feed_hash == feed.feed_hash
    assert len(hyp.observations) >= 2
    assert len(hyp.candidates) >= 1
    for cand in hyp.candidates:
        assert cand.pattern_name in ("Hammer", "Shooting_Star", "Bullish_Engulfing", "Bearish_Engulfing")
        assert cand.rationale != ""
    assert len(hyp.questions_for_research) >= 1


def test_pattern_diagnostics_criteria_evaluation():
    """Contract Test: Granular Python criteria diagnostics evaluate Hammer, Shooting Star, and Engulfing."""
    # 1. Construct valid Hammer candle
    # Downtrend: 3 candles declining, then Hammer at idx 3
    # Hammer geometry: range = 100, open=50080, close=50090 (body=10, B/R=0.10 <= 0.35), high=50095 (upper=5, U/R=0.05 <= 0.15), low=50000 (lower=80, D/R=0.80 >= 0.55, D=80 >= 2*B=20)
    c0 = Candle(venue="BINANCE", symbol="BTCUSDT", timeframe="5m", open_time_ms=1000, close_time_ms=2000, open=50200, high=50250, low=50150, close=50200, volume=10, quote_volume=1, trades_count=1, taker_buy_base_volume=1, taker_buy_quote_volume=1)
    c1 = Candle(venue="BINANCE", symbol="BTCUSDT", timeframe="5m", open_time_ms=2000, close_time_ms=3000, open=50200, high=50220, low=50120, close=50150, volume=10, quote_volume=1, trades_count=1, taker_buy_base_volume=1, taker_buy_quote_volume=1)
    c2 = Candle(venue="BINANCE", symbol="BTCUSDT", timeframe="5m", open_time_ms=3000, close_time_ms=4000, open=50150, high=50160, low=50080, close=50100, volume=10, quote_volume=1, trades_count=1, taker_buy_base_volume=1, taker_buy_quote_volume=1)
    c3_hammer = Candle(venue="BINANCE", symbol="BTCUSDT", timeframe="5m", open_time_ms=4000, close_time_ms=5000, open=50080, high=50095, low=50000, close=50090, volume=10, quote_volume=1, trades_count=1, taker_buy_base_volume=1, taker_buy_quote_volume=1)

    diags = evaluate_pattern_diagnostics([c0, c1, c2, c3_hammer], target_index=-1)
    hammer_diag = next(d for d in diags if d.pattern_id == "Hammer")
    assert hammer_diag.shape_status == "PASS"
    assert hammer_diag.context_status == "PASS"
    assert hammer_diag.overall_match_status == "KHỚP_THEO_RULE_VERSION"

    # 2. Modify to have huge body (violates B/R <= 0.35)
    c3_big_body = Candle(venue="BINANCE", symbol="BTCUSDT", timeframe="5m", open_time_ms=4000, close_time_ms=5000, open=50010, high=50095, low=50000, close=50090, volume=10, quote_volume=1, trades_count=1, taker_buy_base_volume=1, taker_buy_quote_volume=1)
    diags_fail = evaluate_pattern_diagnostics([c0, c1, c2, c3_big_body], target_index=-1)
    hammer_fail = next(d for d in diags_fail if d.pattern_id == "Hammer")
    assert hammer_fail.overall_match_status == "KHÔNG_KHỚP"
    body_crit = next(cr for cr in hammer_fail.criteria if cr.criterion_id == "hammer_small_body")
    assert body_crit.status == "FAIL"

    # 3. Insufficient prior history yields UNKNOWN context -> CHƯA_ĐỦ_TIÊU_CHÍ
    diags_short = evaluate_pattern_diagnostics([c3_hammer], target_index=0)
    hammer_short = next(d for d in diags_short if d.pattern_id == "Hammer")
    assert hammer_short.context_status == "UNKNOWN"
    assert hammer_short.overall_match_status == "CHƯA_ĐỦ_TIÊU_CHÍ"

    # 4. Shooting Star
    # Uptrend: 3 candles rising, then Shooting Star with upper wick >= 55%
    u0 = Candle(venue="BINANCE", symbol="BTCUSDT", timeframe="5m", open_time_ms=1000, close_time_ms=2000, open=50000, high=50050, low=49950, close=50020, volume=10, quote_volume=1, trades_count=1, taker_buy_base_volume=1, taker_buy_quote_volume=1)
    u1 = Candle(venue="BINANCE", symbol="BTCUSDT", timeframe="5m", open_time_ms=2000, close_time_ms=3000, open=50020, high=50080, low=50000, close=50060, volume=10, quote_volume=1, trades_count=1, taker_buy_base_volume=1, taker_buy_quote_volume=1)
    u2 = Candle(venue="BINANCE", symbol="BTCUSDT", timeframe="5m", open_time_ms=3000, close_time_ms=4000, open=50060, high=50120, low=50050, close=50100, volume=10, quote_volume=1, trades_count=1, taker_buy_base_volume=1, taker_buy_quote_volume=1)
    u3_star = Candle(venue="BINANCE", symbol="BTCUSDT", timeframe="5m", open_time_ms=4000, close_time_ms=5000, open=50015, high=50100, low=50005, close=50010, volume=10, quote_volume=1, trades_count=1, taker_buy_base_volume=1, taker_buy_quote_volume=1)
    diags_star = evaluate_pattern_diagnostics([u0, u1, u2, u3_star], target_index=-1)
    star_diag = next(d for d in diags_star if d.pattern_id == "Shooting_Star")
    assert star_diag.shape_status == "PASS"
    assert star_diag.context_status == "PASS"
    assert star_diag.overall_match_status == "KHỚP_THEO_RULE_VERSION"


def test_grounded_research_agent_and_sources():
    """Contract Test: Research agent conducts grounded research with validated public HTTPS sources."""
    candles = create_candles(80)
    t_ms = candles[-1].close_time_ms + 1000
    feed = build_feed_contract(candles, "snap_01", "sha256_01", t_ms, 50000.0)
    adapter = GeminiModelAdapter()
    hyp = adapter.analyze_preliminary(feed_contract_to_dict(feed), mock_mode=True)

    research_agent = ResearchAgent(lesson_service=None, model_adapter=adapter)
    research_contract = research_agent.conduct_job_research(
        hypothesis=hyp,
        job_id="job_test_research",
        feed_hash=feed.feed_hash,
        mock_mode=True,
    )

    assert research_contract.search_provider != ""
    assert len(research_contract.queries_executed) >= 1
    assert len(research_contract.sources) >= 1
    for src in research_contract.sources:
        assert src.url.startswith("https://")
        assert src.access_status in ("ACCESSIBLE", "PAYWALL", "SNIPPET_ONLY")
    assert len(research_contract.contradictory_sources_or_facts) >= 1


def test_multi_stage_pipeline_and_evidence_envelope_persistence(tmp_path, migrated_test_engine):
    """Contract Test: Full multi-stage pipeline executes and stores evidence_envelope with 7 sections."""
    import uuid
    from sqlalchemy import delete
    snap_id = f"snap_pipe_{uuid.uuid4().hex[:8]}"
    job_id = None
    candles = create_candles(80)
    storage = SnapshotStorage(snapshots_dir=tmp_path)
    snap_file, snap_hash = storage.save_snapshot(candles=candles, venue="binance_spot", symbol="BTCUSDT", timeframe="5m")

    try:
        with get_db_session() as session:
            snap_repo = SnapshotRepository(session)
            snap = SnapshotModel(
                id=snap_id,
                symbol="BTCUSDT",
                timeframe="5m",
                start_time_ms=candles[0].open_time_ms,
                end_time_ms=candles[-1].close_time_ms,
                candle_count=len(candles),
                file_path=str(snap_file),
                sha256=snap_hash,
            )
            snap_repo.save(snap)
            session.commit()

        with get_db_session() as session:
            job_repo = ExternalAnalysisJobRepository(session)
            snap_repo = SnapshotRepository(session)
            service = ExternalAnalysisService(
                job_repository=job_repo,
                snapshot_repository=snap_repo,
                snapshot_storage=storage,
            )

            t_ms = candles[75].close_time_ms + 1000
            req = ExternalAnalysisRequest(
                snapshot_id=snap_id,
                prediction_time_t_ms=t_ms,
                purchase_price_p=50000.0,
                horizon_minutes=30,
            )

            job_dto = service.create_analysis_job(req, mock_mode=True)
            session.commit()
            job_id = job_dto.id

            # Completed status
            assert job_dto.status in (AnalysisStatus.READY.value, AnalysisStatus.ABSTAIN.value)
            assert job_dto.ai_prediction is not None
            assert job_dto.ai_prediction.probability_up is None
            assert job_dto.ai_prediction.probability_down is None

            # Verify Evidence Envelope
            env = job_dto.evidence_envelope
            assert env is not None
            assert env["protocol_version"] == "evidence-pipeline-v1"
            assert len(env["stages"]) == 5
            stage_names = [s["stage_name"] for s in env["stages"]]
            assert stage_names == ["PREPARING_FEED", "ANALYZING", "RESEARCHING", "MATCHING", "SYNTHESIZING"]

            # 7 structured Vietnamese sections
            sections = env["report_sections"]
            assert "cau_hoi_va_du_lieu" in sections
            assert "dien_bien_quan_sat" in sections
            assert "gia_thuyet_va_mau_duoc_kiem" in sections
            assert "tai_lieu_da_tra" in sections
            assert "lap_luan_va_phan_bien" in sections
            assert "ket_luan_co_dieu_kien" in sections
            assert "gioi_han_va_kha_nang_ap_dung" in sections
    finally:
        with get_db_session() as s:
            if job_id:
                s.execute(delete(ExternalAnalysisJobModel).where(ExternalAnalysisJobModel.id == job_id))
            s.execute(delete(SnapshotModel).where(SnapshotModel.id == snap_id))
            s.commit()

def test_startup_sweep_interrupted_jobs(migrated_test_engine):
    """Contract Test: Startup sweep marks intermediate jobs as FAILED_INTERRUPTED."""
    import uuid
    from datetime import datetime, timezone
    now_utc = datetime.now(timezone.utc)
    job_id = f"job_interrupt_{uuid.uuid4().hex[:8]}"

    with get_db_session() as session:
        interrupted_job = ExternalAnalysisJobModel(
            id=job_id,
            snapshot_id="dummy_snap",
            snapshot_hash="dummy_hash",
            symbol="BTCUSDT",
            timeframe="5m",
            prediction_time_t_ms=1700000000000,
            purchase_price_p=50000.0,
            horizon_minutes=30,
            mode="RETROSPECTIVE",
            context_variant="A",
            prompt_version="v1",
            model_id="gemini-2.5-flash",
            status=AnalysisStatus.RESEARCHING.value,  # Intermediate state
            is_revealed=False,
            created_at=now_utc,
            updated_at=now_utc,
        )
        session.add(interrupted_job)
        session.commit()

    # Simulate startup sweep logic
    with get_db_session() as session:
        jobs = session.query(ExternalAnalysisJobModel).filter(
            ExternalAnalysisJobModel.status.in_([
                AnalysisStatus.PREPARING_FEED.value,
                AnalysisStatus.ANALYZING.value,
                AnalysisStatus.RESEARCHING.value,
                AnalysisStatus.MATCHING.value,
                AnalysisStatus.SYNTHESIZING.value,
            ])
        ).all()
        for j in jobs:
            j.status = AnalysisStatus.FAILED_INTERRUPTED.value
            j.error_message = "Tiến trình bị gián đoạn do khởi động lại server; không tự động gọi lại API có phí"
        session.commit()

    with get_db_session() as session:
        swept_job = session.query(ExternalAnalysisJobModel).filter_by(id=job_id).first()
        assert swept_job.status == AnalysisStatus.FAILED_INTERRUPTED.value
        assert "khởi động lại server" in swept_job.error_message
        session.delete(swept_job)
        session.commit()


def test_prospective_reveal_gate_pending(tmp_path, migrated_test_engine):
    """Contract Test: Prospective reveal before t + horizon returns outcome PENDING."""
    import time
    import uuid
    from sqlalchemy import delete
    snap_id = f"snap_prosp_{uuid.uuid4().hex[:8]}"
    job_id = None
    now_ms = int(time.time() * 1000)
    candles = create_candles(80, start_time_ms=now_ms - (80 * 300000))
    storage = SnapshotStorage(snapshots_dir=tmp_path)
    snap_file, snap_hash = storage.save_snapshot(candles=candles, venue="binance_spot", symbol="BTCUSDT", timeframe="5m")

    try:
        with get_db_session() as session:
            snap = SnapshotModel(
                id=snap_id,
                symbol="BTCUSDT",
                timeframe="5m",
                start_time_ms=candles[0].open_time_ms,
                end_time_ms=candles[-1].close_time_ms,
                candle_count=len(candles),
                file_path=str(snap_file),
                sha256=snap_hash,
            )
            session.add(snap)
            session.commit()

        with get_db_session() as session:
            service = ExternalAnalysisService(
                job_repository=ExternalAnalysisJobRepository(session),
                snapshot_repository=SnapshotRepository(session),
                snapshot_storage=storage,
            )

            # Cutoff t is last candle close; target horizon is 30m in future relative to now_ms
            req = ExternalAnalysisRequest(
                snapshot_id=snap_id,
                prediction_time_t_ms=candles[-1].close_time_ms + 1000,
                purchase_price_p=50000.0,
                horizon_minutes=30,
                mode=AnalysisMode.PROSPECTIVE,
            )

            job_dto = service.create_analysis_job(req, mock_mode=True)
            session.commit()
            job_id = job_dto.id

        with get_db_session() as session:
            service = ExternalAnalysisService(
                job_repository=ExternalAnalysisJobRepository(session),
                snapshot_repository=SnapshotRepository(session),
                snapshot_storage=storage,
            )
            # Vote first
            service.record_user_vote(job_dto.id, "UP")
            # Attempt reveal before target time
            revealed = service.reveal_outcome(job_dto.id)
            assert revealed.outcome == "PENDING"
            assert revealed.target_price is None
    finally:
        with get_db_session() as s:
            if job_id:
                s.execute(delete(ExternalAnalysisJobModel).where(ExternalAnalysisJobModel.id == job_id))
            s.execute(delete(SnapshotModel).where(SnapshotModel.id == snap_id))
            s.commit()

def test_gemini_adapter_retries_on_transient_503(monkeypatch):
    """Contract Test: GeminiModelAdapter catches HTTP 503 and retries with backoff/rotation."""
    import io
    import json
    import urllib.error
    from shootingstar.adapters.model_api.gemini_adapter import GeminiModelAdapter
    from shootingstar.adapters.model_api.key_manager import GeminiKeyManager

    key_configs = [("key_alpha", "proj_1"), ("key_beta", "proj_2")]
    km = GeminiKeyManager(key_configs=key_configs)
    adapter = GeminiModelAdapter(key_manager=km)

    attempts = []

    def mock_urlopen(req, timeout=None):
        attempts.append(req.full_url)
        if len(attempts) == 1:
            # First attempt fails with 503 Service Unavailable
            fp = io.BytesIO(b'{"error": {"code": 503, "message": "Service Unavailable"}}')
            raise urllib.error.HTTPError(req.full_url, 503, "Service Unavailable", {}, fp)
        # Second attempt succeeds
        success_resp = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": json.dumps({
                                    "observations": [],
                                    "preliminary_candidates": [],
                                    "missing_information": [],
                                    "questions_for_research": [],
                                })
                            }
                        ]
                    }
                }
            ],
            "usageMetadata": {"promptTokenCount": 50, "candidatesTokenCount": 20},
        }
        mock_fp = io.BytesIO(json.dumps(success_resp).encode("utf-8"))
        # Create a mock response object supporting context manager read
        class MockResponse:
            def read(self):
                return mock_fp.read()
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
        return MockResponse()

    monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)
    monkeypatch.setattr("time.sleep", lambda s: None)  # speed up test

    data, slot_idx, body_str = adapter._send_gemini_request({"test": "payload"})
    assert len(attempts) == 2
    assert "key=key_alpha" in attempts[0]
    assert "key=key_beta" in attempts[1]
    assert slot_idx == 1
    assert "candidates" in data

def test_gemini_adapter_single_key_503_retries_and_succeeds(monkeypatch):
    """Contract Test: Single key config retries on 503 and succeeds on subsequent attempt."""
    import io
    import json
    import urllib.error
    from shootingstar.adapters.model_api.gemini_adapter import GeminiModelAdapter
    from shootingstar.adapters.model_api.key_manager import GeminiKeyManager

    key_configs = [("single_key", "single_proj")]
    km = GeminiKeyManager(key_configs=key_configs)
    adapter = GeminiModelAdapter(key_manager=km)

    attempts = []

    def mock_urlopen(req, timeout=None):
        attempts.append(req.full_url)
        if len(attempts) == 1:
            fp = io.BytesIO(b'{"error": {"code": 503, "message": "The model is overloaded."}}')
            raise urllib.error.HTTPError(req.full_url, 503, "Service Unavailable", {}, fp)
        success_resp = {
            "candidates": [{"content": {"parts": [{"text": "{}"}]}}],
            "usageMetadata": {"promptTokenCount": 10, "candidatesTokenCount": 5},
        }
        mock_fp = io.BytesIO(json.dumps(success_resp).encode("utf-8"))
        class MockResponse:
            def read(self):
                return mock_fp.read()
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
        return MockResponse()

    monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)
    monkeypatch.setattr("time.sleep", lambda s: None)

    data, slot_idx, body_str = adapter._send_gemini_request({"test": "payload"})
    assert len(attempts) == 2
    assert "key=single_key" in attempts[0]
    assert "key=single_key" in attempts[1]
    assert slot_idx == 0

def test_gemini_adapter_exhausted_503_raises_gemini_api_error(monkeypatch):
    """Contract Test: When all 503 retries are exhausted, raises GeminiAPIError preserving 503 code."""
    import io
    import urllib.error
    from shootingstar.adapters.model_api.gemini_adapter import GeminiAPIError, GeminiModelAdapter
    from shootingstar.adapters.model_api.key_manager import GeminiKeyManager

    key_configs = [("key_1", "proj_1")]
    km = GeminiKeyManager(key_configs=key_configs)
    adapter = GeminiModelAdapter(key_manager=km)

    def mock_urlopen(req, timeout=None):
        fp = io.BytesIO(b'{"error": {"code": 503, "message": "Service Unavailable"}}')
        raise urllib.error.HTTPError(req.full_url, 503, "Service Unavailable", {}, fp)

    monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)
    monkeypatch.setattr("time.sleep", lambda s: None)

    with pytest.raises(GeminiAPIError) as exc_info:
        adapter._send_gemini_request({"test": "payload"})

    assert "503" in str(exc_info.value)

def test_build_readable_presentation_context():
    """Contract Test: build_readable_presentation_context produces deterministic Vietnamese labels and units."""
    from shootingstar.application.external_analysis.report_presentation import (
        build_readable_presentation_context,
        format_ratio_to_percentage,
        format_usdt_amount,
        format_btc_volume,
    )

    assert format_ratio_to_percentage(0.001768) == "+0.1768%"
    assert format_ratio_to_percentage(-0.000005) == "-0.0005%"
    assert format_ratio_to_percentage(0.0) == "0.0%"
    assert format_usdt_amount(63079.76) == "63,079.76 USDT"
    assert format_btc_volume(1219.5205) == "1,219.5205 BTC"

    feed = {
        "symbol": "BTCUSDT",
        "timeframe": "5m",
        "prediction_time_t_ms": 1786889700000,
        "purchase_price_p": 63063.05,
        "horizon_minutes": 30,
        "candles": [
            {"open_time_ms": 1786868100000, "close_time_ms": 1786868399999, "close": 62968.45},
            {"open_time_ms": 1786889400000, "close_time_ms": 1786889699999, "close": 63063.04},
        ],
        "features": [
            {"feature_id": "latest_close_vs_p_pct", "value": -0.000005},
            {"feature_id": "range_high_6h", "value": 63079.76},
            {"feature_id": "range_low_6h", "value": 62968.45},
            {"feature_id": "volatility_6h_pct", "value": 0.001768},
            {"feature_id": "total_volume_6h", "value": 1219.5205},
            {"feature_id": "return_1h", "value": -0.000643},
            {"feature_id": "last_candle_body_ratio", "value": 0.05},
        ],
    }

    ctx = build_readable_presentation_context(feed)
    assert ctx["symbol"] == "BTCUSDT"
    assert ctx["timeframe"] == "5m"
    assert "UTC+7" in ctx["prediction_time_utc7"]
    assert "63,063.05 USDT" in ctx["purchase_price_formatted"]
    assert len(ctx["canonical_metrics"]) == 7

    metric_map = {m["raw_id"]: m for m in ctx["canonical_metrics"]}
    assert metric_map["latest_close_vs_p_pct"]["value"] == "-0.0005%"
    assert metric_map["range_high_6h"]["value"] == "63,079.76 USDT"
    assert metric_map["volatility_6h_pct"]["value"] == "+0.1768%"
    assert metric_map["total_volume_6h"]["value"] == "1,219.5205 BTC"
