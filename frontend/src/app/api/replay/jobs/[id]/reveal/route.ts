import { NextRequest, NextResponse } from 'next/server';
import { postToApi } from '@/shared/api-client';

export async function POST(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const result = await postToApi(`/replay/jobs/${id}/reveal`, {});

    if (result.error || !result.data) {
      return NextResponse.json(
        { error: result.error || 'Không thể xem kết quả thực tế' },
        { status: result.status || 400 }
      );
    }

    return NextResponse.json(result.data, { status: 200 });
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : 'Yêu cầu không hợp lệ';
    return NextResponse.json({ error: msg }, { status: 400 });
  }
}
