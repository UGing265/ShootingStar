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
  CandleTable,
} from '@/features/data/components';

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

  if (targetSnapshotId) {
    const [qualRes, candlesRes] = await Promise.all([
      fetchFromApi<SnapshotQualityResponse>(`/snapshots/${targetSnapshotId}/quality`),
      fetchFromApi<CandleDTO[]>(`/snapshots/${targetSnapshotId}/candles`, { limit: 20 }),
    ]);
    quality = qualRes.data;
    candles = candlesRes.data || [];
  }

  const hasError = runsRes.error || snapshotsRes.error;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 32 }}>
      <div className="page-header">
        <h1 className="page-title">Lịch sử giá</h1>
        <p className="page-description">
          Dữ liệu nến lịch sử đã lưu trong các bản dữ liệu Parquet; xem mã kiểm tra SHA-256, khoảng thiếu nến và chất lượng dữ liệu. Đây không phải giá thị trường trực tiếp.
        </p>
      </div>

      {hasError && <ErrorBanner message={runsRes.error || snapshotsRes.error || 'Không tải được dữ liệu giá đã lưu'} />}

      {quality && <QualityCard quality={quality} />}

      <Card>
        <h2 style={{ fontSize: 20, fontWeight: 600, marginBottom: 16 }}>Bản dữ liệu Parquet</h2>
        <SnapshotsView snapshots={snapshots} selectedId={targetSnapshotId || undefined} />
      </Card>

      {targetSnapshotId && (
        <Card>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <h2 style={{ fontSize: 20, fontWeight: 600 }}>Xem trước 20 nến đầu tiên</h2>
            <span style={{ fontSize: 13, color: 'var(--ink-muted)' }}>
              Bản dữ liệu đã chọn: <code className="code-snippet">{targetSnapshotId}</code>
            </span>
          </div>
          <CandleTable candles={candles} />
        </Card>
      )}

      <Card>
        <h2 style={{ fontSize: 20, fontWeight: 600, marginBottom: 16 }}>Lần nạp dữ liệu</h2>
        <IngestionRunsView runs={runs} />
      </Card>
    </div>
  );
}
