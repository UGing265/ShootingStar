import React from 'react';
import Link from 'next/link';
import { fetchFromApi } from '@/shared/api-client';
import { Badge, Card, EmptyState, ErrorBanner, PageHeader, StatBox } from '@/shared/ui/primitives';
import { formatDate, formatInt, formatIsoDateTime } from '@/shared/format';
import type { SnapshotSummary } from '@/features/data/types';

interface HealthData {
  status: string;
  database_status: string;
  engine: string;
  timestamp_utc: string;
}

const STEPS = [
  {
    href: '/data',
    title: 'Lịch sử giá',
    text: 'Tải và xem nến BTC/USDT đã lưu, kiểm tra khoảng thiếu nến.',
  },
  {
    href: '/replay',
    title: 'Mô phỏng',
    text: 'Chọn một thời điểm trong quá khứ, xem dự báo, vào lệnh thử và đối chiếu kết quả.',
  },
  {
    href: '/report',
    title: 'Báo cáo',
    text: 'Đọc lại báo cáo phân tích của các lần mô phỏng đã chạy.',
  },
];

export default async function DashboardPage() {
  const [healthRes, snapshotsRes] = await Promise.all([
    fetchFromApi<HealthData>('/health'),
    fetchFromApi<SnapshotSummary[]>('/snapshots', { limit: 5 }),
  ]);

  const health = healthRes.data;
  const snapshots = snapshotsRes.data ?? [];
  const latest = snapshots[0];
  const error = healthRes.error || snapshotsRes.error;
  const serviceOk = health?.status === 'ok';

  return (
    <div className="page">
      <PageHeader
        title="Tổng quan"
        description="Nghiên cứu hướng giá BTC/USDT trong 30 phút bằng dữ liệu lịch sử. Chỉ dùng nến đã đóng, không nhìn trước tương lai."
      />

      {error && <ErrorBanner message={error} />}

      <div className="grid-3">
        <Card compact>
          <div className="stat-label">Dịch vụ dữ liệu</div>
          <div className="row" style={{ marginTop: 4 }}>
            <Badge variant={health ? (serviceOk ? 'success' : 'error') : 'neutral'}>
              {health ? (serviceOk ? 'Đang hoạt động' : 'Có lỗi') : 'Chưa có dữ liệu'}
            </Badge>
          </div>
          <div className="stat-subtext">
            {health ? `Cập nhật ${formatIsoDateTime(health.timestamp_utc)} (UTC+7)` : 'Không kết nối được dịch vụ'}
          </div>
        </Card>
        <Card compact>
          <StatBox
            label="Bộ dữ liệu gần đây"
            value={snapshotsRes.error ? 'Không tải được' : formatInt(snapshots.length)}
            subtext="Tối đa 5 bộ mới nhất"
          />
        </Card>
        <Card compact>
          <StatBox
            label="Nến mới nhất"
            value={latest ? formatDate(latest.end_time_ms) : 'Chưa có dữ liệu'}
            subtext={latest ? `${latest.symbol} · ${latest.timeframe}` : 'Tải dữ liệu ở trang Lịch sử giá'}
          />
        </Card>
      </div>

      <div className="grid-3">
        {STEPS.map((step, i) => (
          <Card key={step.href} compact>
            <div className="stack-sm">
              <span className="stat-label">Bước {i + 1}</span>
              <h2 className="card-title">{step.title}</h2>
              <p className="card-sub">{step.text}</p>
              <Link href={step.href} className="link-more">
                Mở {step.title.toLowerCase()} →
              </Link>
            </div>
          </Card>
        ))}
      </div>

      <Card>
        <div className="spread" style={{ marginBottom: 12 }}>
          <h2 className="card-title">Bộ dữ liệu giá gần đây</h2>
          <Link href="/data" className="link-more">
            Xem tất cả →
          </Link>
        </div>
        {snapshotsRes.error ? (
          <EmptyState message="Không tải được danh sách bộ dữ liệu." />
        ) : snapshots.length === 0 ? (
          <EmptyState
            message="Chưa có bộ dữ liệu giá nào."
            actionLabel="Tải dữ liệu giá"
            actionHref="/data"
          />
        ) : (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Cặp giao dịch</th>
                  <th>Số nến</th>
                  <th>Từ ngày</th>
                  <th>Đến ngày</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {snapshots.map((s) => (
                  <tr key={s.id}>
                    <td>
                      {s.symbol} · {s.timeframe}
                    </td>
                    <td>{formatInt(s.candle_count)}</td>
                    <td>{formatDate(s.start_time_ms)}</td>
                    <td>{formatDate(s.end_time_ms)}</td>
                    <td>
                      <Link href={`/data?snapshot_id=${s.id}`}>Xem</Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
