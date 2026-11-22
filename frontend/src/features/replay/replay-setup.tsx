'use client';

import React, { useId } from 'react';
import { Notice, Spinner } from '@/shared/ui/primitives';
import { formatDateTime, formatInt } from '@/shared/format';
import type { SnapshotSummary } from '../data/types';
import { ReplayChart } from './replay-chart';
import { FORECAST_LOOKBACK_DAYS, fromDateTimeLocal, toDateTimeLocal } from './replay-utils';
import type { ReplaySession } from './use-replay-session';

export function ReplaySetup({ session, snapshots }: { session: ReplaySession; snapshots: SnapshotSummary[] }) {
  const id = useId();
  const {
    snapshotId, setSnapshotId, candles, loadingCandles, engine, setEngine,
    buyTimeMs, buyPriceInput, setBuyPriceInput, hoursBefore, hasEnoughHistory, busy, pickCandle, runAnalysis,
    timeRange, timeError, selectTime,
  } = session;

  const price = parseFloat(buyPriceInput);
  const timeframe = snapshots.find((s) => s.id === snapshotId)?.timeframe ?? '1m';
  const gemini = engine === 'gemini';
  const blocked = loadingCandles || candles.length === 0 || !buyTimeMs || !(price > 0) || (gemini && !hasEnoughHistory);

  return (
    <div className="stack">
      <div className="card replay-setup">
        <div className="grid-4">
          <div className="field">
            <label className="label" htmlFor={`${id}-snapshot`}>Bộ dữ liệu</label>
            <select id={`${id}-snapshot`} className="select" data-testid="replay-snapshot-select" value={snapshotId} onChange={(e) => setSnapshotId(e.target.value)}>
              {snapshots.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.symbol} · {s.timeframe} · {formatInt(s.candle_count)} nến · {formatDateTime(s.start_time_ms)} → {formatDateTime(s.end_time_ms)} · #{s.id.slice(0, 8)}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label className="label" htmlFor={`${id}-time`}>Thời điểm dự báo (UTC+7)</label>
            <input
              id={`${id}-time`}
              type="datetime-local"
              className="input"
              data-testid="replay-time-input"
              value={toDateTimeLocal(buyTimeMs)}
              min={timeRange ? toDateTimeLocal(timeRange.min) : undefined}
              max={timeRange ? toDateTimeLocal(timeRange.max) : undefined}
              onChange={(e) => selectTime(fromDateTimeLocal(e.target.value))}
            />
            {timeError && <p className="hint" role="alert" data-testid="replay-time-error">{timeError}</p>}
          </div>
          <div className="field">
            <label className="label" htmlFor={`${id}-price`}>Giá tại thời điểm (USDT)</label>
            <input
              id={`${id}-price`}
              type="number"
              inputMode="decimal"
              step="0.01"
              min="0"
              className="input"
              data-testid="replay-price-input"
              value={buyPriceInput}
              onChange={(e) => setBuyPriceInput(e.target.value)}
            />
          </div>
          <div className="field">
            <span className="label" id={`${id}-engine`}>Kiểu phân tích</span>
            <div className="seg" role="group" aria-labelledby={`${id}-engine`}>
              <button type="button" className="seg-btn" data-testid="replay-engine-strategy" aria-pressed={engine === 'strategy'} onClick={() => setEngine('strategy')}>
                Vùng vào lệnh (chiến thuật)
              </button>
              <button type="button" className="seg-btn" data-testid="replay-engine-gemini" aria-pressed={gemini} onClick={() => setEngine('gemini')}>
                Báo cáo Gemini (AI)
              </button>
            </div>
          </div>
        </div>

        <ul className="replay-engine-hints">
          <li>
            <strong>Vùng vào lệnh (chiến thuật):</strong> cho ra vùng vào lệnh, mức chốt lời và cắt lỗ trong 30 phút tới.
          </li>
          <li>
            <strong>Báo cáo Gemini (AI):</strong> cho ra nhận định hướng giá 6 giờ tới, kèm lập luận, chỉ số viện dẫn và so sánh với hai luật đơn giản.
          </li>
        </ul>
      </div>

      {gemini && buyTimeMs > 0 && !hasEnoughHistory && (
        <Notice variant="warning" title="Chưa đủ lịch sử.">
          Báo cáo Gemini cần ít nhất {FORECAST_LOOKBACK_DAYS} ngày nến liên tục trước thời điểm dự báo; hiện có {hoursBefore.toFixed(1)} giờ.
        </Notice>
      )}

      <div className="stack-sm">
        <div className="spread">
          <h2 className="section-title">Chọn thời điểm trên biểu đồ</h2>
          <span className="hint" data-testid="replay-load-status">
            {buyTimeMs ? `Đang chọn ${formatDateTime(buyTimeMs)} · ${hoursBefore.toFixed(1)} giờ nến phía trước` : 'Chưa chọn thời điểm'}
            {candles.length > 0 && ` · Snapshot #${snapshotId.slice(0, 8)}, nến đang tải ${formatDateTime(candles[0].open_time_ms)} → ${formatDateTime(candles[candles.length - 1].close_time_ms)}`}
          </span>
        </div>
        {loadingCandles ? (
          <div className="card"><Spinner label="Đang tải nến…" /></div>
        ) : candles.length === 0 ? (
          <div className="card"><p className="muted">Chưa có dữ liệu nến cho bộ dữ liệu này.</p></div>
        ) : (
          <ReplayChart
            candles={candles}
            phase="selection"
            buyTimeMs={buyTimeMs}
            buyPrice={price > 0 ? price : 0}
            onSelect={pickCandle}
            timeframe={timeframe}
          />
        )}
      </div>

      <div className="row">
        <button type="button" className="btn" data-testid="replay-run-analysis" disabled={blocked || busy === 'create'} onClick={() => void runAnalysis()}>
          {busy === 'create' ? 'Đang chạy…' : gemini ? 'Tạo báo cáo' : 'Xem vùng vào lệnh'}
        </button>
        <span className="hint">Chỉ dùng nến đã đóng trước thời điểm dự báo.</span>
      </div>
    </div>
  );
}
