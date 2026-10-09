import React from 'react';
import Link from 'next/link';
import { Card, Badge, StatBox, EmptyState } from '@/shared/ui/primitives';
import { IngestionRunSummary, SnapshotSummary, SnapshotQualityResponse, CandleDTO } from './types';

export function IngestionRunsView({ runs }: { runs: IngestionRunSummary[] }) {
  if (runs.length === 0) {
    return <EmptyState title="Chưa có lần nạp dữ liệu" message="Chưa ghi nhận đợt nạp dữ liệu thị trường nào." />;
  }

  return (
    <div className="table-responsive">
      <table className="data-table">
        <thead>
          <tr>
            <th>Cặp giao dịch / khung thời gian</th>
            <th>Tính toàn vẹn</th>
            <th>Khoảng thời gian (UTC)</th>
            <th>Số nến hợp lệ</th>
            <th>Số khoảng thiếu</th>
            <th>Thời điểm nạp</th>
          </tr>
        </thead>
        <tbody>
          {runs.map((r) => (
            <tr key={r.id}>
              <td>
                <strong>{r.symbol}</strong> ({r.timeframe})
              </td>
              <td>
                <Badge variant={r.is_pristine ? 'success' : 'warning'}>
                  {r.is_pristine ? 'Không thiếu khoảng' : 'Có khoảng thiếu'}
                </Badge>
              </td>
              <td>
                {new Date(r.start_time_ms).toISOString().slice(0, 16)} →{' '}
                {new Date(r.end_time_ms).toISOString().slice(0, 16)}
              </td>
              <td>{r.valid_candles_count.toLocaleString()}</td>
              <td>{r.missing_intervals_count}</td>
              <td>{r.created_at.slice(0, 19).replace('T', ' ')}</td>
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
    return <EmptyState title="Chưa có bản chụp dữ liệu" message="Chưa tìm thấy tệp Parquet bản chụp dữ liệu trong kho lưu trữ." />;
  }

  return (
    <div className="table-responsive">
      <table className="data-table">
        <thead>
          <tr>
            <th>ID bản chụp</th>
            <th>Cặp giao dịch / khung thời gian</th>
            <th>Số nến</th>
            <th>Khoảng thời gian (UTC)</th>
            <th>SHA-256</th>
            <th>Thao tác</th>
          </tr>
        </thead>
        <tbody>
          {snapshots.map((s) => {
            const isSelected = s.id === selectedId;
            return (
              <tr key={s.id} style={isSelected ? { background: 'var(--surface-pearl)' } : undefined}>
                <td>
                  <strong>{s.id.slice(0, 12)}…</strong>
                </td>
                <td>
                  {s.symbol} ({s.timeframe})
                </td>
                <td>{s.candle_count.toLocaleString()}</td>
                <td>
                  {new Date(s.start_time_ms).toISOString().slice(0, 10)} →{' '}
                  {new Date(s.end_time_ms).toISOString().slice(0, 10)}
                </td>
                <td>
                  <code className="code-snippet">{s.sha256.slice(0, 10)}…</code>
                </td>
                <td>
                  <Link href={`/data?snapshot_id=${s.id}`} className="nav-link" style={{ fontWeight: 500 }}>
                    Xem chi tiết →
                  </Link>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function QualityCard({ quality }: { quality: SnapshotQualityResponse }) {
  const coverageText =
    quality.coverage_ratio !== null ? `${(quality.coverage_ratio * 100).toFixed(2)}%` : 'Chưa có dữ liệu';
  const qualityStatus: Record<string, string> = {
    VERIFIED_PRISTINE: 'Đã xác minh: không thiếu khoảng',
    VERIFIED_WITH_GAPS: 'Đã xác minh: có khoảng thiếu',
    UNAVAILABLE_NO_INGESTION_RUN: 'Chưa có lần nạp dữ liệu để xác minh',
  };
  const gapStatus: Record<string, string> = {
    UNAVAILABLE_NOT_PERSISTED: 'Không có danh sách khoảng thiếu được lưu',
  };
  return (
    <Card>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
        <div>
          <h3 style={{ fontSize: 18, fontWeight: 600 }}>Chất lượng bản chụp dữ liệu</h3>
          <p style={{ fontSize: 13, color: 'var(--ink-muted)', marginTop: 4 }}>
            Bản chụp: <code className="code-snippet">{quality.snapshot_id}</code>
          </p>
        </div>
        <Badge variant={quality.is_pristine === true ? 'success' : 'warning'}>
          {qualityStatus[quality.quality_status] ?? quality.quality_status}
        </Badge>
      </div>

      <div className="grid-cols-4" style={{ marginBottom: 16 }}>
        <StatBox label="Tỷ lệ bao phủ" value={coverageText} />
        <StatBox label="Số khoảng thiếu" value={quality.missing_intervals_count ?? 'Chưa có dữ liệu'} />
        <StatBox label="Số nến trùng" value={quality.duplicate_candles_count ?? 'Chưa có dữ liệu'} />
        <StatBox label="Danh sách khoảng thiếu" value={gapStatus[quality.gap_list_status] ?? quality.gap_list_status} />
      </div>
      <div style={{ fontSize: 12, color: 'var(--ink-muted)' }}>
        SHA-256 dùng để nhận diện nội dung bản chụp; chỉ số chất lượng chưa có dữ liệu sẽ không được suy đoán.
      </div>
    </Card>
  );
}

export function CandleTable({ candles }: { candles: CandleDTO[] }) {
  if (candles.length === 0) {
    return <EmptyState title="Chưa tải nến" message="Chọn bản chụp dữ liệu để xem trước một số nến." />;
  }

  return (
    <div className="table-responsive">
      <table className="data-table">
        <thead>
          <tr>
            <th>Thời gian (UTC)</th>
            <th>Giá mở cửa</th>
            <th>Giá cao nhất</th>
            <th>Giá thấp nhất</th>
            <th>Giá đóng cửa</th>
            <th>Khối lượng</th>
            <th>Số giao dịch</th>
          </tr>
        </thead>
        <tbody>
          {candles.slice(0, 20).map((c) => (
            <tr key={c.open_time_ms}>
              <td>{new Date(c.open_time_ms).toISOString().slice(11, 19)}</td>
              <td>${c.open.toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
              <td>${c.high.toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
              <td>${c.low.toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
              <td>${c.close.toLocaleString(undefined, { minimumFractionDigits: 2 })}</td>
              <td>{c.volume.toFixed(4)}</td>
              <td>{c.trades_count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
