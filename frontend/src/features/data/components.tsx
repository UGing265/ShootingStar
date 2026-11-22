import React from 'react';
import Link from 'next/link';
import { Card, Badge, StatBox, EmptyState } from '@/shared/ui/primitives';
import { formatDateTime, formatInt, formatIsoDateTime } from '@/shared/format';
import { IngestionRunSummary, SnapshotSummary, SnapshotQualityResponse } from './types';

/** Coverage ratio (0..1) → `99.85%`; `Chưa có dữ liệu` when missing. */
export function formatCoverage(ratio: number | null | undefined): string {
  if (ratio === null || ratio === undefined || Number.isNaN(ratio)) return 'Chưa có dữ liệu';
  return `${(ratio * 100).toFixed(2)}%`;
}

export function IngestionRunsView({ runs }: { runs: IngestionRunSummary[] }) {
  if (runs.length === 0) {
    return <EmptyState title="Chưa có lần nạp dữ liệu" message="Chưa ghi nhận đợt nạp dữ liệu thị trường nào." />;
  }

  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>Cặp / khung nến</th>
            <th>Chất lượng</th>
            <th>Khoảng thời gian (UTC+7)</th>
            <th>Số nến hợp lệ</th>
            <th>Bao phủ</th>
            <th>Khoảng thiếu</th>
            <th>Thời điểm nạp (UTC+7)</th>
          </tr>
        </thead>
        <tbody>
          {runs.map((r) => (
            <tr key={r.id}>
              <td>
                <strong>{r.symbol}</strong> · {r.timeframe}
              </td>
              <td>
                <Badge variant={r.is_pristine ? 'success' : 'warning'}>
                  {r.is_pristine ? 'Không thiếu khoảng' : 'Có khoảng thiếu'}
                </Badge>
              </td>
              <td>
                {formatDateTime(r.start_time_ms)} → {formatDateTime(r.end_time_ms)}
              </td>
              <td>{formatInt(r.valid_candles_count)}</td>
              <td>{formatCoverage(r.coverage_ratio)}</td>
              <td>{formatInt(r.missing_intervals_count)}</td>
              <td>{formatIsoDateTime(r.created_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function SnapshotsView({
  snapshots,
  selectedId,
}: {
  snapshots: SnapshotSummary[];
  selectedId?: string;
}) {
  if (snapshots.length === 0) {
    return <EmptyState title="Chưa có bộ dữ liệu" message="Chưa có bộ dữ liệu giá nào được lưu." />;
  }

  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>Mã</th>
            <th>Cặp / khung nến</th>
            <th>Số nến</th>
            <th>Khoảng thời gian (UTC+7)</th>
            <th>
              <span className="visually-hidden">Thao tác</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {snapshots.map((s) => (
            <tr key={s.id} aria-selected={s.id === selectedId}>
              <td>
                <span className="data-id">{s.id.slice(0, 8)}</span>
              </td>
              <td>
                <strong>{s.symbol}</strong> · {s.timeframe}
              </td>
              <td>{formatInt(s.candle_count)}</td>
              <td>
                {formatDateTime(s.start_time_ms)} → {formatDateTime(s.end_time_ms)}
              </td>
              <td>
                <Link href={`/data?snapshot_id=${s.id}`} className="link-more">
                  Xem
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function QualityCard({ quality }: { quality: SnapshotQualityResponse }) {
  const qualityStatus: Record<string, string> = {
    VERIFIED_PRISTINE: 'Đã xác minh: không thiếu khoảng',
    VERIFIED_WITH_GAPS: 'Đã xác minh: có khoảng thiếu',
    UNAVAILABLE_NO_INGESTION_RUN: 'Chưa có lần nạp để xác minh',
  };
  const gapStatus: Record<string, string> = {
    UNAVAILABLE_NOT_PERSISTED: 'Danh sách khoảng thiếu chưa được lưu.',
  };
  const badgeVariant =
    quality.is_pristine === true ? 'success' : quality.is_pristine === false ? 'warning' : 'neutral';

  return (
    <Card>
      <div className="stack">
        <div className="spread">
          <div>
            <h2 className="card-title">Chất lượng bộ dữ liệu</h2>
            <p className="card-sub">
              Mã: <span className="data-id">{quality.snapshot_id.slice(0, 8)}</span> · {quality.symbol} · {quality.timeframe}
            </p>
          </div>
          <Badge variant={badgeVariant}>{qualityStatus[quality.quality_status] ?? quality.quality_status}</Badge>
        </div>

        <div className="grid-3">
          <StatBox label="Tỷ lệ bao phủ" value={formatCoverage(quality.coverage_ratio)} />
          <StatBox label="Khoảng thiếu" value={formatInt(quality.missing_intervals_count)} />
          <StatBox label="Nến trùng" value={formatInt(quality.duplicate_candles_count)} />
        </div>

        <p className="hint">
          {gapStatus[quality.gap_list_status] ?? quality.gap_list_status} Chỉ số chưa có dữ liệu được ghi là “Chưa có dữ liệu”, không suy đoán.
        </p>
      </div>
    </Card>
  );
}
