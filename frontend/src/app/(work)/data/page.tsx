import React from 'react';
import { fetchFromApi } from '@/shared/api-client';
import { Card, ErrorBanner, PageHeader, EmptyState } from '@/shared/ui/primitives';
import {
  IngestionRunSummary,
  SnapshotSummary,
  SnapshotQualityResponse,
  CandleDTO,
} from '@/features/data/types';
import {
  IngestionRunsView,
  SnapshotsView,
  QualityCard,
} from '@/features/data/components';
import { CandlestickChart } from '@/features/data/candlestick-chart';
import { SnapshotDownloader } from '@/features/data/snapshot-downloader';
import '@/features/data/data.css';

interface DataPageProps {
  searchParams?: Promise<{
    snapshot_id?: string;
  }>;
}

export default async function DataPage(props: DataPageProps) {
  const sp = props.searchParams ? await props.searchParams : undefined;
  const selectedSnapshotId = sp?.snapshot_id;
  const [runsRes, snapshotsRes] = await Promise.all([
    fetchFromApi<IngestionRunSummary[]>('/ingestion-runs', { limit: 20 }),
    fetchFromApi<SnapshotSummary[]>('/snapshots', { limit: 20 }),
  ]);

  const runs = runsRes.data || [];
  const snapshots = snapshotsRes.data || [];

  // If a snapshot is selected (or pick first one if available)
  const targetSnapshotId = selectedSnapshotId || (snapshots.length > 0 ? snapshots[0].id : null);

  let quality: SnapshotQualityResponse | null = null;
  let candles: CandleDTO[] = [];
  let detailError: string | null = null;

  const targetSnap = snapshots.find((s) => s.id === targetSnapshotId);

  if (targetSnapshotId) {
    const tfMs = targetSnap?.timeframe === '5m' ? 5 * 60 * 1000 : 60 * 1000;
    const initialStartMs = targetSnap
      ? Math.max(targetSnap.start_time_ms, targetSnap.end_time_ms - 500 * tfMs)
      : undefined;

    const [qualRes, candlesRes] = await Promise.all([
      fetchFromApi<SnapshotQualityResponse>(`/snapshots/${targetSnapshotId}/quality`),
      fetchFromApi<CandleDTO[]>(`/snapshots/${targetSnapshotId}/candles`, {
        start_ms: initialStartMs,
        end_ms: targetSnap?.end_time_ms,
        limit: 500,
      }),
    ]);
    quality = qualRes.data;
    candles = candlesRes.data || [];
    detailError = qualRes.error || candlesRes.error;
  }

  const loadError = runsRes.error || snapshotsRes.error || detailError;

  return (
    <div className="page">
      <PageHeader
        title="Lịch sử giá"
        description="Nến lịch sử đã lưu: kiểm tra khoảng thiếu nến và chất lượng dữ liệu. Đây không phải giá thị trường trực tiếp."
      />

      {loadError && <ErrorBanner message={loadError} />}

      <SnapshotDownloader />

      {quality && <QualityCard quality={quality} />}

      {targetSnapshotId ? (
        <CandlestickChart
          initialCandles={candles}
          timeframe={targetSnap?.timeframe || '1m'}
          symbol={targetSnap?.symbol || 'BTCUSDT'}
          snapshotId={targetSnapshotId}
          snapshotStartMs={targetSnap?.start_time_ms}
          snapshotEndMs={targetSnap?.end_time_ms}
          isPristine={quality?.is_pristine ?? undefined}
          allSnapshots={snapshots.map((s) => ({
            id: s.id,
            symbol: s.symbol,
            timeframe: s.timeframe,
            start_time_ms: s.start_time_ms,
            end_time_ms: s.end_time_ms,
            candle_count: s.candle_count,
          }))}
        />
      ) : (
        <Card>
          <EmptyState title="Chưa có dữ liệu giá" message="Tải một bộ dữ liệu ở phía trên." />
        </Card>
      )}

      <Card>
        <div className="stack">
          <h2 className="card-title">Bộ dữ liệu đã lưu</h2>
          <SnapshotsView snapshots={snapshots} selectedId={targetSnapshotId || undefined} />
        </div>
      </Card>

      <Card>
        <div className="stack">
          <h2 className="card-title">Lần nạp dữ liệu</h2>
          <IngestionRunsView runs={runs} />
        </div>
      </Card>
    </div>
  );
}
