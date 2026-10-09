import React from 'react';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import { fetchFromApi } from '@/shared/api-client';
import { ErrorBanner } from '@/shared/ui/primitives';
import { ExperimentDetailResponse } from '@/features/research/types';
import { ExperimentDetailView } from '@/features/research/components';

interface ResearchDetailPageProps {
  params: Promise<{
    id: string;
  }>;
}

export default async function ResearchDetailPage(props: ResearchDetailPageProps) {
  const { id } = await props.params;
  const res = await fetchFromApi<ExperimentDetailResponse>(`/experiments/${id}`);

  if (res.status === 404) {
    notFound();
  }

  if (res.error || !res.data) {
    return (
      <div>
        <div style={{ marginBottom: 20 }}>
          <Link href="/research" className="nav-link">
            ← Về kết quả thử nghiệm
          </Link>
        </div>
        <ErrorBanner message={res.error || 'Không tải được chi tiết thử nghiệm'} />
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <div>
        <Link href="/research" className="nav-link" style={{ fontSize: 14 }}>
          ← Về kết quả thử nghiệm
        </Link>
      </div>
      <ExperimentDetailView detail={res.data} />
    </div>
  );
}
