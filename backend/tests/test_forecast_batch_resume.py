"""Resume retries a failed job without creating a duplicate READY job."""

import json
import uuid
from argparse import Namespace
from datetime import datetime, timezone

from sqlalchemy import select

from shootingstar.adapters.db.models import ExternalAnalysisJobModel, SnapshotModel
from shootingstar.adapters.model_api.prompts.forecast_6h_prompt import PROMPT_VERSION
from shootingstar.adapters.storage import SnapshotStorage
from shootingstar.application.external_analysis.service import ExternalAnalysisService
from shootingstar.cli import forecast_batch_command as batch
from tests.fakes.forecast_adapter import ForecastAdapter
from tests.fakes.forecast_fixtures import make_series, unique_start_ms


def test_resume_retries_failed_and_skips_completed(db_session, tmp_path, monkeypatch):
    snapshot_id = uuid.uuid4().hex
    job_id = str(uuid.uuid4())
    candles = make_series(unique_start_ms(), 15 * 24 * 60 + 12 * 60)
    path, checksum = SnapshotStorage(snapshots_dir=tmp_path).save_snapshot(candles, "BINANCE", "BTCUSDT", "1m")
    step = 6 * 3_600_000
    earliest = candles[0].open_time_ms + 14 * 86_400_000 + 4 * 3_600_000
    t = ((earliest + 1 + step - 1) // step) * step - 1
    snapshot = SnapshotModel(id=snapshot_id, sha256=checksum, venue="BINANCE", symbol="BTCUSDT",
        timeframe="1m", start_time_ms=candles[0].open_time_ms, end_time_ms=candles[-1].close_time_ms,
        candle_count=len(candles), file_path=str(path))
    job = ExternalAnalysisJobModel(id=job_id, snapshot_id=snapshot_id, snapshot_hash=checksum,
        symbol="BTCUSDT", timeframe="1m", prediction_time_t_ms=t, purchase_price_p=candles[(t-candles[0].open_time_ms)//60_000].close,
        horizon_minutes=360, mode="RETROSPECTIVE", context_variant="A", status="FAILED",
        prompt_version=PROMPT_VERSION, model_id="gemini-2.5-flash",
        evidence_envelope_json=json.dumps({"lookback_days": 14}))
    adapter = ForecastAdapter()
    monkeypatch.setenv("SHOOTINGSTAR_EXTERNAL_API_ENABLED", "true")
    monkeypatch.setattr(batch, "ExternalAnalysisService",
                        lambda *args: ExternalAnalysisService(*args, gemini_adapter=adapter))
    args = Namespace(snapshot=snapshot_id, horizon=360, step_hours=6, lookback_days=14,
                     limit=1, dry_run=False, start=None, end=None)
    db_session.add_all([snapshot, job])
    db_session.commit()
    try:
        assert t not in batch._done_times(db_session, snapshot_id, 360, 14)
        assert batch.run(args) == 0
        db_session.expire_all()
        jobs = db_session.scalars(select(ExternalAnalysisJobModel).where(
            ExternalAnalysisJobModel.snapshot_id == snapshot_id)).all()
        assert [(item.id, item.status) for item in jobs] == [(job_id, "READY")]
        assert adapter.calls == 1 and t in batch._done_times(db_session, snapshot_id, 360, 14)
        args.end = datetime.fromtimestamp(t / 1000, tz=timezone.utc).isoformat()
        assert batch.run(args) == 0 and adapter.calls == 1
    finally:
        db_session.rollback()
        for item in db_session.scalars(select(ExternalAnalysisJobModel).where(
                ExternalAnalysisJobModel.snapshot_id == snapshot_id)).all():
            db_session.delete(item)
        stored_snapshot = db_session.get(SnapshotModel, snapshot_id)
        if stored_snapshot is not None:
            db_session.delete(stored_snapshot)
        db_session.commit()
