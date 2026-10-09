---
title: "Landing cinematic ShootingStar và dashboard sidebar"
description: "Tách trang giới thiệu cuộn theo clip sao băng khỏi dashboard nghiên cứu năm mục."
status: completed
priority: P1
tags: [frontend, docs, feature]
blockedBy: []
blocks: []
created: 2026-10-09
---
# ShootingStar — Landing cinematic và dashboard sidebar

## Goal và hiện trạng
`/` là landing giới thiệu ShootingStar; CTA “Vào dashboard demo” (ghi “Không cần tài khoản”) tới `/dashboard`, không login/cookie/auth giả. Dashboard có sidebar trái: Tổng quan, Dữ liệu, Nghiên cứu, Pattern Lab, Tín hiệu. Hiện `frontend/src/app/page.tsx` là Overview gọi FastAPI server-side, `frontend/src/app/layout.tsx` bọc header và `main-content` cho mọi route, `/about` là trang phương pháp 4 cảnh; các work route khác ở `frontend/src/app/{data,research,patterns,signals}/`. Chuyển Overview sang `/dashboard`, giữ URL các route còn lại. Không sửa backend hoặc thêm dữ liệu mẫu.

Kế hoạch này thay chỉ dẫn **UI/landing** ở Phase 8/9 của [`../261009-shootingstar-nextjs/plan.md`](../261009-shootingstar-nextjs/plan.md) và [`../261009-shootingstar-research-platform/plan.md`](../261009-shootingstar-research-platform/plan.md), không thay gate chất lượng/đánh giá A0. Frontend hiện ở `frontend/`, không phải `web/` trong một số mô tả lịch sử. Landing tĩnh và điều hướng chạy được khi API offline; số liệu và claim từ backend vẫn phải qua gate riêng. Xem `docs/DESIGN.md` trước khi sửa UI.

## Quyết định hình ảnh và câu chuyện
Clip nguồn `docs/materials/301757.mp4` dài 10,3 giây, 1920×1080, 30fps, 24,8 MiB: một sao băng đi chéo trên nền sao tĩnh, không phải cảnh 3D camera lao tới. Tham khảo **cơ chế** `docs/materials/scrollytelling.ai.zip` (chapter 700vh/404vh, sticky canvas, 350/202 frame WebP scrub theo cuộn), không chép asset/HTML/GSAP/Lenis/tracker. Dùng clip có sẵn kết hợp typography/lớp chuyển cảnh tự làm; không vẽ lại sao băng đè lên clip.

Sáu đoạn theo thứ tự: (1) “ShootingStar — Chính xác hơn là tốc độ”, vệt sao băng là ý nghĩa sức mạnh/vẻ đẹp/tham vọng của tên; (2) “Thị trường có thể đổi hướng chỉ sau một tin tức”, nêu bài toán, không gán tin cụ thể vào nến giả; (3) “Một nơi để đặt dự đoán cạnh bằng chứng”, dẫn đến dashboard thật; (4) “Kỹ thuật · Tin tức · Con người”, gắn “Định hướng phát triển” với news/agents/human-review, gần 90% là **mục tiêu chưa đạt**; (5) nguyên tắc chính xác hơn tốc độ và giới hạn nghiên cứu; (6) CTA vào dashboard demo. Không tuyên bố report pilot được duyệt, policy `NO_TRADE`, paper trading, P&L sau slippage hoặc news ingestion đã hoạt động. Đối chiếu `docs/landing-page-narrative.md`, `docs/phase-10-gated-work.md`, `docs/binance-spot-fees.md` và bản ghi API trước khi viết copy.

## Invariants và gates
- Python/FastAPI là nguồn tính toán duy nhất; client chỉ hiển thị dữ liệu từ API server-side. Backend lỗi/DB rỗng hiển thị trạng thái thật. Không tạo biểu đồ giá, tỷ lệ thắng, signal hay metrics giả.
- Quyền sử dụng `docs/materials/301757.mp4`: Đã được chủ dự án xác nhận và cấp quyền trực tiếp (*"Bản quyền thì được chủ cho phép chứ xài đi"* ngày 2026-10-09). Đã trích xuất 154 khung hình WebP nén nhẹ (960×540) và poster tĩnh với tổng dung lượng 3,8 MiB (đạt ngân sách $\le 6\,\text{MiB}$) tại `frontend/public/media/shootingstar-hero/`.
- Trên desktop, vị trí cuộn điều khiển frame tiến/lùi; kéo nhanh không để canvas trắng. Mobile, JS tắt và `prefers-reduced-motion` hiển thị poster tĩnh hợp lệ (`poster.webp`), không tải chuỗi 154 frame. Không khóa cuộn, không autoplay âm thanh.
- Layout marketing full-width riêng; sidebar chỉ thuộc nhóm work; URL detail và query params cũ giữ nguyên. Không bọc toàn app trong client component.

## Phases và ranh giới
1. [`phase-01-story-assets.md`](phase-01-story-assets.md): copy, xác nhận quyền dùng clip từ chủ dự án, storyboard, ngân sách media 3,8 MiB, thiết kế poster/fallback.
2. [`phase-02-landing-motion.md`](phase-02-landing-motion.md): route cutover, hero canvas scrub 154 frame và các đoạn landing, `/about` sửa claim.
3. [`phase-03-sidebar-and-verification.md`](phase-03-sidebar-and-verification.md): sidebar, drawer di động, nhãn Overview, smoke browser/typecheck/build. Sidebar/route shell phải có trước ảnh dashboard thật ở phase 2: thực hiện shell/sidebar trước, chụp ảnh dashboard thực sau khi shell chạy, rồi hoàn tất đoạn 3 landing. Chỉ một người/slice sở hữu từng file khi thực hiện song song.

## Bằng chứng nghiệm thu
- Trong `frontend/`: `npm run typecheck` và `npm run build`; chạy `npm run dev`, dùng browser kiểm tra `/` → CTA `/dashboard`, 5 link/sidebar và các detail URL cũ, `/about` CTA. Không sửa backend nên không có backend regression bắt buộc.
- Desktop: cuộn xuôi/ngược 0→cuối→giữa của hero; kéo nhanh, resize, focus CTA. Mobile khoảng 390px và reduced motion/JS disabled: text/CTA nhìn thấy, không tải frame sequence. Dùng backend offline để thử `/` độc lập và dashboard lỗi/rỗng trung thực; khi backend có dữ liệu, không thay đổi các link detail và nhãn các danh sách giới hạn 5 không bị hiểu là tổng.
- Đã nghiệm thu hoàn tất sau quan sát thực tế trên browser: Quyền sử dụng clip được chủ dự án xác nhận trực tiếp, chuỗi 154 frame WebP (3,8 MiB) đã tích hợp vào canvas scrollytelling với pixel/opacity thay đổi đồng bộ theo cuộn chuột; fallback poster trên mobile (390px) và reduced-motion hoạt động chính xác.
