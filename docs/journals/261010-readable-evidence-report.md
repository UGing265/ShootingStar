---
title: "Lập plan báo cáo phân tích dễ đọc"
created: 2026-10-10
status: planning-only
---
# Lập plan báo cáo phân tích dễ đọc

## Context
Người dùng gửi ảnh report có epoch, tên feature nội bộ, Markdown thô và số khoa học; yêu cầu lập kế hoạch làm dễ đọc.

## Đã làm
- Đối chiếu renderer `<p>`, feed serializer, công thức/unit và synthesis prompt.
- Tạo [plan hai phase](../plans/261010-readable-evidence-report/plan.md); cập nhật liên kết API/UX/pipeline. Không sửa code, không gọi model hoặc DB.
- Scan `docs/plans/` vì `plans/` không có; tài liệu `docs/development-rules.md` không tìm thấy.

## Quyết định
Canonical feed/job là nguồn số liệu section 1; Markdown an toàn cho bài lập luận. Ratio phải đổi biểu diễn thành %, volume là BTC. Bài cũ bất biến; không auto-generate để dịch. Technical details giữ raw/provenance.

## Giới hạn
Tên status plan cũ không chuẩn và có tuyên bố hoàn tất trước đây; không tự xác nhận lại các tuyên bố đó. Plan mới còn Pending. Script activation chạy nhưng báo thiếu `CK_SESSION_ID`, không lưu state session; đường dẫn plan là handoff chính.

## Tiếp theo
Triển khai theo hai phase, smoke trên UI thật + kiểm tra đơn vị/timezone/unsafe links; chỉ hoàn tất sau evidence. Không mở rộng timeout, quota, research hoặc accuracy.
