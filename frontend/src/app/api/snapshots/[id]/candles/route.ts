import { NextRequest, NextResponse } from 'next/server';
import { fetchFromApi } from '@/shared/api-client';
import { CandleDTO } from '@/features/data/types';

interface RouteContext {
  params: Promise<{ id: string }>;
}

export async function GET(request: NextRequest, context: RouteContext) {
  const { id } = await context.params;
  const searchParams = request.nextUrl.searchParams;
  const startMs = searchParams.get('start_ms');
  const endMs = searchParams.get('end_ms');
  const limitParam = searchParams.get('limit') || '500';

  const result = await fetchFromApi<CandleDTO[]>(`/snapshots/${id}/candles`, {
    start_ms: startMs ? Number(startMs) : undefined,
    end_ms: endMs ? Number(endMs) : undefined,
    limit: Number(limitParam),
  });

  if (result.error || !result.data) {
    return NextResponse.json(
      { error: result.error || 'Failed to fetch candles' },
      { status: result.status || 500 }
    );
  }

  return NextResponse.json(result.data);
}
