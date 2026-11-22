import React from 'react';
import { Badge, Card, Notice } from '@/shared/ui/primitives';
import { formatDateTime, formatPct, formatUsd } from '@/shared/format';
import type { StrategyEvaluationDTO, StrategyOutcomeDTO } from './types';

function pctFrom(entry: number | null, level: number | null): number | null {
  return entry && level ? ((level - entry) / entry) * 100 : null;
}

function reasonText(reasons: string[]): string {
  if (reasons.includes('NO_TARGET')) {
    return 'Nến này đang sát đỉnh nên không có mức kháng cự cao hơn để đặt chốt lời, hoặc tỷ lệ lời/lỗ chưa đạt mức tối thiểu.';
  }
  if (reasons.includes('INSUFFICIENT_HISTORY')) return 'Chưa đủ nến lịch sử phía trước để xác định hỗ trợ và kháng cự.';
  if (reasons.includes('TICK_COLLAPSE')) return 'Khoảng cách giá quá hẹp: mức cắt lỗ nằm sát giá vào lệnh.';
  if (reasons.includes('RISK_EXCEEDED')) return 'Rủi ro cắt lỗ vượt ngưỡng cho phép.';
  return reasons.length > 0 ? reasons.join(', ') : 'Không thỏa điều kiện an toàn.';
}

function stateBadge(state: string): { label: string; variant: 'success' | 'warning' | 'neutral' } {
  if (state === 'ELIGIBLE' || state === 'EXECUTED') return { label: 'Đủ điều kiện vào lệnh', variant: 'success' };
  if (state === 'WAITING') return { label: 'Chờ nến xác nhận', variant: 'warning' };
  if (state === 'EXPIRED') return { label: 'Hết hạn chờ', variant: 'neutral' };
  if (state === 'INVALIDATED') return { label: 'Điểm vào bị vô hiệu', variant: 'neutral' };
  return { label: 'Không có điểm vào', variant: 'neutral' };
}

function Level({ label, value, hint, tone }: { label: string; value: string; hint?: string; tone?: 'up' | 'down' }) {
  return (
    <div>
      <div className="stat-label">{label}</div>
      <div className={`replay-level${tone ? ` replay-level-${tone}` : ''}`}>{value}</div>
      {hint && <div className="stat-subtext">{hint}</div>}
    </div>
  );
}

export function StrategyCard({ evaluation }: { evaluation: StrategyEvaluationDTO }) {
  const entry = evaluation.proposed_entry;
  const state = stateBadge(evaluation.candidate_state);
  const tpPct = pctFrom(entry, evaluation.target_price);
  const slPct = pctFrom(entry, evaluation.stop_price);

  return (
    <Card>
      <div className="spread">
        <div>
          <h2 className="card-title" data-testid="replay-strategy-title">Vùng vào lệnh theo chiến thuật 30 phút</h2>
          <p className="card-sub">Vùng vào lệnh, chốt lời và cắt lỗ tại thời điểm đã chọn.</p>
        </div>
        <Badge variant={state.variant}>{state.label}</Badge>
      </div>

      {entry ? (
        <>
          <div className="grid-4 replay-levels">
            <Level
              label="Vùng vào lệnh"
              value={formatUsd(entry)}
              hint={
                evaluation.zone_low && evaluation.zone_high
                  ? `${formatUsd(evaluation.zone_low)} – ${formatUsd(evaluation.zone_high)}`
                  : undefined
              }
            />
            <Level label="Chốt lời" value={formatUsd(evaluation.target_price)} hint={tpPct !== null ? formatPct(tpPct) : undefined} tone="up" />
            <Level label="Cắt lỗ" value={formatUsd(evaluation.stop_price)} hint={slPct !== null ? formatPct(slPct) : undefined} tone="down" />
            <Level
              label="Lời / lỗ"
              value={evaluation.reward_risk_ratio !== null ? `1 : ${evaluation.reward_risk_ratio.toFixed(2)}` : 'Chưa có dữ liệu'}
            />
            {evaluation.support_level !== null && <Level label="Mốc hỗ trợ" value={formatUsd(evaluation.support_level)} />}
            {evaluation.reclaim_level !== null && <Level label="Mốc lấy lại" value={formatUsd(evaluation.reclaim_level)} />}
          </div>
          <p className="hint" style={{ marginTop: 12 }}>
            {evaluation.is_trade_eligible
              ? 'Đủ điều kiện khớp lệnh sau khi tính phí và trượt giá.'
              : 'Chưa đủ điều kiện khớp lệnh sau khi tính phí và trượt giá.'}
          </p>
        </>
      ) : (
        <div style={{ marginTop: 12 }}>
          <Notice variant="warning" title="Không vào lệnh tại nến này.">
            {reasonText(evaluation.reasons)}
          </Notice>
        </div>
      )}
    </Card>
  );
}

const OUTCOME_LABELS: Record<string, { label: string; variant: 'success' | 'error' | 'neutral' | 'warning' }> = {
  TP_FIRST: { label: 'Chạm chốt lời trước', variant: 'success' },
  SL_FIRST: { label: 'Chạm cắt lỗ trước', variant: 'error' },
  TIMEOUT: { label: 'Hết 30 phút, chưa chạm mức nào', variant: 'neutral' },
  AMBIGUOUS: { label: 'Nến chạm cả hai mức, không phân định được', variant: 'warning' },
  CENSORED: { label: 'Thiếu nến để kết luận', variant: 'warning' },
  UNSCORABLE: { label: 'Không chấm điểm được', variant: 'warning' },
  UNFILLED: { label: 'Giá không chạm vùng vào lệnh', variant: 'neutral' },
  NO_TRADE: { label: 'Không vào lệnh', variant: 'neutral' },
};

export function StrategyResult({ outcome }: { outcome: StrategyOutcomeDTO }) {
  const meta = (outcome.outcome && OUTCOME_LABELS[outcome.outcome]) || { label: 'Chưa có dữ liệu', variant: 'neutral' as const };
  const net = outcome.net_return_pct;
  const costNote =
    outcome.fee_rate_bps != null && outcome.slippage_bps != null
      ? `Đã trừ phí ${outcome.fee_rate_bps} bps mỗi chiều và trượt giá ${outcome.slippage_bps} bps.`
      : null;

  return (
    <Card>
      <div className="spread">
        <h2 className="card-title" data-testid="replay-strategy-result-title">Kết quả vào lệnh thử</h2>
        <Badge variant={meta.variant}>{meta.label}</Badge>
      </div>
      <div className="grid-4 replay-levels">
        <Level label="Khớp lệnh" value={outcome.trade_executed ? 'Đã khớp' : 'Không khớp'} />
        <Level label="Giá vào" value={outcome.entry_price != null ? formatUsd(outcome.entry_price) : 'Chưa có dữ liệu'} hint={outcome.entry_time_ms ? formatDateTime(outcome.entry_time_ms) : undefined} />
        <Level label="Giá thoát" value={outcome.exit_price != null ? formatUsd(outcome.exit_price) : 'Chưa có dữ liệu'} hint={outcome.exit_time_ms ? formatDateTime(outcome.exit_time_ms) : undefined} />
        <Level
          label="Lãi/lỗ sau phí"
          value={net != null ? formatPct(net) : 'Chưa có dữ liệu'}
          tone={net != null && net > 0 ? 'up' : net != null && net < 0 ? 'down' : undefined}
        />
      </div>
      {costNote && (
        <p className="hint" style={{ marginTop: 12 }}>
          {costNote}
        </p>
      )}
    </Card>
  );
}
