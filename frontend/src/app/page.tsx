import React from 'react';
import Link from 'next/link';

import { HeroSequence } from '@/features/landing/hero-sequence';

export default function LandingPage() {
  return (
    <div className="landing-root">
      {/* ─── Landing Header ─── */}
      <header className="landing-header">
        <div className="landing-nav-container">
          <span className="landing-brand">
            <span className="landing-brand-icon">✦</span>
            <span className="landing-brand-name">ShootingStar</span>
          </span>
          <Link href="/dashboard" className="landing-nav-cta">
            Vào dashboard demo
            <span className="landing-nav-cta-note">Không cần tài khoản</span>
          </Link>
        </div>
      </header>

      {/* ─── Phân đoạn 1: Hero — Tên gọi & Khát vọng ─── */}
      <section className="landing-hero-wrapper landing-section" aria-label="Giới thiệu ShootingStar">
        <HeroSequence />
      </section>

      {/* ─── Phân đoạn 2: Thách thức — Biến động & Nhiễu loạn ─── */}
      <section className="landing-section landing-section-light" aria-label="Thách thức thực nghiệm">
        <div className="landing-section-inner">
          <div className="landing-section-eyebrow">Thách thức thực nghiệm</div>
          <h2 className="landing-section-title">
            Thị trường có thể đổi hướng chỉ sau một tin tức.
          </h2>
          <p className="landing-section-body">
            Những lời quảng cáo &ldquo;tỷ lệ thắng 80–90%&rdquo; hầu hết là ảo ảnh sinh
            ra từ rò rỉ dữ liệu tương lai (lookahead bias) và khớp tham số quá mức.
            Thực tế là thị trường Bitcoin spot vận hành gần với hiệu quả thông tin.
            Một tin tức vĩ mô hay một dòng lệnh lớn có thể bẻ gãy mọi quy luật kỹ
            thuật trong chớp mắt.
          </p>
        </div>
      </section>

      {/* ─── Phân đoạn 3: Giải pháp — Đặt dự đoán cạnh bằng chứng ─── */}
      <section className="landing-section landing-section-dark" aria-label="Giải pháp nghiên cứu">
        <div className="landing-section-inner">
          <div className="landing-section-eyebrow landing-section-eyebrow-light">Nền tảng nghiên cứu</div>
          <h2 className="landing-section-title landing-section-title-light">
            Một nơi để đặt dự đoán cạnh bằng chứng.
          </h2>
          <p className="landing-section-body landing-section-body-light">
            ShootingStar xây dựng cơ sở hạ tầng thực nghiệm độc lập: dự đoán xác suất
            hướng giá trong 30 phút kế tiếp dựa trên nến đã đóng tại thời điểm $t$.
            Dự đoán được ghi nhận bất biến vào sổ dữ liệu tại mốc phát sinh và đối
            chiếu sòng phẳng với kết quả thị trường. Không làm tròn, không vẽ lại lịch sử.
          </p>
          <div className="landing-section-cta">
            <Link href="/dashboard" className="landing-cta-secondary">
              Xem dashboard →
            </Link>
          </div>
        </div>
      </section>

      {/* ─── Phân đoạn 4: Tham vọng — Ba trụ cột ─── */}
      <section className="landing-section landing-section-light" aria-label="Định hướng phát triển">
        <div className="landing-section-inner">
          <div className="landing-section-eyebrow">Định hướng phát triển</div>
          <h2 className="landing-section-title">Kỹ thuật · Tin tức · Con người</h2>
          <p className="landing-section-body" style={{ marginBottom: 40 }}>
            Ba trụ cột định hình tương lai của nền tảng. Gần 90% vẫn là mục tiêu chưa đạt.
          </p>
          <div className="landing-pillars">
            <div className="landing-pillar">
              <div className="landing-pillar-label">Kỹ thuật</div>
              <div className="landing-pillar-status landing-pillar-status-active">Đang thử nghiệm</div>
              <p className="landing-pillar-desc">
                Mô hình định lượng xác suất và Pattern Lab mẫu hình nến, tuân thủ chặt chẽ
                loại trừ rò rỉ dữ liệu tương lai.
              </p>
            </div>
            <div className="landing-pillar">
              <div className="landing-pillar-label">Tin tức</div>
              <div className="landing-pillar-status landing-pillar-status-gated">Mục tiêu chưa đạt</div>
              <p className="landing-pillar-desc">
                Tích hợp phân tích luồng tin tức vĩ mô và sự kiện tức thời vào bộ lọc dự đoán.
                Định hướng phát triển tương lai.
              </p>
            </div>
            <div className="landing-pillar">
              <div className="landing-pillar-label">Con người</div>
              <div className="landing-pillar-status landing-pillar-status-gated">Mục tiêu chưa đạt</div>
              <p className="landing-pillar-desc">
                Cơ chế giám sát phản biện và thẩm định độc lập từ chuyên gia trước các quyết định
                rủi ro. Định hướng phát triển tương lai.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ─── Phân đoạn 5: Kỷ luật — Nguyên tắc & Giới hạn ─── */}
      <section className="landing-section landing-section-parchment" aria-label="Nguyên tắc và giới hạn">
        <div className="landing-section-inner">
          <div className="landing-section-eyebrow">Cam kết trung thực</div>
          <h2 className="landing-section-title">Minh bạch phương pháp trước mọi con số.</h2>
          <div className="landing-principles">
            <div className="landing-principle">
              <div className="landing-principle-title">Chống rò rỉ dữ liệu</div>
              <p className="landing-principle-desc">
                Mọi đặc trưng tại thời điểm <code>t</code> chỉ dùng nến đã đóng
                với độ trễ ghi nhận tối thiểu 1.000ms. Không nhìn trước tương lai.
              </p>
            </div>
            <div className="landing-principle">
              <div className="landing-principle-title">Không giả lập phí bằng 0</div>
              <p className="landing-principle-desc">
                Chi phí giao dịch Binance Spot 0,20% roundtrip và mô hình trượt giá (slippage)
                bắt buộc phải được tính vào mọi bài toán.
              </p>
            </div>
            <div className="landing-principle">
              <div className="landing-principle-title">Chỉ số P&amp;L: GATED</div>
              <p className="landing-principle-desc">
                Chỉ số P&L ròng và chính sách hành động tự động theo chi phí hiện chưa được
                mở khóa cho đến khi hoàn thành thẩm định độc lập. Không có số liệu bịa đặt.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ─── Phân đoạn 6: CTA cuối ─── */}
      <section className="landing-section landing-section-dark landing-section-cta-block" aria-label="Truy cập hệ thống">
        <div className="landing-section-inner" style={{ textAlign: 'center' }}>
          <h2 className="landing-section-title landing-section-title-light">
            Sẵn sàng kiểm chứng dữ liệu thực nghiệm?
          </h2>
          <p className="landing-section-body landing-section-body-light" style={{ marginBottom: 40 }}>
            Khám phá cấu trúc dữ liệu nến, các thí nghiệm walk-forward
            và nhật ký tín hiệu trực tiếp trên hệ thống cục bộ.
          </p>
          <div className="landing-cta-group">
            <Link href="/dashboard" className="landing-cta-primary">
              Vào dashboard demo
            </Link>
            <span className="landing-cta-note">Không cần tài khoản</span>
          </div>
          <div style={{ marginTop: 20 }}>
            <Link href="/about" className="landing-cta-text">
              Xem phương pháp nghiên cứu →
            </Link>
          </div>
        </div>
      </section>

      {/* ─── Footer ─── */}
      <footer className="landing-footer">
        <div className="landing-footer-inner">
          <span className="landing-footer-brand">✦ ShootingStar</span>
          <span className="landing-footer-note">
            Nền tảng nghiên cứu cục bộ — không cam kết lợi nhuận — không số liệu bịa đặt.
          </span>
          <nav className="landing-footer-nav" aria-label="Liên kết trang">
            <Link href="/about">Phương pháp</Link>
            <Link href="/dashboard">Dashboard</Link>
          </nav>
        </div>
      </footer>
    </div>
  );
}
