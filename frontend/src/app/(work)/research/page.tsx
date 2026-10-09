import React from 'react';
import { fetchFromApi } from '@/shared/api-client';
import { Card, ErrorBanner } from '@/shared/ui/primitives';
import { ExperimentSummary } from '@/features/research/types';
import { ExperimentListView } from '@/features/research/components';

export default async function ResearchPage() {
  const res = await fetchFromApi<ExperimentSummary[]>('/experiments', { limit: 50 });
  const experiments = res.data || [];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 32 }}>
      <div className="page-header">
        <h1 className="page-title">Kết quả thử nghiệm</h1>
        <p className="page-description">
          Xem các thử nghiệm mô hình dự đoán hướng giá sau 30 phút đã được lưu, cùng cách tách dữ liệu huấn luyện, hiệu chỉnh và kiểm tra.
        </p>
      </div>

      {res.error && <ErrorBanner message={res.error} />}

      <Card>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <h2 style={{ fontSize: 20, fontWeight: 600 }}>Thử nghiệm đã ghi nhận</h2>
          <span style={{ fontSize: 13, color: 'var(--ink-muted)' }}>
            Hiển thị {experiments.length} thử nghiệm
          </span>
        </div>
        <ExperimentListView experiments={experiments} />
      </Card>
    </div>
  );
}
