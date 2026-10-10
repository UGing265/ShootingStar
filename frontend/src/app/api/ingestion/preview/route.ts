import { NextRequest, NextResponse } from 'next/server';
import { postToApi } from '@/shared/api-client';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const result = await postToApi('/ingestion/preview', body);

    if (result.error || !result.data) {
      return NextResponse.json(
        { error: result.error || 'Failed to fetch ingestion preview' },
        { status: result.status || 500 }
      );
    }

    return NextResponse.json(result.data, { status: 200 });
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : 'Invalid request payload';
    return NextResponse.json({ error: msg }, { status: 400 });
  }
}
