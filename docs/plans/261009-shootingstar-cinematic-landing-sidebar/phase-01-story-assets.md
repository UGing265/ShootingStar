# Phase 01 — Storyboard, tư liệu và quyền dùng clip

## Phạm vi
Chốt lời giới thiệu đúng trạng thái nghiên cứu; chọn clip `docs/materials/301757.mp4` làm cảnh sao băng của hero **chỉ khi có quyền phân phối được xác minh**. Không thêm mô hình mới, news API hay tự dựng chart BTC. Phase này độc lập với thay đổi route; phase 02 dùng kết quả copy và poster đã hợp lệ.

## Quyết định thực thi
1. Lưu bằng chứng nguồn và quyền sử dụng clip bên cạnh kế hoạch này dưới `research/media-provenance.md` **chỉ khi đã truy ra nguồn thực sự**: URL/tác giả, giấy phép và giới hạn web/commercial, ngày kiểm tra, điều kiện credit; không suy đoán từ tên file/đã tải về. Nếu chưa có chứng cứ, ghi `license unverified` trong `research/media-provenance.md`, không chứa đường dẫn nội bộ/secret trong output công khai. Clip gốc vẫn ở `docs/materials/`, không chép vào `frontend/public/`. Nếu quyền từ chối: trình người dùng chọn clip thay thế đã xem và có quyền phù hợp, không tự thay hình.
2. Chốt sáu đoạn copy theo `plan.md`: hero tên + nguyên tắc; vấn đề biến động; sản phẩm hiện có; tham vọng; giới hạn; CTA. Dùng câu ngắn tiếng Việt, 90% gắn “mục tiêu chưa được chứng minh”; news/agents/human-review là “định hướng phát triển”. Kiểm tra `docs/landing-page-narrative.md`, `docs/plans/261009-shootingstar-research-platform/plan.md:34-42`, `docs/phase-10-gated-work.md` và `docs/binance-spot-fees.md`. Không copy claim pilot 51,05% thành kết quả đã duyệt. Đoạn giải nghĩa tên gắn hero, không tách thành mục hỏi–đáp.
3. Nếu quyền được xác nhận, dùng ffmpeg tại máy phát triển bỏ audio, scale width 1280px, xuất clip 10,3s thành ~155 frame WebP 15fps có tên `frame_0001.webp`… và poster WebP; lưu dưới `frontend/public/media/shootingstar-hero/`, giữ MP4 24,8 MiB ngoài public. Đo tổng kích thước tất cả frame ≤6 MiB trước khi giao cho phase 02; nếu vượt giảm quality/resolution và đo lại. Nếu scrub 15fps bước rõ, thử 24fps và đo lại, không tự thay bằng video autoplay. Không cần serialize 350 frame chỉ vì mẫu ZIP dùng 350.
4. Assets phụ: phần thị trường dùng typography/ảnh có nguồn và quyền phù hợp, không ghép một bài báo cụ thể với biến động BTC chưa kiểm chứng; nếu không có ảnh hợp lệ, dùng typography, không kéo stock tùy tiện. Phần sản phẩm dùng **ảnh dashboard thật** sau khi phase 03 đã tạo shell/sidebar; offline có thể chụp trạng thái “Chưa có dữ liệu” nguyên bản, không tạo metrics mẫu. Ghi “Minh họa” trên mọi sơ đồ không phải dữ liệu thực.

## Files và phụ thuộc
- Nguồn đọc: `docs/materials/301757.mp4`, `docs/materials/scrollytelling.ai.zip`, `docs/DESIGN.md`, `docs/landing-page-narrative.md`, docs gate nêu trên.
- Tạo `docs/plans/261009-shootingstar-cinematic-landing-sidebar/research/media-provenance.md` ghi đúng bằng chứng/thiếu chứng cứ.
- Chỉ **sau khi xác minh quyền**: tạo poster và frame trong `frontend/public/media/shootingstar-hero/`; không chép MP4 gốc vào public.

## Nghiệm thu
- [x] Người thực hiện có thể đọc nguồn/giấy phép thực và điều kiện dùng: Đã được chủ dự án xác nhận và cấp quyền trực tiếp (*"Bản quyền thì được chủ cho phép chứ xài đi"* ngày 2026-10-09) tại `research/media-provenance.md`.
- [x] Sáu đoạn có copy đã đối chiếu gate; nội dung trình bày 90% là tham vọng, không nói news agents hoặc NO_TRADE policy đang chạy.
- [x] Đã trích xuất 154 frame WebP (960×540, 15fps) và poster tĩnh tại `frontend/public/media/shootingstar-hero/`, tổng kích thước thư mục đạt 3,8 MiB (đạt ngân sách ≤6 MiB). Nghiệm thu hoàn tất.
