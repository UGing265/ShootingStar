'use client';

import React, { useState } from 'react';
import { AdminLessonItem } from './types';

interface LessonReviewProps {
  initialLessons: AdminLessonItem[];
}

export function LessonReviewComponent({ initialLessons }: LessonReviewProps) {
  const [lessons] = useState<AdminLessonItem[]>(initialLessons);
  const [activeTab, setActiveTab] = useState<'PENDING' | 'APPROVED' | 'REJECTED'>('PENDING');

  const filteredLessons = lessons.filter((l) => l.status === activeTab);

  const formatUtc7 = (isoStr: string) => {
    try {
      const d = new Date(isoStr);
      return new Intl.DateTimeFormat('vi-VN', {
        timeZone: 'Asia/Ho_Chi_Minh',
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      }).format(d);
    } catch {
      return isoStr;
    }
  };

  return (
    <div className="space-y-6">
      {/* Header and Guidelines */}
      <div className="border-b border-[#e5e5e5] pb-4">
        <h1 className="text-xl font-bold tracking-tight text-[#171717]">Thư viện Bài học & Mẫu hình Trading</h1>
        <p className="mt-1 text-sm text-[#737373]">
          Mọi bài học phải được kiểm tra nguồn gốc URL trước khi duyệt. Chỉ bài học có trạng thái{' '}
          <span className="font-semibold text-emerald-700">APPROVED</span> mới được đưa vào context phân tích của AI.
        </p>
      </div>

      {/* Security / Admin Notice */}
      <div className="p-3.5 text-xs text-[#525252] bg-[#fcfcfc] border border-[#e5e5e5] rounded flex items-start space-x-2">
        <span className="font-semibold text-[#0969da] uppercase tracking-wider text-[11px] mt-0.5">Quy chuẩn bảo mật:</span>
        <p>
          Thao tác duyệt / từ chối bài học từ giao diện web được khóa an toàn (Fail-closed) để tránh lộ mã bí mật trình duyệt.
          Người vận hành thực hiện phê duyệt thông qua script hoặc CLI quản trị có xác thực máy chủ.
        </p>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-[#e5e5e5] space-x-6 text-sm">
        {(['PENDING', 'APPROVED', 'REJECTED'] as const).map((tab) => {
          const count = lessons.filter((l) => l.status === tab).length;
          const label = tab === 'PENDING' ? 'Chờ duyệt' : tab === 'APPROVED' ? 'Đã duyệt' : 'Từ chối';
          const isActive = activeTab === tab;
          return (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`pb-3 font-medium transition-colors border-b-2 -mb-[2px] ${
                isActive
                  ? 'border-[#0969da] text-[#0969da]'
                  : 'border-transparent text-[#737373] hover:text-[#171717]'
              }`}
            >
              {label} <span className="ml-1 text-xs px-1.5 py-0.5 rounded-full bg-[#f5f5f5] text-[#525252]">{count}</span>
            </button>
          );
        })}
      </div>

      {/* Lesson List */}
      <div className="space-y-4">
        {filteredLessons.length === 0 ? (
          <div className="py-12 text-center text-sm text-[#737373] bg-[#fafafa] border border-dashed border-[#e5e5e5] rounded-md">
            Chưa có bài học nào trong danh mục này.
          </div>
        ) : (
          filteredLessons.map((lesson) => {
            const rev = lesson.current_revision;

            return (
              <div
                key={lesson.id}
                className="p-5 bg-white border border-[#e5e5e5] rounded-md transition-shadow hover:border-[#d4d4d4]"
              >
                {/* Header */}
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="text-base font-semibold text-[#171717]">{lesson.title}</h3>
                    <div className="mt-1 flex items-center space-x-3 text-xs text-[#737373]">
                      <span>Mã: <code className="text-[#0969da] bg-[#f0f7ff] px-1 py-0.5 rounded">{lesson.id}</code></span>
                      <span>Nguồn: <strong>{lesson.source_name}</strong></span>
                      <a
                        href={lesson.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-[#0969da] hover:underline flex items-center"
                      >
                        Xem bài gốc &rarr;
                      </a>
                    </div>
                  </div>
                  <div className="flex items-center space-x-2">
                    <span className="text-xs px-2 py-0.5 rounded font-mono font-medium bg-[#f5f5f5] text-[#525252]">
                      Rev #{rev?.revision_number || 1}
                    </span>
                    <span
                      className={`text-xs px-2 py-0.5 rounded font-medium ${
                        lesson.status === 'APPROVED'
                          ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                          : lesson.status === 'REJECTED'
                          ? 'bg-rose-50 text-rose-700 border border-rose-200'
                          : 'bg-amber-50 text-amber-700 border border-amber-200'
                      }`}
                    >
                      {lesson.status}
                    </span>
                  </div>
                </div>

                {/* Content */}
                <div className="mt-4 space-y-2 text-sm text-[#383838]">
                  <div className="p-3 bg-[#fcfcfc] border border-[#f0f0f0] rounded">
                    <span className="font-semibold text-xs text-[#737373] block mb-1">ĐỊNH NGHĨA RÚT GỌN:</span>
                    <p>{rev?.short_definition || 'Chưa có định nghĩa.'}</p>
                  </div>

                  <div className="p-3 bg-[#fff9f5] border border-[#ffe8d9] rounded text-[#9a3412]">
                    <span className="font-semibold text-xs text-[#c2410c] block mb-1">CAVEATS / LƯU Ý RỦI RO:</span>
                    <p>{rev?.caveats || 'Chưa có caveat.'}</p>
                  </div>

                  {rev?.source_snippet && (
                    <div className="text-xs text-[#737373] italic">
                      Trích dẫn: &ldquo;{rev.source_snippet}&rdquo;
                    </div>
                  )}
                </div>

                {/* Audit Footer */}
                <div className="mt-4 pt-3 border-t border-[#f0f0f0] flex items-center justify-between text-xs text-[#737373]">
                  <div>
                    {lesson.review_events && lesson.review_events.length > 0 ? (
                      <span>
                        Hoạt động gần nhất: <strong>{lesson.review_events[0].action}</strong> bởi{' '}
                        {lesson.review_events[0].reviewer} vào {formatUtc7(lesson.review_events[0].created_at)}
                      </span>
                    ) : (
                      <span>Khởi tạo: {lesson.created_at ? formatUtc7(lesson.created_at) : 'Mới cập nhật'}</span>
                    )}
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
