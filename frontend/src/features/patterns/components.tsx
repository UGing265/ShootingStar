import React from 'react';
import Link from 'next/link';
import { Card, Badge, StatBox, EmptyState } from '@/shared/ui/primitives';
import { PatternRuleDTO, PatternHitDTO, PatternDetailResponse } from './types';

export function PatternRuleListView({ rules }: { rules: PatternRuleDTO[] }) {
  if (rules.length === 0) {
    return <EmptyState title="Chưa có quy tắc mẫu hình" message="Hệ thống chưa đăng ký quy tắc mẫu hình nến nào." />;
  }

  return (
    <div className="table-responsive">
      <table className="data-table">
        <thead>
          <tr>
            <th>Quy tắc mẫu hình</th>
            <th>Phiên bản</th>
            <th>Mô tả</th>
            <th>Ngày tạo</th>
            <th>Thao tác</th>
          </tr>
        </thead>
        <tbody>
          {rules.map((r) => (
            <tr key={r.id}>
              <td>
                <strong>{r.name}</strong>
              </td>
              <td>
                <code className="code-snippet">v{r.version}</code>
              </td>
              <td>{r.description}</td>
              <td>{r.created_at.slice(0, 19).replace('T', ' ')}</td>
              <td>
                <Link href={`/patterns/${r.id}`} className="nav-link" style={{ fontWeight: 500 }}>
                  Xem lần xuất hiện →
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function PatternDetailView({ detail }: { detail: PatternDetailResponse }) {
  const { rule, hits } = detail;
  const hitsWithOutcomes = hits.filter((h) => h.outcome_return_30m !== null);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <Card>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
          <div>
            <h2 style={{ fontSize: 24, fontWeight: 600 }}>{rule.name}</h2>
            <p style={{ fontSize: 13, color: 'var(--ink-muted)', marginTop: 4 }}>
              ID quy tắc: <code className="code-snippet">{rule.id}</code> | Phiên bản:{' '}
              <code className="code-snippet">v{rule.version}</code>
            </p>
          </div>
          <Badge variant="accent">Quy tắc phiên bản {rule.version}</Badge>
        </div>

        <p style={{ fontSize: 14, color: 'var(--ink)', marginBottom: 16 }}>{rule.description}</p>

        <div className="grid-cols-3" style={{ marginBottom: 16 }}>
          <StatBox label="Tổng số lần xuất hiện" value={hits.length} />
          <StatBox label="Số lần có kết quả sau 30 phút" value={hitsWithOutcomes.length} />
          <StatBox label="Phiên bản quy tắc" value={`v${rule.version}`} subtext="Định nghĩa theo tham số" />
        </div>

        <div style={{ background: 'var(--surface-pearl)', padding: 14, borderRadius: 10, border: '1px solid var(--hairline)', marginBottom: 16 }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--ink-muted)', marginBottom: 6 }}>
            THAM SỐ ĐỊNH NGHĨA QUY TẮC:
          </div>
          <pre style={{ fontSize: 12, fontFamily: 'var(--font-mono)', margin: 0, overflowX: 'auto' }}>
            {JSON.stringify(rule.definition, null, 2)}
          </pre>
        </div>

        <div style={{ fontSize: 12, color: 'var(--ink-muted)', background: 'var(--surface-pearl)', padding: 12, borderRadius: 8, border: '1px solid var(--hairline)' }}>
          ⚠️ <strong>Lưu ý phương pháp:</strong> Mẫu hình giá được nhận diện theo quy tắc toán học. Lợi suất sau 30 phút phản ánh diễn biến thị trường sau khi phát hiện; chưa thể suy ra tỷ lệ thắng hay lãi/lỗ nếu không có quy tắc vào lệnh độc lập.
        </div>
      </Card>

      <Card>
        <h3 style={{ fontSize: 18, fontWeight: 600, marginBottom: 16 }}>Các lần xuất hiện trong lịch sử</h3>
        {hits.length === 0 ? (
          <EmptyState title="Chưa phát hiện lần xuất hiện nào" message="Quy tắc này chưa được kích hoạt trên dữ liệu hiện có." />
        ) : (
          <div className="table-responsive">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Thời gian nến (UTC)</th>
                  <th>Cặp giao dịch / khung thời gian</th>
                  <th>Lợi suất sau 30 phút</th>
                  <th>Nhãn kết quả</th>
                  <th>Ngày tạo</th>
                </tr>
              </thead>
              <tbody>
                {hits.map((h) => (
                  <tr key={h.id}>
                    <td>{new Date(h.detected_time_ms).toISOString().replace('T', ' ').slice(0, 19)}</td>
                    <td>{h.symbol} ({h.timeframe})</td>
                    <td>
                      {h.outcome_return_30m !== null ? (
                        <span
                          style={{
                            color:
                              h.outcome_return_30m > 0
                                ? 'var(--success)'
                                : h.outcome_return_30m < 0
                                ? 'var(--error)'
                                : 'var(--ink)',
                            fontWeight: 500,
                          }}
                        >
                          {(h.outcome_return_30m * 100).toFixed(2)}%
                        </span>
                      ) : (
                        '—'
                      )}
                    </td>
                    <td>{h.outcome_label || '—'}</td>
                    <td>{h.created_at.slice(0, 19).replace('T', ' ')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
