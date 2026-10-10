import React from 'react';
import { fetchFromApi } from '@/shared/api-client';
import { SnapshotSummary } from '@/features/data/types';
import { ReplayPlayer } from '@/features/replay/replay-player';

export default async function ReplayPage() {
  const result = await fetchFromApi<SnapshotSummary[]>('/snapshots');
  const snapshots = result.data || [];

  return (
    <div className="page-container" style={{ padding: '24px 32px' }}>
      <header className="page-header" style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 24, fontWeight: 700, margin: '0 0 6px 0', color: 'var(--text-primary, #0f172a)' }}>
          Mô phỏng dự đoán (Historical Simulation)
        </h1>
        <p style={{ margin: 0, color: 'var(--text-secondary, #64748b)', fontSize: 14 }}>
          Mô phỏng dự đoán điểm mua trong lịch sử với bảo chứng không nhìn trước (Zero-Lookahead), so sánh AI và dự đoán cá nhân, chấm điểm độc lập khi có kết quả thực tế.
        </p>
      </header>

      {snapshots.length === 0 ? (
        <div
          style={{
            padding: 32,
            textAlign: 'center',
            background: '#ffffff',
            borderRadius: 8,
            border: '1px solid #e2e8f0',
          }}
        >
          <p style={{ margin: '0 0 12px 0', color: '#64748b', fontSize: 15 }}>
            Chưa có snapshot nào trong cơ sở dữ liệu để bắt đầu phiên tua nến.
          </p>
          <a
            href="/data"
            style={{
              display: 'inline-block',
              padding: '8px 18px',
              background: '#2563eb',
              color: '#ffffff',
              borderRadius: 6,
              textDecoration: 'none',
              fontWeight: 600,
              fontSize: 14,
            }}
          >
            Tải snapshot mới từ Binance tại trang Lịch sử giá →
          </a>
        </div>
      ) : (
        <ReplayPlayer snapshots={snapshots} />
      )}
    </div>
  );
}
