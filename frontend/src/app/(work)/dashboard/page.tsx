import React from 'react';
import Link from 'next/link';
import { fetchFromApi } from '@/shared/api-client';
import { Card, Badge, ErrorBanner } from '@/shared/ui/primitives';
import { SnapshotSummary } from '@/features/data/types';
import { ExperimentSummary } from '@/features/research/types';
import { SignalSummary } from '@/features/signals/types';

interface HealthData {
  status: string;
  database: string;
  database_status: string;
  engine: string;
  timestamp_utc: string;
}

export default async function OverviewPage() {
  const [healthRes, snapshotsRes, experimentsRes, signalsRes] = await Promise.all([
    fetchFromApi<HealthData>('/health'),
    fetchFromApi<SnapshotSummary[]>('/snapshots', { limit: 5 }),
    fetchFromApi<ExperimentSummary[]>('/experiments', { limit: 5 }),
    fetchFromApi<SignalSummary[]>('/signals', { limit: 5 }),
  ]);

  const hasError = healthRes.error || snapshotsRes.error || experimentsRes.error || signalsRes.error;
  const health = healthRes.data;
  const snapshots = snapshotsRes.data || [];
  const experiments = experimentsRes.data || [];
  const signals = signalsRes.data || [];

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Tổng quan</h1>
        <p className="page-description">
          Xem dữ liệu giá lịch sử, thử nghiệm và các dự đoán hướng giá BTCUSDT trong 30 phút tới đã ghi nhận.
        </p>
      </div>

      {hasError && (
        <ErrorBanner
          message={
            healthRes.error ||
            snapshotsRes.error ||
            experimentsRes.error ||
            signalsRes.error ||
            'Không kết nối được tới dịch vụ dữ liệu'
          }
        />
      )}

      <div className="grid-cols-3" style={{ marginBottom: 24 }}>
        <Card>
          <div className="stat-label">Trạng thái dịch vụ</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 8 }}>
            <Badge variant={health?.status === 'ok' ? 'success' : 'error'}>
              {health ? (health.status === 'ok' ? 'Hoạt động' : 'Có lỗi') : 'Không có dữ liệu'}
            </Badge>
            <span style={{ fontSize: 13, color: 'var(--ink-muted)' }}>
              Cơ sở dữ liệu: {health?.database_status === 'ok' ? 'Hoạt động' : health?.database_status === 'connected' ? 'Đã kết nối' : health?.database_status ? 'Có lỗi' : 'Không có dữ liệu'}
            </span>
          </div>
          <div className="stat-subtext" style={{ marginTop: 8 }}>
            Hệ quản trị: {health?.engine || 'Không có dữ liệu'} • {health?.timestamp_utc ? health.timestamp_utc.slice(11, 19) + ' UTC' : 'Không có dữ liệu'}
          </div>
        </Card>

        <Card>
          <div className="stat-label">Bản dữ liệu gần đây (tối đa 5)</div>
          <div className="stat-value">{snapshotsRes.error ? 'Không có dữ liệu' : snapshots.length}</div>
          <div className="stat-subtext">
            <Link href="/data">Xem lịch sử giá →</Link>
          </div>
        </Card>

        <Card>
          <div className="stat-label">Thử nghiệm gần đây (tối đa 5)</div>
          <div className="stat-value">{experimentsRes.error ? 'Không có dữ liệu' : experiments.length}</div>
          <div className="stat-subtext">
            <Link href="/research">Xem kết quả thử nghiệm →</Link>
          </div>
        </Card>
      </div>

      <div className="grid-cols-2">
        <Card>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <h3 style={{ fontSize: 18, fontWeight: 600 }}>Bản dữ liệu gần đây</h3>
            <Link href="/data" className="nav-link" style={{ fontWeight: 500 }}>
              Xem lịch sử giá →
            </Link>
          </div>
          {snapshotsRes.error ? (
            <p style={{ fontSize: 14, color: 'var(--ink-muted)' }}>Không tải được danh sách bản dữ liệu.</p>
          ) : snapshots.length === 0 ? (
            <p style={{ fontSize: 14, color: 'var(--ink-muted)' }}>Chưa có bản dữ liệu nào được ghi nhận.</p>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Cặp giao dịch</th>
                  <th>Số nến</th>
                  <th>Mã kiểm tra SHA-256</th>
                </tr>
              </thead>
              <tbody>
                {snapshots.slice(0, 3).map((s) => (
                  <tr key={s.id}>
                    <td>{s.symbol} ({s.timeframe})</td>
                    <td>{s.candle_count.toLocaleString()}</td>
                    <td>
                      <code className="code-snippet">{s.sha256.slice(0, 10)}…</code>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>

        <Card>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <h3 style={{ fontSize: 18, fontWeight: 600 }}>Dự đoán gần đây</h3>
            <Link href="/signals" className="nav-link" style={{ fontWeight: 500 }}>
              Xem tất cả dự đoán →
            </Link>
          </div>
          {signalsRes.error ? (
            <p style={{ fontSize: 14, color: 'var(--ink-muted)' }}>Không tải được danh sách dự đoán.</p>
          ) : signals.length === 0 ? (
            <p style={{ fontSize: 14, color: 'var(--ink-muted)' }}>Chưa có dự đoán nào được ghi nhận.</p>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Thời gian (UTC)</th>
                  <th>Hướng</th>
                  <th>Trạng thái</th>
                </tr>
              </thead>
              <tbody>
                {signals.slice(0, 3).map((sig) => (
                  <tr key={sig.id}>
                    <td>{new Date(sig.prediction_time_ms).toISOString().slice(11, 16)}</td>
                    <td>
                      <Badge variant={sig.predicted_class === 'UP' ? 'success' : 'neutral'}>
                        {sig.predicted_class === 'UP' ? 'Tăng' : sig.predicted_class === 'DOWN' ? 'Giảm' : sig.predicted_class}
                      </Badge>
                    </td>
                    <td>
                      <Badge variant={sig.status === 'EVALUATED' ? 'success' : 'warning'}>
                        {sig.status === 'EVALUATED' ? 'Đã đánh giá' : sig.status === 'PENDING' ? 'Chờ đánh giá' : sig.status}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      </div>
    </div>
  );
}
