"""Tests for FastAPI read endpoints, schema validation, and Research UI.

Verifies strict security invariants and Phase 1 B1 contracts:
- Sanitized /health with DB offline, never leaking DB URL or credentials.
- Strict omission of raw file_path, artifact_path, and sensitive internal details.
- Validated candle extraction with SHA-256 integrity verification.
- Snapshot quality handling for both linked ingestion runs and legacy unlinked runs.
- Multi-report experiment detail with ordered splits, calibration, and baselines.
- Pattern rules and hits (including failure hits and pending hits).
- Signals list and detail with separated decision, outcome, reviews, and audit logs.
"""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from unittest.mock import patch
import uuid

import pytest
from starlette.testclient import TestClient

from shootingstar.adapters.db.models import (
    AuditLogModel,
    ExperimentModel,
    ExperimentSplitModel,
    IngestionRunModel,
    MetricReportModel,
    ModelArtifactModel,
    PatternHitModel,
    PatternRuleModel,
    ReviewOverrideModel,
    SignalOutcomeModel,
    SignalPredictionModel,
    SnapshotModel,
)
from shootingstar.adapters.db.repository import (
    ExperimentRepository,
    MetricReportRepository,
    PatternHitRepository,
    PatternRuleRepository,
    ReviewOverrideRepository,
    SignalRepository,
    SnapshotRepository,
)
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
    pilot_path = "data/snapshots/BINANCE_BTCUSDT_5m_1788894000000_1791485999999_97f6323ad2.parquet"
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


def test_api_experiment_detail_multi_reports_and_artifacts(client, db_session):
    now = datetime.now(timezone.utc)
    exp_id = "exp_test_" + uuid.uuid4().hex[:12]

    # Snapshot placeholder
    sha = "exp_snap_" + uuid.uuid4().hex[:16]
    snap = SnapshotModel(
        id=sha,
        venue="BINANCE",
        symbol="BTCUSDT",
        timeframe="5m",
        start_time_ms=1000,
        end_time_ms=2000,
        candle_count=100,
        file_path="dummy.parquet",
        sha256=sha,
        created_at=now,
    )
    db_session.add(snap)

    exp = ExperimentModel(
        id=exp_id,
        name="Pilot Experiment",
        config_hash="cfg_hash_123",
        snapshot_id=sha,
        parameters_json=json.dumps({"horizon": 30, "model": "LogisticRegression"}),
        created_at=now,
    )
    db_session.add(exp)

    # Ordered splits
    s1 = ExperimentSplitModel(
        id=uuid.uuid4().hex,
        experiment_id=exp_id,
        split_type="TRAIN",
        start_time_ms=1000,
        end_time_ms=1500,
        sample_count=50,
        created_at=now,
    )
    s2 = ExperimentSplitModel(
        id=uuid.uuid4().hex,
        experiment_id=exp_id,
        split_type="TEST",
        start_time_ms=1501,
        end_time_ms=2000,
        sample_count=50,
        created_at=now,
    )
    db_session.add_all([s1, s2])

    # Artifacts (should NOT expose artifact_path!)
    art = ModelArtifactModel(
        id="art_" + uuid.uuid4().hex[:8],
        experiment_id=exp_id,
        model_type="LogisticRegression",
        artifact_path="C:/secret/models/model.pkl",
        artifact_hash="hash_art_456",
        metrics_json=json.dumps({"accuracy": 0.51}),
        created_at=now,
    )
    db_session.add(art)

    # Multi-reports: TRAIN baseline and TEST report with calibration
    rep_train = MetricReportModel(
        id=uuid.uuid4().hex,
        experiment_id=exp_id,
        split_type="TRAIN",
        report_type="BASELINE_MAJORITY",
        metrics_json=json.dumps({"accuracy": 0.50}),
        calibration_json=None,
        created_at=now,
    )
    rep_test = MetricReportModel(
        id=uuid.uuid4().hex,
        experiment_id=exp_id,
        split_type="TEST",
        report_type="EVALUATION_REPORT",
        metrics_json=json.dumps({
            "accuracy": 0.5105,
            "directional_accuracy": 0.5105,
            "cost_adjusted": "UNAVAILABLE_PENDING_SLIPPAGE_METHOD",
        }),
        calibration_json=json.dumps({"bins": [{"bin": 0, "sample_count": 25, "mean_predicted_prob": 0.48}]}),
        created_at=now,
    )
    db_session.add_all([rep_train, rep_test])
    db_session.commit()

    try:
        res = client.get(f"/experiments/{exp_id}")
        assert res.status_code == 200
        data = res.json()
        assert data["id"] == exp_id
        assert data["snapshot_sha256"] == sha
        assert len(data["splits"]) == 2
        assert data["splits"][0]["split_type"] == "TRAIN"
        assert data["splits"][1]["split_type"] == "TEST"

        # Check artifacts: strictly no artifact_path!
        assert len(data["artifacts"]) == 1
        assert "artifact_path" not in data["artifacts"][0]
        assert data["artifacts"][0]["artifact_hash"] == "hash_art_456"

        # Check multi-reports with calibration
        assert len(data["reports"]) == 2
        r_train = next(r for r in data["reports"] if r["split_type"] == "TRAIN")
        assert r_train["calibration"] is None
        r_test = next(r for r in data["reports"] if r["split_type"] == "TEST")
        assert r_test["calibration"] is not None
        assert "bins" in r_test["calibration"]
        assert r_test["metrics"]["directional_accuracy"] == 0.5105
        assert r_test["metrics"]["cost_adjusted"] == "UNAVAILABLE_PENDING_SLIPPAGE_METHOD"
    finally:
        db_session.delete(rep_train)
        db_session.delete(rep_test)
        db_session.delete(art)
        db_session.delete(s1)
        db_session.delete(s2)
        db_session.delete(exp)
        db_session.delete(snap)
        db_session.commit()


def test_api_pattern_rules_and_hits(client, db_session):
    now = datetime.now(timezone.utc)
    rule_id = "rule_ss_" + uuid.uuid4().hex[:8]
    rule = PatternRuleModel(
        id=rule_id,
        name="ShootingStar",
        version=1,
        description="Bearish shooting star candlestick pattern",
        definition_json=json.dumps({"wick_ratio": 2.0, "body_ratio": 0.3}),
        created_at=now,
    )
    db_session.add(rule)

    # 1. Successful / evaluated hit
    hit1 = PatternHitModel(
        id=uuid.uuid4().hex,
        rule_id=rule_id,
        detected_time_ms=10000,
        symbol="BTCUSDT",
        timeframe="5m",
        outcome_return_30m=-0.005,
        outcome_label="DOWN",
        created_at=now,
    )
    # 2. Failure hit (contrary outcome)
    hit2 = PatternHitModel(
        id=uuid.uuid4().hex,
        rule_id=rule_id,
        detected_time_ms=20000,
        symbol="BTCUSDT",
        timeframe="5m",
        outcome_return_30m=0.008,
        outcome_label="UP",  # failed pattern!
        created_at=now,
    )
    # 3. Pending hit (outcome not yet evaluated)
    hit3 = PatternHitModel(
        id=uuid.uuid4().hex,
        rule_id=rule_id,
        detected_time_ms=30000,
        symbol="BTCUSDT",
        timeframe="5m",
        outcome_return_30m=None,
        outcome_label=None,
        created_at=now,
    )
    db_session.add_all([hit1, hit2, hit3])
    db_session.commit()

    try:
        # Check rule listing
        res_rules = client.get("/pattern-rules?limit=10")
        assert res_rules.status_code == 200
        rules = res_rules.json()
        assert any(r["id"] == rule_id for r in rules)

        # Check rule hits
        res_hits = client.get(f"/pattern-rules/{rule_id}/hits?limit=10")
        assert res_hits.status_code == 200
        hits = res_hits.json()
        assert len(hits) == 3
        # Sorted by detected_time_ms desc
        assert hits[0]["detected_time_ms"] == 30000
        assert hits[0]["outcome_label"] is None  # pending
        assert hits[1]["detected_time_ms"] == 20000
        assert hits[1]["outcome_label"] == "UP"  # failure hit
        assert hits[2]["detected_time_ms"] == 10000
        assert hits[2]["outcome_label"] == "DOWN"
    finally:
        db_session.delete(hit1)
        db_session.delete(hit2)
        db_session.delete(hit3)
        db_session.delete(rule)
        db_session.commit()


def test_api_signals_list_and_detail_with_audit_and_review(client, db_session):
    now = datetime.now(timezone.utc)
    sig_id = "sig_pred_" + uuid.uuid4().hex[:12]

    # Ensure foreign key experiment exists
    snap_repo = SnapshotRepository(db_session)
    pilot_path = "data/snapshots/BINANCE_BTCUSDT_5m_1788894000000_1791485999999_97f6323ad2.parquet"
    real_sha = hashlib.sha256(Path(pilot_path).read_bytes()).hexdigest()
    existing_snap = snap_repo.get_by_sha256(real_sha)
    snap_id = existing_snap.id if existing_snap else "snap_placeholder"

    exp_id = "exp_sig_" + uuid.uuid4().hex[:12]
    exp = ExperimentModel(
        id=exp_id,
        name="Signal Experiment",
        config_hash="cfg_hash_sig_123",
        snapshot_id=snap_id,
        parameters_json="{}",
        created_at=now,
    )
    db_session.add(exp)

    # Prediction
    pred = SignalPredictionModel(
        id=sig_id,
        prediction_time_ms=50000,
        experiment_id=exp_id,
        symbol="BTCUSDT",
        timeframe="5m",
        horizon_minutes=30,
        probability_up=0.35,
        probability_down=0.65,
        probability_no_trade=0.0,
        predicted_class="DOWN",
        decision="NO_TRADE",
        decision_reason="Threshold filter below confidence band",
        created_at=now,
    )
    db_session.add(pred)

    # Maturation outcome
    outcome = SignalOutcomeModel(
        id=uuid.uuid4().hex,
        signal_id=sig_id,
        status="EVALUATED",
        evaluated_at_ms=51800,
        realized_return=-0.004,
        realized_label="DOWN",
        is_match=True,
        unscorable_reason=None,
        created_at=now,
    )
    db_session.add(outcome)

    # Review override
    review = ReviewOverrideModel(
        id=uuid.uuid4().hex,
        signal_id=sig_id,
        reviewer_id="lead_analyst",
        override_decision="NO_TRADE",
        notes="Confirmed decision aligned with volatility bounds",
        created_at=now,
    )
    db_session.add(review)

    # Audit log (filtered by entity_id)
    audit = AuditLogModel(
        entity_type="signal",
        entity_id=sig_id,
        action="MATURED",
        details_json=json.dumps({"realized_return": -0.004}),
        created_at=now,
    )
    db_session.add(audit)
    db_session.commit()

    try:
        # Check signals list
        res_list = client.get("/signals?limit=10")
        assert res_list.status_code == 200
        sigs = res_list.json()
        sig_summary = next(s for s in sigs if s["id"] == sig_id)
        assert sig_summary["status"] == "EVALUATED"
        assert sig_summary["predicted_class"] == "DOWN"
        assert sig_summary["decision"] == "NO_TRADE"
        assert sig_summary["is_match"] is True

        # Check signal detail
        res_detail = client.get(f"/signals/{sig_id}")
        assert res_detail.status_code == 200
        detail = res_detail.json()
        assert detail["prediction"]["id"] == sig_id
        assert detail["prediction"]["decision_reason"] == "Threshold filter below confidence band"
        assert detail["outcome"]["status"] == "EVALUATED"
        assert len(detail["reviews"]) == 1
        assert detail["reviews"][0]["reviewer_id"] == "lead_analyst"
        assert len(detail["audit_logs"]) == 1
        assert detail["audit_logs"][0]["action"] == "MATURED"

        # Check unknown signal -> 404
        res_404 = client.get("/signals/unknown_sig_id")
        assert res_404.status_code == 404
    finally:
        db_session.delete(audit)
        db_session.delete(review)
        db_session.delete(outcome)
        db_session.delete(pred)
        db_session.delete(exp)
        db_session.commit()


def test_api_patterns_endpoint_deterministic_and_404(client, db_session):
    # 1. Non-existent snapshot ID must return 404 Not Found
    response_404 = client.get("/patterns?snapshot_id=unknown_snap_id")
    assert response_404.status_code == 404
    assert "not found" in response_404.json()["detail"].lower()

    # 2. Register deterministic test snapshot
    snap_repo = SnapshotRepository(db_session)
    pilot_path = "data/snapshots/BINANCE_BTCUSDT_5m_1788894000000_1791485999999_97f6323ad2.parquet"
    real_sha = hashlib.sha256(Path(pilot_path).read_bytes()).hexdigest()

    snap = SnapshotModel(
        id=real_sha,
        venue="BINANCE",
        symbol="BTCUSDT",
        timeframe="5m",
        start_time_ms=1788894000000,
        end_time_ms=1791485999999,
        candle_count=8640,
        file_path=pilot_path,
        sha256=real_sha,
    )
    existing = snap_repo.get_by_sha256(real_sha)
    if not existing:
        snap_repo.save(snap)
        db_session.commit()

    # Query with explicit snapshot_id
    response = client.get(f"/patterns?snapshot_id={real_sha}")
    assert response.status_code == 200
    data = response.json()
    assert data["snapshot_sha256"] == real_sha
    assert data["candle_count"] == 8640
    assert "reports" in data
    assert data["hypothesis_track"] == "SEPARATE_HYPOTHESIS_TRACK_NOT_IN_MODEL_FEATURES"
    assert data["computation_type"] == "ON_DEMAND_SNAPSHOT_AGGREGATE"
    # Invariant: Must strictly omit raw snapshot file path
    assert "snapshot_file" not in data

    # Query default without params
    response_default = client.get("/patterns")
    assert response_default.status_code == 200
    data_def = response_default.json()
    assert len(data_def["reports"]) == 4


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
    assert "COST: UNAVAILABLE_PENDING_SLIPPAGE_METHOD" in html
    assert "Rule-Based Pattern Lab" in html
