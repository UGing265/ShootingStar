import React from 'react';
import { fetchFromApi } from '@/shared/api-client';
import { Card, ErrorBanner } from '@/shared/ui/primitives';
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

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 32 }}>
      <div className="page-header">
        <h1 className="page-title">Lịch sử giá</h1>
        <p className="page-description">
          Dữ liệu nến lịch sử đã lưu trong các bản dữ liệu Parquet; xem mã kiểm tra SHA-256, khoảng thiếu nến và chất lượng dữ liệu. Đây không phải giá thị trường trực tiếp.
        </p>
      </div>

      {(runsRes.error || snapshotsRes.error || detailError) && (
        <ErrorBanner message={runsRes.error || snapshotsRes.error || detailError || 'Không tải được dữ liệu giá đã lưu'} />
      )}


      <SnapshotDownloader />
      {quality && <QualityCard quality={quality} />}

      {targetSnapshotId && (
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
      )}

      <Card>
        <h2 style={{ fontSize: 20, fontWeight: 600, marginBottom: 16 }}>Bản dữ liệu Parquet</h2>
        <SnapshotsView snapshots={snapshots} selectedId={targetSnapshotId || undefined} />
      </Card>
      <Card>
        <h2 style={{ fontSize: 20, fontWeight: 600, marginBottom: 16 }}>Lần nạp dữ liệu</h2>
        <IngestionRunsView runs={runs} />
      </Card>
    </div>
  );
}
