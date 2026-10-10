import { NextRequest, NextResponse } from 'next/server';
import { fetchFromApi } from '@/shared/api-client';

export async function GET(
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

    const result = await fetchFromApi(`/external-analysis/jobs/${encodeURIComponent(id)}`, undefined, headers);

    if (result.error || !result.data) {
      return NextResponse.json(
        { error: result.error || 'Không tìm thấy tác vụ phân tích' },
        { status: result.status || 404 }
      );
    }

    return NextResponse.json(result.data, { status: 200 });
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : 'Lỗi truy xuất tác vụ';
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}
