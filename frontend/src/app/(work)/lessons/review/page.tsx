import React from 'react';
import { fetchFromApi } from '@/shared/api-client';
import { ApprovedLessonItem, AdminLessonItem } from '@/features/lessons/types';
import { LessonReviewComponent } from '@/features/lessons/lesson-review';

export const metadata = {
  title: 'Thư viện Bài học Trading | ShootingStar',
};

export default async function LessonReviewPage() {
  // Fetch strictly public approved lessons catalog
  const result = await fetchFromApi<ApprovedLessonItem[]>('/lessons');
  const approvedList: ApprovedLessonItem[] = result.data || [];

  const lessons: AdminLessonItem[] = approvedList.map((l) => ({
    id: l.id,
    title: l.title,
    source_name: l.source_name,
    source_url: l.source_url,
    status: 'APPROVED',
    current_revision: {
      id: l.revision_id,
      revision_number: l.revision_number,
      short_definition: l.short_definition,
      caveats: l.caveats,
      created_at: new Date().toISOString(),
    },
    review_events: [],
  }));

  return (
    <div className="max-w-5xl mx-auto py-8 px-4 space-y-6">
      <div className="p-4 text-xs text-[#525252] bg-[#fafafa] border border-[#e5e5e5] rounded">
        <strong>Chế độ xem:</strong> Trang đang hiển thị danh mục bài học đã được phê duyệt từ API công khai (<code className="text-[#0969da]">/lessons</code>).
        Khu vực thẩm định bài mới (Admin Review Workbench) đang được khóa an toàn (Fail-closed) cho đến khi tích hợp xác thực phiên quản trị máy chủ.
      </div>
      <LessonReviewComponent initialLessons={lessons} />
    </div>
  );
}
