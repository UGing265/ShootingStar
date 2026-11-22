import React from 'react';
import Link from 'next/link';
import { fetchForecastScoreboard, fetchFromApi } from '@/shared/api-client';
import { EmptyState, Notice, PageHeader } from '@/shared/ui/primitives';
import type { ExternalAnalysisJobDTO } from '@/features/replay/external-types';
import { ReportView } from '@/features/report/report-view';
import { RecentReportsList } from '@/features/report/recent-reports-list';

interface ReportPageProps {
  searchParams?: Promise<{ job?: string; mock?: string }>;
}

export default async function ReportPage(props: ReportPageProps) {
  const sp = props.searchParams ? await props.searchParams : undefined;
  const jobId = sp?.job;
  const mock = sp?.mock === '1';

  const adminKey = process.env.SHOOTINGSTAR_ADMIN_KEY;
  const jobRes = jobId
    ? await fetchFromApi<ExternalAnalysisJobDTO>(
        `/external-analysis/jobs/${encodeURIComponent(jobId)}`,
        undefined,
        adminKey ? { 'X-Admin-Key': adminKey } : undefined,
      )
    : null;

  const forecastJob =
    jobRes?.data?.evidence_envelope?.protocol_version === 'forecast-6h-v1' ? jobRes.data : null;
  const scoreboardRes = forecastJob
    ? await fetchForecastScoreboard(
        forecastJob.snapshot_id,
        forecastJob.horizon_minutes,
        forecastJob.evidence_envelope?.lookback_days ?? 14,
        adminKey ? { 'X-Admin-Key': adminKey } : undefined,
      )
    : null;

  return (
    <div className="page">
      <PageHeader
        title="Báo cáo"
        description="Báo cáo phân tích của các lần mô phỏng: nhận định hướng giá 6 giờ, điểm đồng thuận, so sánh với luật đơn giản và kết quả đối chiếu."
        actions={
          jobId ? (
            <Link href="/report" className="btn btn-secondary btn-sm">
              Tất cả báo cáo
            </Link>
          ) : undefined
        }
      />

      {jobId && jobRes ? (
        jobRes.data ? (
          <ReportView
            job={jobRes.data}
            mock={mock}
            scoreboard={forecastJob ? (scoreboardRes?.data ?? null) : undefined}
            scoreboardError={scoreboardRes?.error}
          />
        ) : jobRes.status === 404 ? (
          <EmptyState title="Không tìm thấy báo cáo" message="Mã báo cáo không tồn tại hoặc đã bị xóa." />
        ) : (
          <Notice variant="error" title="Không tải được báo cáo.">
            {jobRes.error}
          </Notice>
        )
      ) : (
        <RecentReportsList />
      )}
    </div>
  );
}
