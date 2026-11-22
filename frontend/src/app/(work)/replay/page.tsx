import React from 'react';
import { fetchFromApi } from '@/shared/api-client';
import { EmptyState, ErrorBanner, PageHeader } from '@/shared/ui/primitives';
import type { CandleDTO, SnapshotSummary } from '@/features/data/types';
import { ReplayPlayer } from '@/features/replay/replay-player';
import { WINDOW_CANDLES, windowStartMs } from '@/features/replay/replay-utils';

export default async function ReplayPage() {
  const result = await fetchFromApi<SnapshotSummary[]>('/snapshots');
  const snapshots = result.data ?? [];

  let initialCandles: CandleDTO[] = [];
  if (snapshots.length > 0) {
    const first = snapshots[0];
    const candlesRes = await fetchFromApi<CandleDTO[]>(`/snapshots/${first.id}/candles`, { start_ms: windowStartMs(first, null), limit: WINDOW_CANDLES });
    initialCandles = candlesRes.data ?? [];
  }

  return (
    <div className="page">
      <PageHeader
        title="Mô phỏng"
        description="Quay lại một thời điểm trong quá khứ, xem phân tích chỉ từ nến đã đóng, đưa ra dự đoán rồi đối chiếu với diễn biến thật."
      />
      {result.error && <ErrorBanner message={result.error} />}
      {snapshots.length === 0 ? (
        <div className="card">
          <EmptyState
            message="Chưa có bộ dữ liệu giá nào để mô phỏng."
            actionLabel="Tải dữ liệu ở trang Lịch sử giá"
            actionHref="/data"
          />
        </div>
      ) : (
        <ReplayPlayer snapshots={snapshots} initialCandles={initialCandles} />
      )}
    </div>
  );
}
