"""Unit tests for Phase 02: Multi-Window Rolling Evaluation and Candidate Studies."""

import tempfile
from pathlib import Path
import numpy as np
import pytest
import json

from shootingstar.application.training.splits import RollingWindowSplitter
from shootingstar.application.training.experiment import MultiWindowStudyRunner
from shootingstar.domain.models import Candle
from shootingstar.adapters.storage import SnapshotStorage


def test_rolling_window_splitter_purging_and_eligibility():
    # 60 days of 1-minute timestamps (86400 candles)
    day_ms = 86400 * 1000
    start_ms = 1704067200000  # 2024-01-01 00:00:00
    timestamps = [start_ms + i * 60000 for i in range(60 * 1440)]

    splitter = RollingWindowSplitter(
        candidate_window_days=[7, 14, 30, 90],
        test_period_days=7,
        calib_days=3,
        val_days=4,
        timeframe="1m",
        horizon_minutes=30,
    )

    periods = splitter.generate_periods(timestamps, num_periods=1)
    assert len(periods) == 1
    period = periods[0]

    # Verify identical test window across all candidates
    for cand in period.candidate_splits:
        assert cand.test.start_time_ms == period.test_start_ms
        assert cand.test.end_time_ms == period.test_end_ms

    # Candidate 7d, 14d, 30d should be eligible within 60d data
    cands_by_name = {c.window_name: c for c in period.candidate_splits}
    assert cands_by_name["7d"].is_eligible is True
    assert cands_by_name["14d"].is_eligible is True
    assert cands_by_name["30d"].is_eligible is True

    # Candidate 90d MUST be ineligible due to only 60d available data
    assert cands_by_name["90d"].is_eligible is False
    assert "available before cutoff" in cands_by_name["90d"].ineligibility_reason

    # Invariant: Strict Purge Gap
    # train -> calib -> val -> test
    cand_30d = cands_by_name["30d"]
    assert cand_30d.train is not None
    assert cand_30d.calibration is not None
    assert cand_30d.validation is not None

    gap_ms = splitter.purge_gap_samples * 60000
    assert cand_30d.train.end_time_ms + gap_ms <= cand_30d.calibration.start_time_ms
    assert cand_30d.calibration.end_time_ms + gap_ms <= cand_30d.validation.start_time_ms
    assert cand_30d.validation.end_time_ms + gap_ms <= cand_30d.test.start_time_ms


def test_multi_window_study_runner_execution():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        storage = SnapshotStorage(snapshots_dir=tmp_path / "snapshots")
        models_dir = tmp_path / "models"
        reports_dir = tmp_path / "reports"

        # Generate 45 days of 5-minute candles (45 * 288 = 12960 candles)
        candles = []
        base_time = 1704067200000
        price = 42000.0
        for i in range(45 * 288):
            open_t = base_time + (i * 300000)
            close_t = open_t + 299999
            ret = (np.sin(i / 50.0) * 0.002) + 0.0001
            c_open = price
            c_close = price * (1.0 + ret)
            c_high = max(c_open, c_close) * 1.001
            c_low = min(c_open, c_close) * 0.999
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
                    quote_volume=10.0 * c_close,
                    trades_count=100,
                    taker_buy_base_volume=5.0,
                    taker_buy_quote_volume=5.0 * c_close,
                )
            )
            price = c_close

        snap_path, _ = storage.save_snapshot(candles, venue="BINANCE", symbol="BTCUSDT", timeframe="5m")

        runner = MultiWindowStudyRunner(
            snapshot_storage=storage,
            models_dir=models_dir,
            reports_dir=reports_dir,
        )

        study_report = runner.run_study(
            snapshot_path=snap_path,
            study_id="study_test_45d",
            candidate_window_days=[7, 14, 60],
            test_period_days=5,
        )

        assert study_report.study_id == "study_test_45d"
        assert len(study_report.results) == 3

        res_by_name = {r.window_name: r for r in study_report.results}

        # 7d and 14d should be eligible with validation accuracy measured
        assert res_by_name["7d"].is_eligible is True
        assert res_by_name["7d"].validation_accuracy is not None
        assert res_by_name["14d"].is_eligible is True
        assert res_by_name["14d"].validation_accuracy is not None

        # Exactly ONE candidate is chosen as the winner on validation performance
        winner_count = sum(1 for r in study_report.results if r.is_selected_winner)
        assert winner_count == 1

        # Only the winner has test evaluation metrics (directional_accuracy, brier_score)
        winner_res = next(r for r in study_report.results if r.is_selected_winner)
        assert winner_res.directional_accuracy is not None
        assert winner_res.brier_score is not None
        assert winner_res.artifact_hash is not None
        assert winner_res.train_end_ms is not None

        # Non-winner eligible candidate remains validation-only (no test metrics)
        non_winner_res = next(r for r in study_report.results if r.is_eligible and not r.is_selected_winner)
        assert non_winner_res.directional_accuracy is None
        assert non_winner_res.brier_score is None

        # 60d exceeds 45d data, marked ineligible
        assert res_by_name["60d"].is_eligible is False
        assert res_by_name["60d"].ineligibility_reason is not None

        # Manifest with train cutoff was created on disk
        manifest_file = models_dir / f"{winner_res.artifact_hash}.manifest.json"
        assert manifest_file.exists()
        manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))
        assert manifest_data["artifact_hash"] == winner_res.artifact_hash
        assert manifest_data["train_end_ms"] == winner_res.train_end_ms
        assert manifest_data["is_selected_winner"] is True
        # Report JSON was written
        rep_file = reports_dir / "study_test_45d_study.json"
        assert rep_file.exists()
