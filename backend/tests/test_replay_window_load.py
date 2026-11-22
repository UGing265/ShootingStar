"""Replay uses bounded real Parquet windows while preserving snapshot semantics."""

import pytest

from shootingstar.adapters.storage import SnapshotStorage
from shootingstar.application.replay import SimulationJobManager
from shootingstar.domain.exceptions import DomainError
from tests.fakes.forecast_fixtures import make_series, unique_start_ms


class WindowStorage(SnapshotStorage):
    def __init__(self, snapshots_dir):
        super().__init__(snapshots_dir=snapshots_dir)
        self.windows = []

    def load_snapshot(self, path):
        raise AssertionError("Replay must not load a complete snapshot")

    def load_snapshot_window(self, path, start_ms=None, end_ms=None, limit=None):
        assert start_ms is not None and end_ms is not None
        candles = super().load_snapshot_window(path, start_ms, end_ms, limit)
        self.windows.append((start_ms, end_ms, len(candles)))
        return candles


def test_replay_windows_preserve_strategy_bounds_and_pending(tmp_path):
    storage = WindowStorage(tmp_path / 'snapshots')
    candles = make_series(unique_start_ms(), 2000)
    candles = candles[:850] + candles[950:]
    path, sha = storage.save_snapshot(candles, 'BINANCE', 'BTCUSDT', '1m')
    manager = SimulationJobManager(storage, tmp_path / 'simulations')
    first, last = candles[0].open_time_ms, candles[-1].close_time_ms
    c = candles[880]
    t = c.close_time_ms
    expected = manager._evaluate_strategy_candidate([x for x in candles if x.close_time_ms <= t], t, 30)
    job = manager.create_job(path, sha, t, c.close, 30, snapshot_start_ms=first,
                             snapshot_end_ms=last, snapshot_timeframe='1m')
    assert job.candle_close_at_buy == c.close
    assert job.strategy_evaluation == expected
    assert max(size for _, _, size in storage.windows) < len(candles)
    manager.record_vote(job.job_id, 'UP')
    result = manager.reveal_outcome(job.job_id, path, snapshot_end_ms=last)
    target = t + 30 * 60_000
    target_candle = next(x for x in candles if x.open_time_ms <= target <= x.close_time_ms)
    assert result.outcome.status == 'EVALUATED' and result.outcome.future_price == target_candle.close
    assert storage.windows[-1][2] < 100
    with pytest.raises(DomainError, match='outside snapshot bounds'):
        manager.create_job(path, sha, first - 1, c.close, snapshot_start_ms=first,
                           snapshot_end_ms=last, snapshot_timeframe='1m')
    with pytest.raises(DomainError, match='outside snapshot bounds'):
        manager.create_job(path, sha, last + 1, c.close, snapshot_start_ms=first,
                           snapshot_end_ms=last, snapshot_timeframe='1m')
    before_gap = candles[840]
    gap_job = manager.create_job(path, sha, before_gap.close_time_ms, before_gap.close, snapshot_start_ms=first,
                                 snapshot_end_ms=last, snapshot_timeframe='1m')
    manager.record_vote(gap_job.job_id, 'UP')
    gap_result = manager.reveal_outcome(gap_job.job_id, path, snapshot_end_ms=last)
    assert gap_result.outcome.status == 'UNSCORABLE'
    assert gap_result.outcome.unscorable_reason == 'Phát hiện khoảng trống dữ liệu (gap) tại mốc horizon.'
    near_end = candles[-10]
    pending = manager.create_job(path, sha, near_end.close_time_ms, near_end.close, snapshot_start_ms=first,
                                 snapshot_end_ms=last, snapshot_timeframe='1m')
    manager.record_vote(pending.job_id, 'UP')
    result = manager.reveal_outcome(pending.job_id, path, snapshot_end_ms=last)
    assert result.outcome.status == 'PENDING'
    assert result.outcome.unscorable_reason == 'Snapshot kết thúc trước mốc horizon kết quả.'


def test_empty_snapshot_keeps_existing_errors(tmp_path):
    import pyarrow as pa
    import pyarrow.parquet as pq

    storage = WindowStorage(tmp_path / 'snapshots')
    candles = make_series(unique_start_ms(), 100)
    path, sha = storage.save_snapshot(candles, 'BINANCE', 'BTCUSDT', '1m')
    manager = SimulationJobManager(storage, tmp_path / 'simulations')
    first, last = candles[0].open_time_ms, candles[-1].close_time_ms
    empty = tmp_path / 'empty.parquet'
    pq.write_table(pa.Table.from_pylist([], schema=SnapshotStorage.SCHEMA), empty)
    with pytest.raises(DomainError, match='Snapshot has no candles:'):
        manager.create_job(empty, sha, first, 100.0, snapshot_start_ms=first,
                           snapshot_end_ms=last, snapshot_timeframe='1m')
    job = manager.create_job(path, sha, candles[60].close_time_ms, candles[60].close,
                             snapshot_start_ms=first, snapshot_end_ms=last, snapshot_timeframe='1m')
    manager.record_vote(job.job_id, 'UP')
    with pytest.raises(DomainError, match='^Snapshot has no candles$'):
        manager.reveal_outcome(job.job_id, empty, snapshot_end_ms=last)
    with pytest.raises(DomainError, match='^Snapshot has no candles$'):
        manager.reveal_outcome(job.job_id, empty)
