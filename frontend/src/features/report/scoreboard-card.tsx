import { Card, EmptyState, Notice } from '@/shared/ui/primitives';
import { formatInt } from '@/shared/format';
import { confidenceLabel } from './labels';

export interface ScoreboardMetric {
  n: number;
  correct: number;
  accuracy: number | null;
  wilson_95: [number, number] | null;
}

export interface ScoreboardData {
  snapshot_id: string;
  horizon_minutes: number;
  lookback_days: number;
  total: number;
  flat: number;
  unscorable: number;
  missing_baseline_or_direction: number;
  scored: number;
  threshold_n: Record<string, number>;
  accuracy: Record<string, ScoreboardMetric>;
  confidence: Record<string, ScoreboardMetric>;
  agreement: Record<string, ScoreboardMetric>;
  possible_memorization: Record<string, ScoreboardMetric>;
}

const PREDICTORS: ReadonlyArray<{ key: string; label: string }> = [
  { key: 'gemini', label: 'Gemini' },
  { key: 'always_up', label: 'Luôn TĂNG' },
  { key: 'momentum_6h', label: 'Theo đà 6h' },
];

function percent(value: number | null): string {
  return value === null ? 'Chưa có dữ liệu' : `${(value * 100).toFixed(1)}%`;
}

function wilson(interval: [number, number] | null): string {
  if (!interval) return 'Chưa có dữ liệu';
  return `${(interval[0] * 100).toFixed(1)}% đến ${(interval[1] * 100).toFixed(1)}%`;
}

function MetricTable({ rows }: { rows: ReadonlyArray<{ label: string; metric: ScoreboardMetric }> }) {
  return (
    <div className="table-wrap" style={{ marginTop: 8 }}>
      <table className="data-table">
        <thead>
          <tr>
            <th>Nguồn</th>
            <th>Độ chính xác</th>
            <th>n</th>
            <th>Khoảng tin cậy 95%</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.label}>
              <td>{row.label}</td>
              <td>{percent(row.metric.accuracy)}</td>
              <td>{formatInt(row.metric.n)}</td>
              <td>{wilson(row.metric.wilson_95)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ScoreboardCard({ data, error }: { data: ScoreboardData | null; error?: string | null }) {
  if (error) {
    return (
      <Notice variant="warning" title="Chưa tải được bảng điểm.">
        {error}
      </Notice>
    );
  }

  return (
    <Card>
      <h2 className="card-title">Bảng điểm dự báo</h2>
      <p className="card-sub">
        Tính trên máy chủ từ các job đã chấm điểm của cùng bộ dữ liệu; trình duyệt chỉ hiển thị.
      </p>

      {!data ? (
        <EmptyState message="Chưa có dữ liệu bảng điểm." />
      ) : data.scored === 0 ? (
        <EmptyState
          title="Chưa có dữ liệu"
          message="Chưa có mốc nào đủ điều kiện chấm điểm (đi ngang hoặc thiếu dữ liệu)."
        />
      ) : (
        <>
          <MetricTable
            rows={PREDICTORS.map((predictor) => ({
              label: predictor.label,
              metric: data.accuracy[predictor.key] ?? { n: 0, correct: 0, accuracy: null, wilson_95: null },
            }))}
          />
          <div className="stack-sm" style={{ marginTop: 12 }}>
            <span className="label">Theo độ tin cậy của Gemini</span>
            {Object.keys(data.confidence).length === 0 ? (
              <p className="hint">Chưa có dữ liệu.</p>
            ) : (
              <MetricTable
                rows={Object.entries(data.confidence).map(([level, metric]) => ({
                  label: confidenceLabel(level),
                  metric,
                }))}
              />
            )}
          </div>
        </>
      )}

      {data && (
        <p className="hint" style={{ marginTop: 8 }}>
          Tổng {formatInt(data.total)} mốc · đã chấm {formatInt(data.scored)} · đi ngang {formatInt(data.flat)} ·
          không chấm được {formatInt(data.unscorable)}.
        </p>
      )}
    </Card>
  );
}
