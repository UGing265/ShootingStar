import React from 'react';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import { fetchFromApi } from '@/shared/api-client';
import { ErrorBanner } from '@/shared/ui/primitives';
import { SignalDetailResponse } from '@/features/signals/types';
import { SignalDetailView } from '@/features/signals/components';

interface SignalDetailPageProps {
  params: Promise<{
    id: string;
  }>;
}

export default async function SignalDetailPage(props: SignalDetailPageProps) {
  const { id } = await props.params;
  const res = await fetchFromApi<SignalDetailResponse>(`/signals/${id}`);

  if (res.status === 404) {
    notFound();
  }

  if (res.error || !res.data) {
    return (
      <div>
        <div style={{ marginBottom: 20 }}>
          <Link href="/signals" className="nav-link">
            ← Về dự đoán
          </Link>
        </div>
        <ErrorBanner message={res.error || 'Không tải được chi tiết dự đoán'} />
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <div>
        <Link href="/signals" className="nav-link" style={{ fontSize: 14 }}>
          ← Về dự đoán
        </Link>
      </div>
      <SignalDetailView detail={res.data} />
    </div>
  );
}
