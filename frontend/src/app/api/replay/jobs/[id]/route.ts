import { NextRequest, NextResponse } from 'next/server';
import { fetchFromApi } from '@/shared/api-client';

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const result = await fetchFromApi(`/replay/jobs/${id}`);

    if (result.error || !result.data) {
      return NextResponse.json(
        { error: result.error || 'Không tìm thấy tác vụ mô phỏng' },
        { status: result.status || 404 }
      );
    }

    return NextResponse.json(result.data, { status: 200 });
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : 'Yêu cầu không hợp lệ';
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}
