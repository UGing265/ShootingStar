import React from 'react';
import Link from 'next/link';
import { Card, Badge, StatBox, EmptyState } from '@/shared/ui/primitives';
import { SignalSummary, SignalDetailResponse } from './types';

function signalStatus(status: string): string {
  switch (status) {
    case 'PENDING': return 'Chờ đánh giá';
    case 'EVALUATED': return 'Đã đánh giá';
    case 'UNSCORABLE': return 'Không thể đánh giá';
    default: return status;
  }
}

function signalClass(value: string): string {
  switch (value) {
    case 'UP': return 'Tăng';
    case 'DOWN': return 'Giảm';
    case 'NO_TRADE': return 'Không giao dịch';
    default: return value;
  }
}

function signalDecision(value: string): string {
  switch (value) {
    case 'BUY': return 'Đề xuất mua';
    case 'LONG': return 'Đề xuất mua';
    case 'TRADE_LONG': return 'Đề xuất mua';
    case 'HOLD': return 'Giữ';
    case 'NO_TRADE': return 'Không giao dịch';
    case 'ABSTAIN': return 'Đứng ngoài';
    default: return value;
  }
}

export function SignalListView({ signals }: { signals: SignalSummary[] }) {
  if (signals.length === 0) {
    return <EmptyState title="Chưa có dự đoán" message="Chưa ghi nhận dự đoán nào từ mô hình nghiên cứu." />;
  }

  return (
    <div className="table-responsive">
      <table className="data-table">
        <thead>
          <tr>
            <th>Thời gian dự đoán (UTC)</th>
            <th>Phân loại</th>
            <th>Xác suất tăng</th>
            <th>Quyết định</th>
            <th>Trạng thái</th>
            <th>Lợi suất thực tế</th>
            <th>Thao tác</th>
          </tr>
        </thead>
        <tbody>
          {signals.map((s) => (
            <tr key={s.id}>
              <td>{new Date(s.prediction_time_ms).toISOString().slice(11, 19)}</td>
              <td>
                <Badge variant={s.predicted_class === 'UP' ? 'success' : 'neutral'}>
                  {signalClass(s.predicted_class)}
                </Badge>
              </td>
              <td>{(s.probability_up * 100).toFixed(1)}%</td>
              <td>
                <span style={{ fontSize: 13, fontWeight: 500 }}>{signalDecision(s.decision)}</span>
              </td>
              <td>
                <Badge
                  variant={
                    s.status === 'EVALUATED'
                      ? 'success'
                      : s.status === 'PENDING'
                      ? 'warning'
                      : 'error'
                  }
                >
                  {signalStatus(s.status)}
                </Badge>
              </td>
              <td>
                {s.realized_return !== null ? (
                  <span
                    style={{
                      color:
                        s.realized_return > 0
                          ? 'var(--success)'
                          : s.realized_return < 0
                          ? 'var(--error)'
                          : 'var(--ink)',
                      fontWeight: 500,
                    }}
                  >
                    {(s.realized_return * 100).toFixed(2)}%
                  </span>
                ) : (
                  '—'
                )}
              </td>
              <td>
                <Link href={`/signals/${s.id}`} className="nav-link" style={{ fontWeight: 500 }}>
                  Xem chi tiết →
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function SignalDetailView({ detail }: { detail: SignalDetailResponse }) {
  const { prediction, outcome, reviews, audit_logs } = detail;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <Card>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
          <div>
            <h2 style={{ fontSize: 24, fontWeight: 600 }}>Chi tiết dự đoán</h2>
            <p style={{ fontSize: 13, color: 'var(--ink-muted)', marginTop: 4 }}>
              ID dự đoán: <code className="code-snippet">{prediction.id}</code> | Thời gian:{' '}
              {new Date(prediction.prediction_time_ms).toISOString().replace('T', ' ').slice(0, 19)} UTC
            </p>
          </div>
          <Badge
            variant={
              outcome?.status === 'EVALUATED'
                ? 'success'
                : outcome?.status === 'UNSCORABLE'
                ? 'error'
                : 'warning'
            }
          >
            {signalStatus(outcome?.status ?? 'PENDING')}
          </Badge>
        </div>

        <div className="grid-cols-4" style={{ marginBottom: 16 }}>
          <StatBox label="Phân loại dự đoán" value={signalClass(prediction.predicted_class)} />
          <StatBox label="Xác suất tăng" value={`${(prediction.probability_up * 100).toFixed(1)}%`} />
          <StatBox label="Quyết định" value={signalDecision(prediction.decision)} subtext={prediction.decision_reason} />
          <StatBox
            label="Lợi suất thực tế"
            value={outcome?.realized_return !== null && outcome?.realized_return !== undefined ? `${(outcome.realized_return * 100).toFixed(2)}%` : 'Chưa có dữ liệu'}
          />
        </div>

        <div style={{ fontSize: 12, color: 'var(--ink-muted)', background: 'var(--surface-pearl)', padding: 12, borderRadius: 8, border: '1px solid var(--hairline)' }}>
          🔒 <strong>Quy tắc thời điểm:</strong> Dự đoán được ghi nhận sau khi nến đóng. Khi dự đoán DOWN, chiến lược spot đứng ngoài và giữ tiền mặt (lợi suất 0,0%); không tính lợi nhuận từ vị thế bán khống.
        </div>
      </Card>

      {outcome && (
        <Card>
          <h3 style={{ fontSize: 18, fontWeight: 600, marginBottom: 16 }}>Kết quả sau thời gian dự đoán</h3>
          <div className="grid-cols-3">
            <StatBox label="Trạng thái kết quả" value={signalStatus(outcome.status)} />
            <StatBox label="Nhãn thực tế" value={outcome.realized_label ? signalClass(outcome.realized_label) : 'Chưa có dữ liệu'} />
            <StatBox label="Thời điểm đánh giá (UTC)" value={new Date(outcome.evaluated_at_ms).toISOString().slice(11, 19)} />
          </div>
          {outcome.unscorable_reason && (
            <div style={{ marginTop: 12, color: 'var(--error)', fontSize: 13 }}>
              <strong>Lý do không thể đánh giá:</strong> {outcome.unscorable_reason}
            </div>
          )}
        </Card>
      )}

      {reviews && reviews.length > 0 && (
        <Card>
          <h3 style={{ fontSize: 18, fontWeight: 600, marginBottom: 16 }}>Đánh giá thủ công ({reviews.length})</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {reviews.map((r) => (
              <div key={r.id} style={{ fontSize: 14, borderBottom: '1px solid var(--hairline)', paddingBottom: 8 }}>
                <p>
                  <strong>Người đánh giá:</strong> {r.reviewer_id} • <strong>Quyết định:</strong> {signalDecision(r.override_decision)}
                </p>
                <p style={{ marginTop: 4, color: 'var(--ink-muted)' }}>{r.notes}</p>
                <p style={{ marginTop: 4, fontSize: 11, color: 'var(--ink-subtle)' }}>Ghi nhận: {r.created_at}</p>
              </div>
            ))}
          </div>
        </Card>
      )}

      {audit_logs && audit_logs.length > 0 && (
        <Card>
          <h3 style={{ fontSize: 18, fontWeight: 600, marginBottom: 16 }}>Nhật ký kiểm toán</h3>
          <table className="data-table">
            <thead>
              <tr>
                <th>Hành động</th>
                <th>Chi tiết</th>
                <th>Thời điểm</th>
              </tr>
            </thead>
            <tbody>
              {audit_logs.map((log) => (
                <tr key={log.id}>
                  <td><strong>{log.action}</strong></td>
                  <td><code className="code-snippet">{JSON.stringify(log.details)}</code></td>
                  <td>{log.created_at.slice(0, 19).replace('T', ' ')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
