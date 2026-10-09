import React from 'react';
import { fetchFromApi } from '@/shared/api-client';
import { Card, ErrorBanner } from '@/shared/ui/primitives';
import { SignalSummary } from '@/features/signals/types';
import { SignalListView } from '@/features/signals/components';

export default async function SignalsPage() {
  const res = await fetchFromApi<SignalSummary[]>('/signals', { limit: 50 });
  const signals = res.data || [];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 32 }}>
      <div className="page-header">
        <h1 className="page-title">Dự đoán</h1>
        <p className="page-description">
          Xem các dự đoán hướng giá đã ghi nhận và kết quả đánh giá sau 30 phút khi có dữ liệu. Dự đoán chưa được đánh giá không có kết quả thực tế.
        </p>
      </div>

      {res.error && <ErrorBanner message={res.error} />}

      <Card>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <h2 style={{ fontSize: 20, fontWeight: 600 }}>Dự đoán đã ghi nhận</h2>
          <span style={{ fontSize: 13, color: 'var(--ink-muted)' }}>
            Hiển thị {signals.length} dự đoán
          </span>
        </div>
        <SignalListView signals={signals} />
      </Card>
    </div>
  );
}
