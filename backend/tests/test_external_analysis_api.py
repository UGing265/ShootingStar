"""External-analysis API tests: admin gating, job creation, 0.5% reveal, legacy rows."""

import json
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from tests.fakes.forecast_fixtures import (
    MINUTE_MS,
    WARMUP_MINUTES,
    make_1m_candle,
    make_series,
    unique_start_ms,
)
from shootingstar.adapters.db.models import ExternalAnalysisJobModel, SnapshotModel
from shootingstar.adapters.db.session import get_db_session
from shootingstar.adapters.storage import SnapshotStorage
from shootingstar.api.app import app
from shootingstar.application.external_analysis.contracts import AnalysisStatus

ENABLED_ENV = "SHOOTINGSTAR_EXTERNAL_API_ENABLED"
ADMIN_ENV = "SHOOTINGSTAR_ADMIN_KEY"
ADMIN_KEY = "test-admin-secret"
HEADERS = {"X-Admin-Key": ADMIN_KEY}
LOOKBACK_DAYS = 7
HORIZON_MINUTES = 360


def _save_snapshot(tmp_path, candles):
    storage = SnapshotStorage(snapshots_dir=tmp_path)
    path, sha = storage.save_snapshot(candles, "BINANCE", "BTCUSDT", "1m")
    return storage, path, sha


def _insert_snapshot(session, candles, path, sha):
    session.add(SnapshotModel(
        id=sha, venue="BINANCE", symbol="BTCUSDT", timeframe="1m",
        start_time_ms=candles[0].open_time_ms, end_time_ms=candles[-1].close_time_ms,
        candle_count=len(candles), file_path=str(path), sha256=sha,
    ))
    session.flush()


def _insert_job(session, job_id, sha, t_ms, purchase_price, **overrides):
    now = datetime.now(timezone.utc)
    values = dict(
        id=job_id, snapshot_id=sha, snapshot_hash=sha, symbol="BTCUSDT", timeframe="1m",
        prediction_time_t_ms=t_ms, purchase_price_p=purchase_price, horizon_minutes=HORIZON_MINUTES,
        mode="RETROSPECTIVE", context_variant="A", prompt_version="forecast-6h-v1",
        model_id="gemini-2.5-flash", status=AnalysisStatus.READY.value,
        direction="UP", rationale="test", user_vote="UP", is_revealed=False,
        created_at=now, updated_at=now,
    )
    values.update(overrides)
    session.add(ExternalAnalysisJobModel(**values))
    session.flush()


def _drop_rows(job_ids, snap_ids):
    with get_db_session() as session:
        if job_ids:
            session.execute(delete(ExternalAnalysisJobModel).where(ExternalAnalysisJobModel.id.in_(job_ids)))
        for snap_id in snap_ids:
            session.execute(delete(SnapshotModel).where(SnapshotModel.id == snap_id))
        session.commit()


def test_admin_gate_blocks_without_config_or_key(monkeypatch):
    client = TestClient(app)
    body = {"snapshot_id": "dummy", "prediction_time_t_ms": 0, "purchase_price_p": 100.0}

    monkeypatch.delenv(ENABLED_ENV, raising=False)
    assert client.post("/external-analysis/jobs", json=body).status_code == 503

    monkeypatch.setenv(ENABLED_ENV, "true")
    monkeypatch.setenv(ADMIN_ENV, ADMIN_KEY)
    assert client.get("/external-analysis/jobs/anything").status_code == 403
    assert client.get("/external-analysis/jobs/anything", headers={"X-Admin-Key": "wrong"}).status_code == 403
    assert client.get("/external-analysis/jobs/non_existent_job", headers=HEADERS).status_code == 404


def test_api_creates_and_gets_new_forecast_job(tmp_path, migrated_test_engine, monkeypatch):
    candles = make_series(unique_start_ms(), WARMUP_MINUTES)
    t_ms = candles[-1].close_time_ms
    _, path, sha = _save_snapshot(tmp_path, candles)
    job_ids, snap_ids = [], []
    monkeypatch.setenv(ENABLED_ENV, "true")
    monkeypatch.setenv(ADMIN_ENV, ADMIN_KEY)
    monkeypatch.setattr("shootingstar.api.external_routes._execute_job_in_background", lambda *a, **k: None)
    client = TestClient(app)
    try:
        with get_db_session() as session:
            _insert_snapshot(session, candles, path, sha)
            session.commit()

        created = client.post("/external-analysis/jobs", headers=HEADERS, json={
            "snapshot_id": sha,
            "prediction_time_t_ms": t_ms,
            "purchase_price_p": candles[-1].close,
            "horizon_minutes": HORIZON_MINUTES,
            "lookback_days": LOOKBACK_DAYS,
        })
        assert created.status_code == 202
        body = created.json()
        job_ids.append(body["id"])
        snap_ids.append(sha)
        assert body["status"] == AnalysisStatus.PREPARING_FEED.value
        assert body["horizon_minutes"] == HORIZON_MINUTES

        fetched = client.get(f"/external-analysis/jobs/{body['id']}", headers=HEADERS)
        assert fetched.status_code == 200
        assert fetched.json()["id"] == body["id"]
        assert fetched.json()["outcome"] is None
    finally:
        _drop_rows(job_ids, snap_ids)


@pytest.mark.parametrize("target_close, expected", [(100.7, "UP"), (100.3, "FLAT")])
def test_reveal_uses_half_percent_flat_threshold(
    tmp_path, migrated_test_engine, monkeypatch, target_close, expected
):
    start = unique_start_ms()
    t_ms = start + MINUTE_MS - 1
    target_ms = t_ms + HORIZON_MINUTES * MINUTE_MS
    candles = [make_1m_candle(start, 100.0), make_1m_candle(target_ms, target_close)]
    _, path, sha = _save_snapshot(tmp_path, candles)
    job_id = f"job_reveal_{uuid.uuid4().hex[:8]}"
    monkeypatch.setenv(ENABLED_ENV, "true")
    monkeypatch.setenv(ADMIN_ENV, ADMIN_KEY)
    client = TestClient(app)
    try:
        with get_db_session() as session:
            _insert_snapshot(session, candles, path, sha)
            _insert_job(session, job_id, sha, t_ms, 100.0)
            session.commit()

        revealed = client.post(f"/external-analysis/jobs/{job_id}/reveal", headers=HEADERS)
        assert revealed.status_code == 200
        assert revealed.json()["outcome"] == expected
        assert revealed.json()["target_price"] == pytest.approx(target_close)
    finally:
        _drop_rows([job_id], [sha])


def test_legacy_abstain_job_still_serializes_via_api(migrated_test_engine, monkeypatch):
    job_id = f"job_legacy_{uuid.uuid4().hex[:8]}"
    envelope = {
        "protocol_version": "evidence-pipeline-v1",
        "stages": [{"stage_name": "PREPARING_FEED", "status": "COMPLETED"}],
        "hypothesis": {"candidates": []},
    }
    now = datetime.now(timezone.utc)
    monkeypatch.setenv(ENABLED_ENV, "true")
    monkeypatch.setenv(ADMIN_ENV, ADMIN_KEY)
    client = TestClient(app)
    try:
        with get_db_session() as session:
            session.add(ExternalAnalysisJobModel(
                id=job_id, snapshot_id="legacy_snapshot", snapshot_hash="legacy_hash",
                symbol="BTCUSDT", timeframe="5m", prediction_time_t_ms=1_700_000_000_000,
                purchase_price_p=50_000.0, horizon_minutes=30,
                mode="RETROSPECTIVE", context_variant="A", prompt_version="v1",
                model_id="gemini-2.5-flash", status=AnalysisStatus.READY.value,
                direction="ABSTAIN", rationale="legacy", evidence_times_json="[]",
                evidence_envelope_json=json.dumps(envelope),
                is_revealed=False, created_at=now, updated_at=now,
            ))
            session.commit()

        fetched = client.get(f"/external-analysis/jobs/{job_id}", headers=HEADERS)
        assert fetched.status_code == 200
        body = fetched.json()
        assert body["ai_prediction"]["direction"] == "ABSTAIN"
        assert body["evidence_envelope"]["protocol_version"] == "evidence-pipeline-v1"
        assert body["evidence_envelope"]["stages"][0]["stage_name"] == "PREPARING_FEED"
        assert body["stages"][0]["stage_name"] == "PREPARING_FEED"
        assert body["outcome"] is None
    finally:
        _drop_rows([job_id], [])
