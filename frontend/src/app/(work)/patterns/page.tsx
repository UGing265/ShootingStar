import React from 'react';
import { fetchFromApi } from '@/shared/api-client';
import { Card, ErrorBanner } from '@/shared/ui/primitives';
import { PatternRuleDTO } from '@/features/patterns/types';
import { PatternRuleListView } from '@/features/patterns/components';

export default async function PatternsPage() {
  const res = await fetchFromApi<PatternRuleDTO[]>('/pattern-rules');
  const rules = res.data || [];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 32 }}>
      <div className="page-header">
        <h1 className="page-title">Mẫu hình giá</h1>
        <p className="page-description">
          Xem các quy tắc nhận diện mẫu nến, điều kiện không còn hiệu lực và kết quả biến động giá lịch sử sau 30 phút.
        </p>
      </div>

      {res.error && <ErrorBanner message={res.error} />}

      <Card>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <h2 style={{ fontSize: 20, fontWeight: 600 }}>Quy tắc mẫu nến</h2>
          <span style={{ fontSize: 13, color: 'var(--ink-muted)' }}>
            Hiển thị {rules.length} quy tắc
          </span>
        </div>
        <PatternRuleListView rules={rules} />
      </Card>
    </div>
  );
}
