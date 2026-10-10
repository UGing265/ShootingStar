import { NextRequest, NextResponse } from 'next/server';
import { postToApi } from '@/shared/api-client';

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const adminKey = process.env.SHOOTINGSTAR_ADMIN_KEY || '';
    const headers: Record<string, string> = {};
    if (adminKey) {
      headers['X-Admin-Key'] = adminKey;
    }

    const result = await postToApi(`/external-analysis/jobs/${encodeURIComponent(id)}/reveal`, {}, headers);

    if (result.error || !result.data) {
      return NextResponse.json(
        { error: result.error || 'Không thể xem kết quả thực tế' },
        { status: result.status || 500 }
      );
    }

    return NextResponse.json(result.data, { status: 200 });
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : 'Yêu cầu không hợp lệ';
    return NextResponse.json({ error: msg }, { status: 400 });
  }
}
