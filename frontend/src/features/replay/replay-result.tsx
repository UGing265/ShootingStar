'use client';

import React from 'react';
import Link from 'next/link';
import { Badge, Card, Notice, Spinner } from '@/shared/ui/primitives';
import {
  directionArrow,
  directionLabel,
  formatHorizonMinutes,
  formatPct,
  formatUsd,
  forecastDirectionLabel,
} from '@/shared/format';
import { ReplayChart } from './replay-chart';
import { StrategyResult } from './strategy-card';
import { reportHref } from '../report/recent-reports';
import { ForecastComparison } from '../report/forecast-comparison';
import { strategyLevels } from './replay-utils';
import type { ReplaySession } from './use-replay-session';

function Verdict({ correct, outcome }: { correct: boolean | null; outcome?: string | null }) {
  if (outcome === 'FLAT' || outcome === 'UNSCORABLE') {
    return <Badge variant="neutral">Không chấm</Badge>;
  }
  if (correct === null) return <Badge variant="neutral">Chưa có dữ liệu</Badge>;
  return correct ? <Badge variant="success">Đúng</Badge> : <Badge variant="error">Sai</Badge>;
}

function Metric({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="stat-label">{label}</div>
      <div className="stat-value">{children}</div>
    </div>
  );
}

export function ReplayResult({ session, timeframe }: { session: ReplaySession; timeframe: string }) {
  const { externalJob, externalMock, simJob, candles, busy, error, hasOutcome, userVote, reveal, reset } = session;

  const buyTimeMs = externalJob?.prediction_time_t_ms ?? simJob?.buy_time_ms ?? 0;
  const buyPrice = externalJob?.purchase_price_p ?? simJob?.buy_price ?? 0;
  const horizon = externalJob?.horizon_minutes ?? simJob?.horizon_minutes ?? 30;
  const targetTimeMs = buyTimeMs + horizon * 60_000;

  const outcomeDirection = externalJob?.outcome ?? simJob?.outcome?.market_direction ?? null;
  const targetPrice = externalJob?.target_price ?? simJob?.outcome?.future_price ?? null;
  const changePct = simJob?.outcome?.price_change_pct ?? (targetPrice && buyPrice ? ((targetPrice - buyPrice) / buyPrice) * 100 : null);
  const unscorable = simJob?.outcome?.status === 'UNSCORABLE' || externalJob?.outcome === 'UNSCORABLE';
  const flat = outcomeDirection === 'FLAT';
  const flatThreshold = externalJob?.evidence_envelope?.flat_threshold_pct ?? 0.5;

  const userCorrect =
    userVote && (outcomeDirection === 'UP' || outcomeDirection === 'DOWN') ? userVote === outcomeDirection : null;
  const ai = externalJob?.ai_prediction;
  const aiCorrect =
    ai && ai.direction !== 'ABSTAIN' && (outcomeDirection === 'UP' || outcomeDirection === 'DOWN') ? ai.direction === outcomeDirection : null;

  if (busy === 'reveal' && !hasOutcome) {
    return (
      <Card>
        <Spinner label="Đang mở kết quả thực tế…" />
      </Card>
    );
  }

  if (!hasOutcome) {
    return (
      <div className="stack" data-testid="replay-result-pending">
        <Card>
          <h2 className="card-title">Dự đoán đã được lưu</h2>
          <p className="card-sub">Bấm nút bên dưới để mở nến sau thời điểm dự báo và chấm điểm.</p>
          <div style={{ marginTop: 12 }}>
            <button type="button" className="btn" onClick={() => void reveal()}>
              Xem kết quả thực tế
            </button>
          </div>
        </Card>
        {error && <Notice variant="error">{error}</Notice>}
      </div>
    );
  }

  return (
    <div className="stack" data-testid="replay-result-outcome">
      {unscorable && (
        <Notice variant="warning" title="Không chấm điểm được.">
          {simJob?.outcome?.unscorable_reason || 'Chưa đủ nến sau thời điểm dự báo để kết luận.'}
        </Notice>
      )}

      <Card>
        <h2 className="card-title">Thị trường đã đi thế nào</h2>
        <div className="grid-4 replay-levels">
          <Metric label="Giá tại thời điểm">{formatUsd(buyPrice)}</Metric>
          <Metric label={`Giá sau ${formatHorizonMinutes(horizon)}`}>{formatUsd(targetPrice)}</Metric>
          <Metric label="Thay đổi">{changePct !== null ? formatPct(changePct) : 'Chưa có dữ liệu'}</Metric>
          <Metric label="Hướng">
            {directionArrow(outcomeDirection)} {directionLabel(outcomeDirection)}
          </Metric>
        </div>
      </Card>

      {flat && (
        <Notice variant="neutral" title={`Đi ngang (dưới ${flatThreshold}%), không chấm.`}>
          Biến động nhỏ hơn ngưỡng nên không tính đúng sai cho Gemini hay hai luật đơn giản.
        </Notice>
      )}

      {externalJob?.evidence_envelope?.protocol_version === 'forecast-6h-v1' && (
        <ForecastComparison job={externalJob} />
      )}

      <div className="grid-2">
        <Card compact>
          <div className="spread">
            <span className="card-title">Bạn</span>
            <Verdict correct={userCorrect} outcome={outcomeDirection} />
          </div>
          <p className="card-sub">Bạn chọn: {userVote ? directionLabel(userVote) : 'Chưa dự đoán'}</p>
        </Card>
        {ai && (
          <Card compact>
            <div className="spread">
              <span className="card-title">Báo cáo Gemini {formatHorizonMinutes(horizon)}</span>
              {externalMock && <Badge variant="warning">DỮ LIỆU GIẢ LẬP</Badge>}
              {ai.direction === 'ABSTAIN' ? (
                <Badge variant="neutral">Không dự báo</Badge>
              ) : (
                <Verdict correct={aiCorrect} outcome={outcomeDirection} />
              )}
            </div>
            <p className="card-sub">Dự báo: {forecastDirectionLabel(ai.direction)}</p>
          </Card>
        )}
      </div>

      {simJob?.strategy_outcome && <StrategyResult outcome={simJob.strategy_outcome} />}

      <ReplayChart
        candles={candles}
        phase="result"
        buyTimeMs={buyTimeMs}
        buyPrice={buyPrice}
        targetTimeMs={targetTimeMs}
        targetPrice={targetPrice}
        targetCandleCloseMs={targetTimeMs}
        evidenceTimes={ai?.evidence_candle_times}
        strategyLevels={strategyLevels(simJob?.strategy_evaluation)}
        showAll
        timeframe={timeframe}
      />

      <div className="spread">
        {externalJob ? (
          <Link href={reportHref(externalJob.id, externalMock)} className="btn btn-secondary">
            Đọc báo cáo đầy đủ
          </Link>
        ) : (
          <span />
        )}
        <button type="button" className="btn" onClick={reset}>
          Thử thời điểm khác
        </button>
      </div>
    </div>
  );
}
