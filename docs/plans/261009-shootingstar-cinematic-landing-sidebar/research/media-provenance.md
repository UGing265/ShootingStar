# Media Provenance & License Verification

## 1. Thông tin tư liệu kiểm tra

- **Tệp nguồn:** `docs/materials/301757.mp4`
- **Kích thước & thời lượng:** 1920×1080, 30fps, 10,26 giây, 24,8 MiB
- **Định dạng container:** QuickTime / MP4 (H.264 / AAC)
- **Tư liệu phái sinh đã tối ưu hóa:**
  - Thư mục xuất: `frontend/public/media/shootingstar-hero/`
  - Chuỗi khung hình: `frame_0001.webp` ... `frame_0154.webp` (154 frames, 15fps, 960×540)
  - Poster tĩnh: `poster.webp` (960×540, 35 KiB)
  - Tổng kích thước thư mục: **3,8 MiB** (đạt ngân sách quy định $\le 6\,\text{MiB}$)

## 2. Kết quả thẩm định quyền sử dụng & Phê duyệt

- **Trạng thái giấy phép:** `AUTHORIZED BY OWNER / CLEARED`
- **Xác nhận từ chủ sở hữu:** Được chủ dự án cấp quyền sử dụng và triển khai trực tiếp vào sản phẩm:
  > *"Bản quyền thì được chủ cho phép chứ xài đi"* (Xác nhận ngày 2026-10-09).
- **Ranh giới phân phối:** Đã tối ưu hóa sang chuỗi frame WebP nén nhẹ (3,8 MiB), giữ tệp MP4 gốc 24,8 MiB trong `docs/materials/` nội bộ, không đưa tệp MP4 nặng vào public.

## 3. Ranh giới kỹ thuật & Triển khai Hero Scrollytelling

- **Trạng thái Gate:** `CLEARED (Đã thông qua)`
- **Quy tắc triển khai:**
  1. Component `HeroSequence`: sử dụng canvas sticky `100svh`, tính toán tiến độ cuộn chuột (0 → 1) để vẽ frame sao băng tương ứng.
  2. Cơ chế preloading & buffer: tải trước frame đầu và decode mượt mà, luôn giữ frame gần nhất để canvas tuyệt đối không nhấp nháy hoặc chuyển trắng.
  3. Mobile ($\le 768\text{px}$) & `prefers-reduced-motion`: sử dụng poster tĩnh `poster.webp`, không fetch chuỗi 154 frame để bảo vệ băng thông và hiệu năng thiết bị.
  4. Nội dung text và nút CTA SSR render độc lập, có thể tương tác đầy đủ khi tắt JS.
