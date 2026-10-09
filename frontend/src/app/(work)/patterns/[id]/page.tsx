import React from 'react';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import { fetchFromApi } from '@/shared/api-client';
import { ErrorBanner } from '@/shared/ui/primitives';
import { PatternRuleDTO, PatternHitDTO } from '@/features/patterns/types';
import { PatternDetailView } from '@/features/patterns/components';

interface PatternDetailPageProps {
  params: Promise<{
    id: string;
  }>;
}

export default async function PatternDetailPage(props: PatternDetailPageProps) {
  const { id } = await props.params;
  const [ruleRes, hitsRes] = await Promise.all([
    fetchFromApi<PatternRuleDTO>(`/pattern-rules/${id}`),
    fetchFromApi<PatternHitDTO[]>(`/pattern-rules/${id}/hits`),
  ]);

  if (ruleRes.status === 404) {
    notFound();
  }

  if (ruleRes.error || !ruleRes.data) {
    return (
      <div>
        <div style={{ marginBottom: 20 }}>
          <Link href="/patterns" className="nav-link">
            ← Về mẫu hình giá
          </Link>
        </div>
        <ErrorBanner message={ruleRes.error || 'Không tải được chi tiết quy tắc mẫu hình'} />
      </div>
    );
  }

  const detail = {
    rule: ruleRes.data,
    hits: hitsRes.data || [],
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <div>
        <Link href="/patterns" className="nav-link" style={{ fontSize: 14 }}>
          ← Về mẫu hình giá
        </Link>
      </div>
      {hitsRes.error && (
        <ErrorBanner message={`Không tải được các lần xuất hiện của mẫu hình: ${hitsRes.error}`} />
      )}
      <PatternDetailView detail={detail} />
    </div>
  );
}
