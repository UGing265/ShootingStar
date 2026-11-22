'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { Badge } from '@/shared/ui/primitives';
import './about.css';

const SCENES = [
  {
    tag: 'Cảnh 1: Khát vọng & bối cảnh',
    title: 'Khát vọng ShootingStar',
    text: 'Giống như sao băng rạch ngang bầu trời đêm, cơ hội trong crypto xuất hiện chớp nhoáng giữa hàng ngàn biến động và tin tức giật gân. Thay vì hứa hẹn “90% thắng”, ShootingStar chọn con đường nghiên cứu: quay lại quá khứ, đo hướng đi 30 phút của Bitcoin một cách trung thực.',
  },
  {
    tag: 'Cảnh 2: Không nhìn trước tương lai',
    title: 'Chỉ dùng nến đã đóng',
    text: 'Bạn chọn một thời điểm t trong lịch sử. Mọi phân tích tại thời điểm đó, kể cả báo cáo 6 giờ nến, chỉ được dùng dữ liệu đã có trước t. Các nến sau t bị ẩn cho tới khi bạn đã chốt dự đoán.',
  },
  {
    tag: 'Cảnh 3: Vùng vào lệnh & chi phí',
    title: 'Vùng vào lệnh, chốt lời, cắt lỗ',
    text: 'Chiến thuật vào lệnh 30 phút đề xuất vùng vào lệnh, mức chốt lời và cắt lỗ từ hỗ trợ và kháng cự gần nhất. Kết quả vào lệnh thử luôn trừ phí giao dịch và trượt giá, không giả định phí bằng 0.',
  },
  {
    tag: 'Cảnh 4: Minh bạch hiện trạng',
    title: 'Giới hạn hiện tại',
    text: 'Mỗi lần mô phỏng chỉ là một mẫu; vài kết quả đúng chưa chứng minh phương pháp hiệu quả. Báo cáo do Gemini viết có thể đã “biết” diễn biến sau mốc lịch sử. Không có số liệu bịa đặt, không có cam kết lợi nhuận.',
  },
];

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
    <div className="page">
      <div className="about-wrap">
        <section className="about-hero">
          <div className="about-hero-badge">
            <Badge variant="accent">Công cụ nghiên cứu hướng giá</Badge>
          </div>
          <h1 className="about-hero-title">ShootingStar: Nghiên cứu dự đoán 30 phút</h1>
          <p className="about-hero-lead">
            Thử dự đoán hướng giá BTC/USDT trên lịch sử rồi đối chiếu với diễn biến thật. Phương pháp minh bạch: chính xác
            trước, tốc độ sau, nói không với số liệu ảo.
          </p>
        </section>

        <div className="scrolly-container">
          <div className="scrolly-stage" role="img" aria-label="Minh họa các cảnh giới thiệu">
            <svg width="600" height="280" viewBox="0 0 600 280" fill="none" xmlns="http://www.w3.org/2000/svg">
              <line x1="40" y1="140" x2="560" y2="140" stroke="#252528" strokeDasharray="4 4" />
              <line x1="300" y1="20" x2="300" y2="260" stroke="#0071e3" strokeWidth="2" strokeDasharray="6 4" />
              <text x="308" y="40" fill="#2997ff" fontSize="12" fontFamily="system-ui" fontWeight="500">
                Thời điểm t (nến đã đóng)
              </text>

              {activeScene === 0 && (
                <g>
                  <path d="M 40 180 Q 90 90 140 150 T 240 120 T 300 140" stroke="#a1a1a6" strokeWidth="1.5" fill="none" />
                  <path d="M 60 220 L 300 140" stroke="#2997ff" strokeWidth="3" strokeLinecap="round" />
                  <circle cx="300" cy="140" r="6" fill="#ffffff" />
                  <circle cx="300" cy="140" r="14" stroke="#2997ff" strokeWidth="1.5" />
                  <text x="50" y="245" fill="#a1a1a6" fontSize="12" fontFamily="system-ui">
                    Thị trường nhiễu loạn và tin tức giật gân
                  </text>
                </g>
              )}

              {activeScene === 1 && (
                <g>
                  <rect x="80" y="80" width="200" height="110" rx="10" fill="rgba(0, 102, 204, 0.15)" stroke="#0071e3" strokeWidth="1.5" />
                  <text x="100" y="115" fill="#2997ff" fontSize="14" fontFamily="system-ui" fontWeight="600">
                    6 GIỜ NẾN TRƯỚC t
                  </text>
                  <text x="100" y="145" fill="#ffffff" fontSize="12" fontFamily="system-ui">
                    • Chỉ nến đã đóng
                  </text>
                  <text x="100" y="165" fill="#ffffff" fontSize="12" fontFamily="system-ui">
                    • Không nhìn trước tương lai
                  </text>
                  <rect x="300" y="60" width="260" height="160" fill="#1c1c1e" stroke="#3a3a3c" strokeDasharray="4 4" />
                  <text x="350" y="146" fill="#a1a1a6" fontSize="12" fontFamily="system-ui">
                    Vùng tương lai được ẩn
                  </text>
                </g>
              )}

              {activeScene === 2 && (
                <g>
                  <rect x="330" y="95" width="230" height="50" fill="rgba(0, 102, 204, 0.18)" stroke="#2997ff" strokeWidth="1" />
                  <text x="340" y="114" fill="#2997ff" fontSize="12" fontFamily="system-ui" fontWeight="600">
                    Vùng vào lệnh
                  </text>
                  <line x1="300" y1="60" x2="560" y2="60" stroke="#30d158" strokeDasharray="5 3" />
                  <text x="340" y="52" fill="#30d158" fontSize="12" fontFamily="system-ui">
                    Chốt lời
                  </text>
                  <line x1="300" y1="190" x2="560" y2="190" stroke="#ff453a" strokeDasharray="5 3" />
                  <text x="340" y="208" fill="#ff453a" fontSize="12" fontFamily="system-ui">
                    Cắt lỗ
                  </text>
                  <text x="60" y="140" fill="#a1a1a6" fontSize="12" fontFamily="system-ui">
                    Đã trừ phí và trượt giá
                  </text>
                </g>
              )}

              {activeScene === 3 && (
                <g>
                  <rect x="150" y="60" width="300" height="160" rx="12" fill="rgba(255, 149, 0, 0.12)" stroke="#ff9500" strokeWidth="1.5" />
                  <text x="190" y="115" fill="#ff9f0a" fontSize="16" fontFamily="system-ui" fontWeight="700">
                    Mỗi lần chỉ là một mẫu
                  </text>
                  <text x="185" y="148" fill="#a1a1a6" fontSize="12" fontFamily="system-ui">
                    Chưa có kết luận hiệu quả nào được kiểm chứng
                  </text>
                  <text x="185" y="172" fill="#ffffff" fontSize="12" fontFamily="system-ui">
                    Không có lời hứa lợi nhuận
                  </text>
                </g>
              )}
            </svg>
          </div>

          <div className="scrolly-scenes">
            {SCENES.map((scene) => (
              <div className="scrolly-step" key={scene.tag}>
                <div className="scrolly-card">
                  <div className="scrolly-step-tag">{scene.tag}</div>
                  <h2 className="scrolly-step-title">{scene.title}</h2>
                  <p className="scrolly-step-text">{scene.text}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        <section className="about-footer">
          <Link href="/replay" className="btn-action">
            Bắt đầu mô phỏng →
          </Link>
        </section>
      </div>
    </div>
  );
}
