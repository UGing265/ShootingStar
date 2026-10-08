"""Tests for FastAPI read endpoints, schema validation, and Research UI."""

import pytest
from fastapi.testclient import TestClient

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


def test_api_patterns_endpoint(client):
    response = client.get("/patterns")
    assert response.status_code == 200
    data = response.json()
    assert "reports" in data
    assert data["hypothesis_track"] == "SEPARATE_HYPOTHESIS_TRACK_NOT_IN_MODEL_FEATURES"


def test_api_signals_endpoint(client):
    response = client.get("/signals")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


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
