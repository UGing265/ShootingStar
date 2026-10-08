"""Tests for FastAPI read endpoints, schema validation, and Research UI."""

import uuid
import pytest
from fastapi.testclient import TestClient

from shootingstar.adapters.db.models import SnapshotModel
from shootingstar.adapters.db.repository import SnapshotRepository
from shootingstar.api.app import app


@pytest.fixture
def client(migrated_test_engine):
    """Provides a TestClient with migrated test DB."""
    return TestClient(app)


def test_api_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"
    assert "PostgreSQL" in data["engine"]


def test_api_snapshots_endpoint(client):
    response = client.get("/snapshots")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_api_experiments_endpoint(client):
    response = client.get("/experiments")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_api_experiment_detail_and_404_not_found(client):
    # Non-existent experiment must return 404 Not Found
    response = client.get("/experiments/non_existent_exp_12345")
    assert response.status_code == 404
    data = response.json()
    assert "not found" in data["detail"].lower()


def test_api_patterns_endpoint_deterministic_and_404(client, db_session):
    # 1. Non-existent snapshot ID must return 404 Not Found
    response_404 = client.get("/patterns?snapshot_id=unknown_snap_id")
    assert response_404.status_code == 404
    assert "not found" in response_404.json()["detail"].lower()

    # 2. Register valid snapshot in DB pointing to real pilot parquet
    snap_repo = SnapshotRepository(db_session)
    pilot_path = "data/snapshots/BINANCE_BTCUSDT_5m_1788894000000_1791485999999_97f6323ad2.parquet"
    sha = "97f6323ad230cb233157b85e05030fec188825a07204fc108d888d37e2f5b80a"
    snap = SnapshotModel(
        id=sha,
        venue="BINANCE",
        symbol="BTCUSDT",
        timeframe="5m",
        start_time_ms=1788894000000,
        end_time_ms=1791485999999,
        candle_count=8640,
        file_path=pilot_path,
        sha256=sha,
    )
    if not snap_repo.get_by_sha256(sha):
        snap_repo.save(snap)
        db_session.commit()

    # Query with explicit snapshot_id
    response = client.get(f"/patterns?snapshot_id={sha}")
    assert response.status_code == 200
    data = response.json()
    assert data["snapshot_sha256"] == sha
    assert data["candle_count"] == 8640
    assert "reports" in data
    assert data["hypothesis_track"] == "SEPARATE_HYPOTHESIS_TRACK_NOT_IN_MODEL_FEATURES"

    # Query default without params (must resolve deterministically from DB)
    response_default = client.get("/patterns")
    assert response_default.status_code == 200
    data_def = response_default.json()
    assert data_def["snapshot_sha256"] is not None
    assert len(data_def["reports"]) == 4


def test_api_signals_endpoint(client):
    response = client.get("/signals")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_api_narrative_endpoint(client):
    response = client.get("/narrative")
    assert response.status_code == 200
    data = response.json()
    assert "markdown" in data
    assert "ShootingStar: Honest Research Narrative" in data["markdown"]
    assert "Directional Accuracy" in data["markdown"]
    assert "51.05%" in data["markdown"]


def test_research_ui_manifesto_and_cost_gating(client):
    response = client.get("/")
    assert response.status_code == 200
    html = response.text

    assert "ShootingStar Research Platform" in html
    assert "Evidence-First" in html
    # Cost-adjusted fields must be explicitly gated
    assert "UNAVAILABLE_PENDING_SLIPPAGE_METHOD" in html
    # Honest baseline comparison must be visible
    assert "Majority Baseline" in html
    assert "Brier Score" in html
    assert "Rule-Based Pattern Lab" in html
