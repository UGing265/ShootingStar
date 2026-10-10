---
title: "Chốt plan điểm mua, TP/SL tối đa 30 phút"
created: 2026-10-10
status: planning-only
---
# Chốt plan chiến thuật 30 phút

## Context
Người dùng chưa mua BTC, muốn tìm điểm vào và vùng lời/nguy hiểm, TP/SL tối đa30m từ entry. Watcher chạy lâu hơn; không cam kết một lượt chắc thắng.

## Đã làm
- Tạo [plan bốn phase](../plans/261010-fast-entry-30m-strategy/plan.md) và research decisions; cập nhật sáu plan liên quan, không thay status lịch sử hoặc khóa dependency toàn plan không cần.
- Hai research slices: provider data/costs và probability/code reuse. Ba reviewers: safety/lifecycle/statistics; gộp8 findings thành7, sửa plan cả7.
- Không sửa code, chạy watcher/train/backtest, gọi model hoặc đặt order.

## Quyết định
Long-only, một active exposure kể cả EXIT_REQUIRED, immutable TP/SL/deadline/mode. Market-touch probabilities khác executable profit. RESEARCH_ONLY shadow bootstrap từ chưa approved; manual off-plan vẫn ghi/reconcile, không để FLAT giả.

## Rủi ro
Risk amounts/hạn chờ còn phải operator cấu hình; calibration/cost/prospective evidence không được bịa. Public stream không bảo đảm fill/stop bảo vệ tiền thật. Script activation báo CK_SESSION_ID thiếu, state không persist; đường dẫn plan là handoff chính.

## Tiếp theo
Triển khai theo phase và gate đã viết, không tự triển khai ở lượt lập kế hoạch. Chỉ báo done về functionality sau CLI/browser/contracts/report thực tế.
