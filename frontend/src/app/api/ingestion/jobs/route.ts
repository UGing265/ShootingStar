import { NextRequest, NextResponse } from 'next/server';
import { fetchFromApi, postToApi } from '@/shared/api-client';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const result = await postToApi('/ingestion/jobs', body);

    if (result.error || !result.data) {
      return NextResponse.json(
        { error: result.error || 'Failed to trigger ingestion job' },
        { status: result.status || 500 }
      );
    }

    return NextResponse.json(result.data, { status: 202 });
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : 'Invalid request payload';
    return NextResponse.json({ error: msg }, { status: 400 });
  }
}

export async function GET() {
  const result = await fetchFromApi('/ingestion/jobs', { limit: 20 });

  if (result.error || !result.data) {
    return NextResponse.json(
      { error: result.error || 'Failed to list ingestion jobs' },
      { status: result.status || 500 }
    );
  }

  return NextResponse.json(result.data);
}
