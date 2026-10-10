import { NextRequest, NextResponse } from 'next/server';
import { postToApi } from '@/shared/api-client';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const result = await postToApi('/replay/jobs', body);

    if (result.error || !result.data) {
      return NextResponse.json(
        { error: result.error || 'Không thể tạo tác vụ mô phỏng' },
        { status: result.status || 500 }
      );
    }

    return NextResponse.json(result.data, { status: 201 });
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : 'Yêu cầu không hợp lệ';
    return NextResponse.json({ error: msg }, { status: 400 });
  }
}
