'use client';

import React from 'react';
import Link from 'next/link';
import { Card, Notice, Spinner } from '@/shared/ui/primitives';
import { ReportView } from '../report/report-view';
import { isInProgress } from '../report/labels';
import { reportHref } from '../report/recent-reports';
import { ReplayChart } from './replay-chart';
import { StrategyCard } from './strategy-card';
import { strategyLevels } from './replay-utils';
import type { ReplaySession } from './use-replay-session';

export function ReplayAnalysis({ session, timeframe }: { session: ReplaySession; timeframe: string }) {
  const { externalJob, externalMock, simJob, candles, busy, error, addStrategy, setStep, reset } = session;

  const buyTimeMs = externalJob?.prediction_time_t_ms ?? simJob?.buy_time_ms ?? 0;
  const buyPrice = externalJob?.purchase_price_p ?? simJob?.buy_price ?? 0;
  const running = externalJob ? isInProgress(externalJob.status) : false;
  const failed = externalJob?.status === 'FAILED' || externalJob?.status === 'FAILED_INTERRUPTED';
  const evidenceTimes = externalJob?.ai_prediction?.evidence_candle_times ?? [];
  const levels = strategyLevels(simJob?.strategy_evaluation);

  return (
    <div className="stack" data-testid="replay-analysis">
      <ReplayChart
        candles={candles}
        phase="analysis"
        buyTimeMs={buyTimeMs}
        buyPrice={buyPrice}
        evidenceTimes={evidenceTimes}
        strategyLevels={levels}
        timeframe={timeframe}
      />

      {externalJob && <ReportView job={externalJob} live={false} mock={externalMock} />}

      {simJob?.strategy_evaluation && <StrategyCard evaluation={simJob.strategy_evaluation} />}
      {simJob && !simJob.strategy_evaluation && (
        <Notice variant="neutral" title="Chưa có vùng vào lệnh.">
          Máy chủ chưa trả về đánh giá chiến thuật cho thời điểm này.
        </Notice>
      )}

      {externalJob && !simJob && !running && !failed && (
        <Card compact>
          <div className="spread">
            <div>
              <h2 className="card-title">Muốn xem vùng vào lệnh, chốt lời và cắt lỗ?</h2>
              <p className="card-sub">Chạy thêm chiến thuật vào lệnh 30 phút tại cùng thời điểm này.</p>
            </div>
            <button type="button" className="btn btn-secondary" data-testid="replay-add-strategy" disabled={busy === 'create'} onClick={() => void addStrategy()}>
              {busy === 'create' ? 'Đang chạy…' : 'Thêm vùng vào lệnh'}
            </button>
          </div>
        </Card>
      )}

      {error && <Notice variant="error">{error}</Notice>}
      {running && <Spinner label="Đang viết báo cáo, vui lòng chờ…" />}

      <div className="spread">
        <button type="button" className="btn btn-quiet" onClick={reset}>
          Chọn lại thời điểm
        </button>
        <div className="row">
          {externalJob && (
            <Link href={reportHref(externalJob.id, externalMock)} className="link-more">
              Mở trang báo cáo
            </Link>
          )}
          <button type="button" className="btn" disabled={running || failed} onClick={() => setStep('vote')}>
            Tiếp: dự đoán của bạn
          </button>
        </div>
      </div>
    </div>
  );
}
