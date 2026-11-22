'use client';

import React from 'react';
import { Notice } from '@/shared/ui/primitives';
import { formatHorizonMinutes, formatUsd } from '@/shared/format';
import { STRATEGY_HORIZON_MINUTES } from './replay-utils';
import type { ReplaySession } from './use-replay-session';

export function ReplayVote({ session }: { session: ReplaySession }) {
  const { externalJob, simJob, busy, error, vote, setStep } = session;
  const price = externalJob?.purchase_price_p ?? simJob?.buy_price ?? 0;
  const horizon = externalJob?.horizon_minutes ?? simJob?.horizon_minutes ?? STRATEGY_HORIZON_MINUTES;
  const disabled = busy !== null;

  return (
    <div className="stack" data-testid="replay-vote">
      <div className="card">
        <h2 className="card-title">Bạn dự đoán thế nào?</h2>
        <p className="card-sub">
          Sau {formatHorizonMinutes(horizon)}, giá có cao hơn hay thấp hơn mức mua {formatUsd(price)}? Lựa chọn sẽ được khóa lại ngay khi bạn bấm.
        </p>
        <div className="grid-2 replay-vote-grid">
          <button type="button" className="replay-vote replay-vote-up" data-testid="replay-vote-up" disabled={disabled} onClick={() => void vote('UP')}>
            <span className="replay-vote-title">▲ Tăng</span>
            <span className="hint">Cao hơn {formatUsd(price)}</span>
          </button>
          <button type="button" className="replay-vote replay-vote-down" data-testid="replay-vote-down" disabled={disabled} onClick={() => void vote('DOWN')}>
            <span className="replay-vote-title">▼ Giảm</span>
            <span className="hint">Thấp hơn {formatUsd(price)}</span>
          </button>
        </div>
        {busy === 'vote' && <p className="hint">Đang lưu dự đoán…</p>}
      </div>
      {error && <Notice variant="error">{error}</Notice>}
      <div>
        <button type="button" className="btn btn-quiet" disabled={disabled} onClick={() => setStep('analysis')}>
          Quay lại phân tích
        </button>
      </div>
    </div>
  );
}
