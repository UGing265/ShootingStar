import React from 'react';
import Link from 'next/link';
import { Card, Badge, StatBox, EmptyState } from '@/shared/ui/primitives';
import { ExperimentSummary, ExperimentDetailResponse, CalibrationBinDTO } from './types';

export function ExperimentListView({ experiments }: { experiments: ExperimentSummary[] }) {
  if (experiments.length === 0) {
    return <EmptyState title="Chưa có thử nghiệm" message="Chưa thực hiện thử nghiệm nghiên cứu nào theo phương pháp kiểm định cuốn chiếu." />;
  }

  return (
    <div className="table-responsive">
      <table className="data-table">
        <thead>
          <tr>
            <th>Tên thử nghiệm</th>
            <th>Cặp giao dịch / khung thời gian</th>
            <th>Mã băm cấu hình</th>
            <th>Ngày tạo (UTC)</th>
            <th>Thao tác</th>
          </tr>
        </thead>
        <tbody>
          {experiments.map((e) => {
            const symbol = typeof e.parameters?.symbol === 'string' ? e.parameters.symbol : 'BTCUSDT';
            const timeframe = typeof e.parameters?.timeframe === 'string' ? e.parameters.timeframe : '5m';
            return (
              <tr key={e.id}>
                <td>
                  <strong>{e.name}</strong>
                </td>
                <td>
                  {symbol} ({timeframe})
                </td>
                <td>
                  <code className="code-snippet">{e.config_hash.slice(0, 10)}…</code>
                </td>
                <td>{e.created_at.slice(0, 19).replace('T', ' ')}</td>
                <td>
                  <Link href={`/research/${e.id}`} className="nav-link" style={{ fontWeight: 500 }}>
                    Xem báo cáo →
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

export function ExperimentDetailView({ detail }: { detail: ExperimentDetailResponse }) {
  const { name, config_hash, snapshot_id, snapshot_sha256, parameters, splits, reports, artifacts } = detail;
  const primaryReport = reports[0];
  const metrics = primaryReport?.metrics || {};
  const timeframe = typeof parameters?.timeframe === 'string' ? parameters.timeframe : '5m';

  const calibBins: CalibrationBinDTO[] = primaryReport?.calibration?.bins ?? [];
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <Card>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
          <div>
            <h2 style={{ fontSize: 24, fontWeight: 600 }}>{name}</h2>
            <p style={{ fontSize: 13, color: 'var(--ink-muted)', marginTop: 4 }}>
              Mã băm cấu hình: <code className="code-snippet">{config_hash.slice(0, 12)}…</code> | Bản chụp:{' '}
              <code className="code-snippet">{snapshot_id}</code>
              {snapshot_sha256 && ` (${snapshot_sha256.slice(0, 10)}…)`}
            </p>
          </div>
          <Badge variant="accent">{timeframe} • Dự đoán sau 30 phút</Badge>
        </div>

        <div className="grid-cols-4">
          <StatBox
            label="Độ chính xác ngoài mẫu"
            value={typeof metrics.accuracy === 'number' ? `${(metrics.accuracy * 100).toFixed(2)}%` : 'Chưa có dữ liệu'}
          />
          <StatBox
            label="Điểm Brier"
            value={typeof metrics.brier_score === 'number' ? metrics.brier_score.toFixed(4) : 'Chưa có dữ liệu'}
            subtext="Càng thấp càng tốt"
          />
          <StatBox
            label="Lợi suất spot thực tế"
            value={
              typeof metrics.spot_cumulative_return === 'number'
                ? `${(metrics.spot_cumulative_return * 100).toFixed(2)}%`
                : 'Chưa có dữ liệu'
            }
          />
          <StatBox
            label="Độ trễ giả định"
            value={typeof metrics.assumed_latency_ms === 'number' ? `${metrics.assumed_latency_ms} ms` : 'Chưa có dữ liệu'}
            subtext="Giới hạn thời điểm ra quyết định"
          />
        </div>
      </Card>

      <Card>
        <h3 style={{ fontSize: 18, fontWeight: 600, marginBottom: 16 }}>Các lượt kiểm định cuốn chiếu và khoảng cách loại trừ</h3>
        <table className="data-table">
          <thead>
            <tr>
              <th>Loại tập dữ liệu</th>
              <th>Số mẫu</th>
              <th>Khoảng thời gian (UTC)</th>
              <th>Khoảng cách loại trừ</th>
            </tr>
          </thead>
          <tbody>
            {splits.map((s) => (
              <tr key={s.id}>
                <td>
                  <strong>{s.split_type}</strong>
                </td>
                <td>{s.sample_count}</td>
                <td>
                  {new Date(s.start_time_ms).toISOString().slice(0, 16).replace('T', ' ')} →{' '}
                  {new Date(s.end_time_ms).toISOString().slice(0, 16).replace('T', ' ')}
                </td>
                <td>
                  <Badge variant="neutral">Kiểm tra cấu hình chia tập</Badge>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      <Card>
        <h3 style={{ fontSize: 18, fontWeight: 600, marginBottom: 8 }}>
          Các mô hình đối chứng (đánh giá trên cùng tập kiểm thử)
        </h3>
        <p style={{ fontSize: 13, color: 'var(--ink-muted)', marginBottom: 16 }}>
          So sánh các đối chứng theo số liệu báo cáo; lớp đa số được xác định từ tập huấn luyện.
        </p>
        <table className="data-table">
          <thead>
            <tr>
              <th>Mô hình / đối chứng</th>
              <th>Độ chính xác trên tập kiểm thử</th>
              <th>Lợi suất spot tích lũy</th>
              <th>Vai trò</th>
            </tr>
          </thead>
          <tbody>
            <tr style={{ background: 'var(--surface-pearl)' }}>
              <td>
                <strong>Mô hình ML hiệu chỉnh xác suất (ứng viên)</strong>
              </td>
              <td>{typeof metrics.accuracy === 'number' ? `${(metrics.accuracy * 100).toFixed(2)}%` : 'Chưa có dữ liệu'}</td>
              <td>
                {typeof metrics.spot_cumulative_return === 'number'
                  ? `${(metrics.spot_cumulative_return * 100).toFixed(2)}%`
                  : 'Chưa có dữ liệu'}
              </td>
              <td>
                <Badge variant="accent">Ứng viên</Badge>
              </td>
            </tr>
            <tr>
              <td>Lớp đa số (xác định từ y_train)</td>
              <td>
                {typeof metrics.majority_class_accuracy === 'number'
                  ? `${(metrics.majority_class_accuracy * 100).toFixed(2)}%`
                  : 'Chưa có dữ liệu'}
              </td>
              <td>0.00%</td>
              <td>
                <Badge variant="neutral">Đối chứng</Badge>
              </td>
            </tr>
            <tr>
              <td>Luôn dự đoán UP (mua không điều kiện)</td>
              <td>
                {typeof metrics.always_up_accuracy === 'number'
                  ? `${(metrics.always_up_accuracy * 100).toFixed(2)}%`
                  : 'Chưa có dữ liệu'}
              </td>
              <td>—</td>
              <td>
                <Badge variant="neutral">Đối chứng</Badge>
              </td>
            </tr>
            <tr>
              <td>Động lượng đơn giản</td>
              <td>
                {typeof metrics.momentum_accuracy === 'number'
                  ? `${(metrics.momentum_accuracy * 100).toFixed(2)}%`
                  : 'Chưa có dữ liệu'}
              </td>
              <td>—</td>
              <td>
                <Badge variant="neutral">Đối chứng</Badge>
              </td>
            </tr>
          </tbody>
        </table>
      </Card>

      {calibBins.length > 0 && (
        <Card>
          <h3 style={{ fontSize: 18, fontWeight: 600, marginBottom: 16 }}>Các nhóm hiệu chỉnh xác suất</h3>
          <table className="data-table">
            <thead>
              <tr>
                <th>Khoảng xác suất</th>
                <th>Số mẫu</th>
                <th>Xác suất dự đoán trung bình</th>
                <th>Tần suất thực tế</th>
              </tr>
            </thead>
            <tbody>
              {calibBins.map((b) => (
                <tr key={b.bin_index}>
                  <td>{b.bin_range}</td>
                  <td>{b.sample_count}</td>
                  <td>{(b.mean_predicted_prob * 100).toFixed(1)}%</td>
                  <td>{(b.empirical_frequency * 100).toFixed(1)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      {artifacts.length > 0 && (
        <Card>
          <h3 style={{ fontSize: 18, fontWeight: 600, marginBottom: 16 }}>Nguồn gốc mô hình và tệp kết quả</h3>
          {artifacts.map((a) => (
            <div key={a.id} style={{ fontSize: 13, marginBottom: 12 }}>
              <div>
                <strong>Loại:</strong> {a.model_type}
              </div>
              <div>
                <strong>SHA-256 tệp:</strong> <code className="code-snippet">{a.artifact_hash}</code>
              </div>
              <div style={{ color: 'var(--ink-muted)', marginTop: 4 }}>
                Ngày tạo: {a.created_at.slice(0, 19).replace('T', ' ')}
              </div>
            </div>
          ))}
        </Card>
      )}
    </div>
  );
}
