'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { Badge, Card, EmptyState } from '@/shared/ui/primitives';
import { formatDateTime, formatUsd } from '@/shared/format';
import { loadRecentReports, reportHref, type RecentReport } from './recent-reports';

export function RecentReportsList() {
  const [reports, setReports] = useState<RecentReport[] | null>(null);

  useEffect(() => {
    setReports(loadRecentReports());
  }, []);

  return (
    <Card>
      <h2 className="card-title">Báo cáo đã tạo trên máy này</h2>
      {reports === null ? (
        <p className="card-sub" style={{ marginTop: 8 }}>
          Đang tải…
        </p>
      ) : reports.length === 0 ? (
        <EmptyState
          message="Chưa có báo cáo nào. Chạy một mô phỏng với phân tích Gemini để tạo báo cáo."
          actionLabel="Đến trang Mô phỏng"
          actionHref="/replay"
        />
      ) : (
        <div className="table-wrap" style={{ marginTop: 8 }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Thời điểm dự báo (UTC+7)</th>
                <th>Cặp giao dịch</th>
                <th>Giá tại thời điểm</th>
                <th>Tạo lúc</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {reports.map((r) => (
                <tr key={r.id}>
                  <td>{formatDateTime(r.predictionTimeMs)}</td>
                  <td>
                    {r.symbol} · {r.timeframe}
                  </td>
                  <td>{formatUsd(r.purchasePrice)}</td>
                  <td>{formatDateTime(r.savedAtMs)}</td>
                  <td>
                    <Link href={reportHref(r.id, r.mock === true)}>Mở</Link>
                    {r.mock && <Badge variant="warning">DỮ LIỆU GIẢ LẬP</Badge>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
