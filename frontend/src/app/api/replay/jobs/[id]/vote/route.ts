import { NextRequest, NextResponse } from 'next/server';
import { postToApi } from '@/shared/api-client';

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const body = await request.json();
    const result = await postToApi(`/replay/jobs/${id}/vote`, body);

    if (result.error || !result.data) {
      return NextResponse.json(
        { error: result.error || 'Không thể ghi nhận dự đoán' },
        { status: result.status || 400 }
      );
    }

    return NextResponse.json(result.data, { status: 200 });
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : 'Yêu cầu không hợp lệ';
    return NextResponse.json({ error: msg }, { status: 400 });
  }
}
