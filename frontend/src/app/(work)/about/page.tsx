'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { Card, Badge } from '@/shared/ui/primitives';

export default function AboutPage() {
  const [activeScene, setActiveScene] = useState(0);

  useEffect(() => {
    const handleScroll = () => {
      const steps = document.querySelectorAll('.scrolly-step');
      const triggerY = window.innerHeight * 0.45;
      steps.forEach((step, idx) => {
        const rect = step.getBoundingClientRect();
        if (rect.top <= triggerY && rect.bottom >= triggerY) {
          setActiveScene(idx);
        }
      });
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    handleScroll();
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  return (
    <div style={{ maxWidth: 960, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 48 }}>
      {/* Header */}
      <section style={{ textAlign: 'center', paddingTop: 20 }}>
        <div style={{ marginBottom: 12 }}>
          <Badge variant="accent">Nền Tảng Nghiên Cứu Định Lượng</Badge>
        </div>
        <h1 style={{ fontSize: 44, fontWeight: 700, letterSpacing: '-0.03em', lineHeight: 1.15, marginBottom: 16 }}>
          ShootingStar — Nghiên Cứu Dự Đoán 30 Phút
        </h1>
        <p style={{ fontSize: 18, color: 'var(--ink-muted)', lineHeight: 1.6, maxWidth: 720, margin: '0 auto' }}>
          Khát vọng tìm kiếm tín hiệu thật sự giữa thị trường crypto biến động hỗn loạn. Cam kết minh bạch phương pháp: chính xác trước, tốc độ sau, kiên quyết nói không với số liệu ảo.
        </p>
      </section>

      {/* Pinned Scrollytelling Stage */}
      <div className="scrolly-container">
        <div className="scrolly-stage">
          <svg width="600" height="280" viewBox="0 0 600 280" fill="none" xmlns="http://www.w3.org/2000/svg">
            {/* Background grid */}
            <line x1="40" y1="140" x2="560" y2="140" stroke="#252528" strokeDasharray="4 4" />
            <line x1="300" y1="20" x2="300" y2="260" stroke="#0071e3" strokeWidth="2" strokeDasharray="6 4" />
            <text x="308" y="40" fill="#2997ff" fontSize="12" fontFamily="system-ui" fontWeight="500">
              Mốc t (Nến Đóng)
            </text>

            {/* Scene 0: Thị trường biến động & Khát vọng sao băng */}
            {activeScene === 0 && (
              <g>
                {/* Volatile market waveform */}
                <path d="M 40 180 Q 90 90 140 150 T 240 120 T 300 140" stroke="#a1a1a6" strokeWidth="1.5" fill="none" />
                <path d="M 60 220 L 300 140" stroke="url(#starGrad)" strokeWidth="4" strokeLinecap="round" />
                <circle cx="300" cy="140" r="6" fill="#ffffff" />
                <circle cx="300" cy="140" r="14" stroke="#2997ff" strokeWidth="1.5" />
                <text x="50" y="245" fill="#a1a1a6" fontSize="12" fontFamily="system-ui">
                  Thị trường crypto nhiễu loạn & tin tức giật gân
                </text>
              </g>
            )}

            {/* Scene 1: Giả thuyết nghiên cứu con người */}
            {activeScene === 1 && (
              <g>
                <rect x="80" y="80" width="200" height="110" rx="10" fill="rgba(0, 102, 204, 0.15)" stroke="#0071e3" strokeWidth="1.5" />
                <text x="100" y="115" fill="#2997ff" fontSize="14" fontFamily="system-ui" fontWeight="600">
                  GIẢ THUYẾT NGHIÊN CỨU
                </text>
                <text x="100" y="145" fill="#ffffff" fontSize="12" fontFamily="system-ui">
                  • Phân tích hình thái nến (i ≤ t)
                </text>
                <text x="100" y="165" fill="#ffffff" fontSize="12" fontFamily="system-ui">
                  • Loại bỏ hoàn toàn lookahead
                </text>
              </g>
            )}

            {/* Scene 2: Xác suất mô hình & Quyết định NO_TRADE */}
            {activeScene === 2 && (
              <g>
                {/* Purge gap window */}
                <rect x="300" y="60" width="70" height="160" fill="rgba(255, 149, 0, 0.15)" stroke="#ff9500" strokeDasharray="4 2" />
                <text x="306" y="90" fill="#ff9f0a" fontSize="11" fontFamily="system-ui">
                  Purge 30m
                </text>
                {/* Clean out-of-sample forward test */}
                <rect x="390" y="80" width="180" height="110" rx="10" fill="rgba(52, 199, 89, 0.12)" stroke="#34c759" strokeWidth="1.5" />
                <text x="405" y="115" fill="#30d158" fontSize="13" fontFamily="system-ui" fontWeight="600">
                  MÔ HÌNH HIỆU CHUẨN
                </text>
                <text x="405" y="142" fill="#ffffff" fontSize="12" fontFamily="system-ui">
                  Xác suất P(UP) / P(DOWN)
                </text>
                <text x="405" y="165" fill="#ffd60a" fontSize="11" fontFamily="system-ui">
                  Bộ lọc: Quyết định NO_TRADE
                </text>
              </g>
            )}

            {/* Scene 3: Trạng thái kiểm chứng thực tế */}
            {activeScene === 3 && (
              <g>
                <rect x="150" y="60" width="300" height="160" rx="12" fill="rgba(255, 149, 0, 0.12)" stroke="#ff9500" strokeWidth="1.5" />
                <text x="190" y="105" fill="#ff9f0a" fontSize="16" fontFamily="system-ui" fontWeight="700">
                  Chưa Có Kết Quả Kiểm Chứng
                </text>
                <text x="175" y="135" fill="#a1a1a6" fontSize="12" fontFamily="system-ui">
                  Hệ thống đang chạy kiểm định hồi quy walk-forward
                </text>
                <text x="185" y="165" fill="#ffd60a" fontSize="12" fontFamily="system-ui">
                  Chi phí & P&L: GATED (Đang chờ duyệt slippage)
                </text>
                <text x="180" y="190" fill="#ffffff" fontSize="11" fontFamily="system-ui">
                  Vị thế DOWN: Đứng ngoài giữ tiền mặt (0.0% return)
                </text>
              </g>
            )}

            <defs>
              <linearGradient id="starGrad" x1="60" y1="220" x2="300" y2="140" gradientUnits="userSpaceOnUse">
                <stop stopColor="#2997ff" stopOpacity="0" />
                <stop offset="1" stopColor="#ffffff" />
              </linearGradient>
            </defs>
          </svg>
        </div>

        {/* Narrative Steps */}
        <div className="scrolly-scenes">
          <div className="scrolly-step">
            <div className="scrolly-card">
              <div className="scrolly-step-tag">Cảnh 1 — Khát Vọng & Bối Cảnh</div>
              <h2 className="scrolly-step-title">Khát vọng ShootingStar</h2>
              <p className="scrolly-step-text">
                Giống như sao băng rạch ngang bầu trời đêm, cơ hội trong crypto xuất hiện chớp nhoáng giữa hàng ngàn biến động và tin tức giật gân. Nhưng thay vì lao vào những lời hứa hão huyền "90% win rate", ShootingStar chọn con đường khoa học: đo lường thực nghiệm hướng đi 30 phút của Bitcoin với sự trung thực tối đa.
              </p>
            </div>
          </div>

          <div className="scrolly-step">
            <div className="scrolly-card">
              <div className="scrolly-step-tag">Cảnh 2 — Giả Thuyết</div>
              <h2 className="scrolly-step-title">Giả thuyết nghiên cứu con người</h2>
              <p className="scrolly-step-text">
                Chúng tôi không giao toàn bộ quyền quyết định cho "hộp đen". Nghiên cứu bắt đầu từ các giả thuyết hình thái nến có thể diễn giải được, kết hợp các đặc trưng động lượng. Mọi đặc trưng tại thời điểm <code>t</code> chỉ được phép sử dụng dữ liệu đã thực sự có sẵn trước khi nến đóng, tuyệt đối không nhìn trước tương lai.
              </p>
            </div>
          </div>

          <div className="scrolly-step">
            <div className="scrolly-card">
              <div className="scrolly-step-tag">Cảnh 3 — Triết Lý &amp; Quyết Định</div>
              <h2 className="scrolly-step-title">Xác suất mô hình &amp; Ngưỡng giao dịch</h2>
              <p className="scrolly-step-text">
                Chính xác quan trọng hơn tốc độ. Điểm số từ mô hình được hiệu chuẩn xác suất (Platt calibration) để phản ánh đúng tần suất thắng thực tế. Chính sách hành động tự động dựa trên chi phí (<strong>NO_TRADE</strong> theo slippage) chưa hoạt động — đây là mục tiêu phát triển tương lai, chưa được thẩm định.
              </p>
            </div>
          </div>

          <div className="scrolly-step">
            <div className="scrolly-card">
              <div className="scrolly-step-tag">Cảnh 4 — Minh Bạch Hiện Trạng</div>
              <h2 className="scrolly-step-title">Bằng chứng thực nghiệm & Giới hạn</h2>
              <p className="scrolly-step-text">
                Hiện tại nền tảng đang trong quá trình thực nghiệm walk-forward; <strong>chưa có kết quả kiểm chứng độc lập</strong> được phê duyệt cho production. Tất cả chỉ số P&L ròng bị khóa (GATED) cho đến khi mô hình trượt giá sổ lệnh thực tế được thẩm định. Không có số liệu bịa đặt, không có cam kết lợi nhuận.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Action Footer */}
      <section style={{ textAlign: 'center', padding: '24px 0 60px 0' }}>
        <Link href="/dashboard" className="btn-action" style={{ padding: '14px 28px', fontSize: 16 }}>
          Truy cập Dashboard →
        </Link>
      </section>
    </div>
  );
}
