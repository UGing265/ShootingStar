import { NextRequest, NextResponse } from 'next/server';
import { postToApi } from '@/shared/api-client';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const adminKey = process.env.SHOOTINGSTAR_ADMIN_KEY || '';
    const headers: Record<string, string> = {};
    if (adminKey) {
      headers['X-Admin-Key'] = adminKey;
    }

    const mockMode = body.mock_mode === true;
    const path = mockMode ? '/external-analysis/jobs?mock_mode=true' : '/external-analysis/jobs';

    const result = await postToApi(path, body, headers);

    if (result.error || !result.data) {
      return NextResponse.json(
        { error: result.error || 'Không thể tạo tác vụ phân tích ngoài' },
        { status: result.status || 500 }
      );
    }

    return NextResponse.json(result.data, { status: 201 });
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : 'Yêu cầu không hợp lệ';
    return NextResponse.json({ error: msg }, { status: 400 });
  }
}
