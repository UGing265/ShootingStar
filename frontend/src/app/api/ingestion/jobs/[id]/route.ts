import { NextRequest, NextResponse } from 'next/server';
import { fetchFromApi } from '@/shared/api-client';

interface RouteContext {
  params: Promise<{ id: string }>;
}

export async function GET(_request: NextRequest, context: RouteContext) {
  const { id } = await context.params;
  const result = await fetchFromApi(`/ingestion/jobs/${id}`);

  if (result.error || !result.data) {
    return NextResponse.json(
      { error: result.error || 'Failed to fetch ingestion job' },
      { status: result.status || 500 }
    );
  }

  return NextResponse.json(result.data);
}
