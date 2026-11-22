"""Forecast pipeline and job-lifecycle tests: one model call, strict validation, no network."""

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import delete

from tests.fakes.forecast_adapter import ForecastAdapter
from tests.fakes.forecast_fixtures import WARMUP_MINUTES, make_series, unique_start_ms
from shootingstar.adapters.db.models import ExternalAnalysisJobModel, SnapshotModel
from shootingstar.adapters.db.repository import ExternalAnalysisJobRepository, SnapshotRepository
from shootingstar.adapters.db.session import get_db_session
from shootingstar.adapters.model_api.gemini_transport import GeminiAPIError
from shootingstar.adapters.storage import SnapshotStorage
from shootingstar.application.external_analysis.contracts import (
    AnalysisStatus,
    ExternalAnalysisRequest,
)
from shootingstar.application.external_analysis.forecast_pipeline import run_forecast_pipeline
from shootingstar.application.external_analysis.service import ExternalAnalysisService
from shootingstar.application.external_analysis.stages.analyst_stage import analyze
from shootingstar.application.external_analysis.stages.verify_stage import verify

LOOKBACK_DAYS = 7
HORIZON_MINUTES = 360


def _pipeline_inputs():
    candles = make_series(unique_start_ms(), WARMUP_MINUTES)
    return candles, candles[-1].close_time_ms


def test_pipeline_makes_one_model_call_and_builds_versioned_envelope():
    candles, t_ms = _pipeline_inputs()
    adapter = ForecastAdapter()

    envelope = run_forecast_pipeline(
        candles, t_ms, HORIZON_MINUTES, candles[-1].close, LOOKBACK_DAYS, adapter
    )

    assert adapter.calls == 1
    assert envelope["protocol_version"] == "forecast-6h-v1"
    assert envelope["horizon_minutes"] == HORIZON_MINUTES
    assert envelope["lookback_days"] == LOOKBACK_DAYS
    assert envelope["flat_threshold_pct"] == 0.5
    assert envelope["answer"]["direction"] == "UP"
    assert envelope["verification"] == {"valid": True, "issues": []}
    assert set(envelope["agreement_score"]) == {"up", "down", "total"}
    assert envelope["agreement_score"]["total"] > 0
    assert envelope["baselines"]["always_up"] == "UP"
    assert envelope["baselines"]["momentum_6h"] == "UP"
    assert envelope["possible_memorization"] is False
    assert len(envelope["digest"]["digest_hash"]) == 64
    assert envelope["token_usage"]["prompt_tokens"] == 0


BAD_ANSWERS = [
    {"direction": "ABSTAIN", "confidence": "LOW", "reasons": [{"feature_ids": ["1h_rsi14"], "text": "x"}], "risks": []},
    {"direction": "UP", "confidence": "SURE", "reasons": [{"feature_ids": ["1h_rsi14"], "text": "x"}], "risks": []},
    {"direction": "UP", "confidence": "LOW", "reasons": [], "risks": []},
    {"direction": "UP", "confidence": "LOW", "risks": []},
]


@pytest.mark.parametrize("answer", BAD_ANSWERS)
def test_invalid_answer_raises_without_fabricating_forecast(answer):
    digest = {
        "features": [
            {"feature_id": "1h_rsi14", "timeframe": "1h", "name": "rsi14", "value": 50.0, "unit": "index"}
        ],
        "digest_hash": "x",
    }
    adapter = ForecastAdapter(answer=answer)

    with pytest.raises(GeminiAPIError):
        analyze(adapter, digest, HORIZON_MINUTES, 100.0)

    assert adapter.calls == 1


VERIFY_DIGEST = {
    "features": [
        {"feature_id": "1h_ema20_slope", "timeframe": "1h", "name": "ema20_slope", "value": 1.23, "unit": "%"},
        {"feature_id": "1h_rsi14", "timeframe": "1h", "name": "rsi14", "value": 50.0, "unit": "index"},
    ],
    "digest_hash": "x",
}


def test_verify_flags_unknown_feature_id():
    answer = {"reasons": [{"feature_ids": ["1h_missing"], "text": "Tín hiệu mơ hồ."}], "risks": []}

    result = verify(answer, VERIFY_DIGEST)

    assert result["valid"] is False
    assert {"reason_index": 0, "type": "unknown_feature_id", "value": "1h_missing"} in result["issues"]


def test_verify_flags_fabricated_decimal():
    answer = {"reasons": [{"feature_ids": ["1h_ema20_slope"], "text": "EMA tăng 9.99%."}], "risks": []}

    result = verify(answer, VERIFY_DIGEST)

    assert {"reason_index": 0, "type": "unmatched_number", "value": "9.99"} in result["issues"]


def test_verify_ignores_timeframe_and_indicator_period_words():
    # "1 giờ", "RSI 14", "7 ngày" are units/periods, not claims to verify.
    text = "EMA tăng 1.23% trong 1 giờ, RSI 14 giữ trên 50, xét 7 ngày."
    answer = {"reasons": [{"feature_ids": ["1h_ema20_slope", "1h_rsi14"], "text": text}], "risks": []}

    result = verify(answer, VERIFY_DIGEST)

    assert result == {"valid": True, "issues": []}


def test_key_manager_dedup_rotation_and_masking():
    from shootingstar.adapters.model_api.key_manager import GeminiKeyManager, mask_secret

    manager = GeminiKeyManager(
        key_configs=[("key_A", "proj"), ("key_B", "proj"), ("key_A", "proj")],
        cooldown_seconds=30,
    )

    assert manager.total_slots == 2
    first = manager.get_next_slot(current_time=0)
    second = manager.get_next_slot(current_time=0)
    assert first.index != second.index
    assert mask_secret("key_A") == "****"

    manager.record_429_quota_exhausted(first.index, cooldown_seconds=30)
    assert manager.get_next_slot(current_time=0) is None


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


def _service(session, storage, adapter):
    return ExternalAnalysisService(
        ExternalAnalysisJobRepository(session), SnapshotRepository(session), storage, gemini_adapter=adapter
    )


def _drop_rows(job_ids, snap_ids):
    with get_db_session() as session:
        if job_ids:
            session.execute(delete(ExternalAnalysisJobModel).where(ExternalAnalysisJobModel.id.in_(job_ids)))
        for snap_id in snap_ids:
            session.execute(delete(SnapshotModel).where(SnapshotModel.id == snap_id))
        session.commit()


def test_service_ready_job_persists_envelope_with_one_call(tmp_path, migrated_test_engine):
    candles = make_series(unique_start_ms(), WARMUP_MINUTES)
    t_ms = candles[-1].close_time_ms
    storage, path, sha = _save_snapshot(tmp_path, candles)
    adapter = ForecastAdapter()
    job_ids, snap_ids = [], []
    try:
        with get_db_session() as session:
            _insert_snapshot(session, candles, path, sha)
            request = ExternalAnalysisRequest(
                snapshot_id=sha, prediction_time_t_ms=t_ms, purchase_price_p=candles[-1].close,
                horizon_minutes=HORIZON_MINUTES, lookback_days=LOOKBACK_DAYS,
            )
            dto = _service(session, storage, adapter).create_analysis_job(request)
            job_ids.append(dto.id)
            snap_ids.append(sha)

            assert adapter.calls == 1
            assert dto.status == AnalysisStatus.READY.value
            assert dto.ai_prediction.direction.value == "UP"
            assert dto.outcome is None
            assert dto.leakage_risk_banner is True

            envelope = dto.evidence_envelope
            assert envelope["protocol_version"] == "forecast-6h-v1"
            assert envelope["horizon_minutes"] == HORIZON_MINUTES
            assert envelope["lookback_days"] == LOOKBACK_DAYS
            assert envelope["flat_threshold_pct"] == 0.5
            assert envelope["possible_memorization"] is False
            for key in ("digest", "answer", "verification", "agreement_score", "baselines", "token_usage"):
                assert key in envelope
    finally:
        _drop_rows(job_ids, snap_ids)


def test_service_marks_invalid_answer_failed_without_fabricated_forecast(tmp_path, migrated_test_engine):
    candles = make_series(unique_start_ms(), WARMUP_MINUTES)
    t_ms = candles[-1].close_time_ms
    storage, path, sha = _save_snapshot(tmp_path, candles)
    adapter = ForecastAdapter(answer={"direction": "UP", "confidence": "LOW", "reasons": [], "risks": []})
    job_ids, snap_ids = [], []
    try:
        with get_db_session() as session:
            _insert_snapshot(session, candles, path, sha)
            request = ExternalAnalysisRequest(
                snapshot_id=sha, prediction_time_t_ms=t_ms, purchase_price_p=candles[-1].close,
                horizon_minutes=HORIZON_MINUTES, lookback_days=LOOKBACK_DAYS,
            )
            dto = _service(session, storage, adapter).create_analysis_job(request)
            job_ids.append(dto.id)
            snap_ids.append(sha)

            assert dto.status == AnalysisStatus.FAILED.value
            assert "Forecast failed" in dto.error_message
            assert dto.ai_prediction is None
            assert "answer" not in (dto.evidence_envelope or {})
            assert adapter.calls == 1
    finally:
        _drop_rows(job_ids, snap_ids)


def test_service_marks_insufficient_history_without_calling_model(tmp_path, migrated_test_engine):
    candles = make_series(unique_start_ms(), 100)
    t_ms = candles[-1].close_time_ms
    storage, path, sha = _save_snapshot(tmp_path, candles)
    adapter = ForecastAdapter()
    job_ids, snap_ids = [], []
    try:
        with get_db_session() as session:
            _insert_snapshot(session, candles, path, sha)
            request = ExternalAnalysisRequest(
                snapshot_id=sha, prediction_time_t_ms=t_ms, purchase_price_p=candles[-1].close,
                horizon_minutes=HORIZON_MINUTES, lookback_days=LOOKBACK_DAYS,
            )
            dto = _service(session, storage, adapter).create_analysis_job(request)
            job_ids.append(dto.id)
            snap_ids.append(sha)

            assert dto.status == AnalysisStatus.INSUFFICIENT_HISTORY.value
            assert dto.ai_prediction is None
            assert adapter.calls == 0
    finally:
        _drop_rows(job_ids, snap_ids)


def test_create_analysis_job_rejects_mock_mode():
    service = ExternalAnalysisService(None, None, None, gemini_adapter=ForecastAdapter())
    request = ExternalAnalysisRequest(snapshot_id="x", prediction_time_t_ms=0, purchase_price_p=100.0)

    with pytest.raises(ValueError, match="Production mock forecasts are disabled"):
        service.create_analysis_job(request, mock_mode=True)


def test_run_pipeline_marks_mock_job_failed(tmp_path, migrated_test_engine):
    now = datetime.now(timezone.utc)
    job_id = f"job_mock_{uuid.uuid4().hex[:8]}"
    try:
        with get_db_session() as session:
            session.add(ExternalAnalysisJobModel(
                id=job_id, snapshot_id="dummy_snapshot", snapshot_hash="dummy_hash",
                symbol="BTCUSDT", timeframe="1m", prediction_time_t_ms=0,
                purchase_price_p=100.0, horizon_minutes=HORIZON_MINUTES,
                mode="RETROSPECTIVE", context_variant="A", prompt_version="forecast-6h-v1",
                model_id="gemini-2.5-flash", status=AnalysisStatus.PREPARING_FEED.value,
                is_revealed=False, created_at=now, updated_at=now,
            ))
            session.flush()
            service = ExternalAnalysisService(
                ExternalAnalysisJobRepository(session), SnapshotRepository(session),
                SnapshotStorage(snapshots_dir=tmp_path), gemini_adapter=ForecastAdapter(),
            )
            dto = service.run_pipeline(job_id, mock_mode=True)

            assert dto.status == AnalysisStatus.FAILED.value
            assert dto.error_message == "Production mock forecasts are disabled"
    finally:
        _drop_rows([job_id], [])
