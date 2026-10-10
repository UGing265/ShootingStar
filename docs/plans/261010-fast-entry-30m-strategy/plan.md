---
title: "Một lượt — một kế hoạch — tối đa 30 phút"
description: "Tìm điểm mua BTCUSDT Spot, chờ xác nhận, khóa TP/SL và theo dõi tối đa 30 phút từ lúc vào; xác suất có kiểm chứng."
status: in-progress
priority: P1
tags: [research, backend, frontend, experimental]
blockedBy: []
blocks: []
created: 2026-10-10
---
# Chiến thuật điểm vào và thoát trong 30 phút

## Quyết định người dùng đã chốt
- Người chưa có BTC tìm điểm mua; long-only Binance BTCUSDT Spot, không short.
- Phân tích/theo dõi có thể chạy lâu hơn 30 phút; từng vị thế từ lúc vào tối đa 30 phút.
- Mua / chờ xác nhận / bỏ lượt; một kế hoạch gồm vùng vào, điều kiện vào, TP, SL, hạn chờ, điều kiện hủy và bằng chứng.
- Sau vào: chạm TP/SL thì thoát sớm, không chạm thì thoát khi hết 30 phút. Không dời SL xa hơn, gia hạn hoặc sửa kế hoạch cũ để biến thua thành thắng.
- “Đánh nhanh thắng nhanh” là mong muốn; không bảo đảm thắng mỗi lần. Kế hoạch trước, giới hạn lỗ trước, bằng chứng trước.
- Phạm vi là hỗ trợ quyết định và ghi nhận paper/manual execution, **không gửi lệnh thật**. Hết hạn tạo tín hiệu thoát, không bảo đảm người dùng đã bán hoặc khớp đúng giá.

## Phạm vi và lựa chọn
Mode hard; brainstorm đã chốt, không hỏi lại scope. Tái dùng causal feed, patterns, DB/repository, CLI, Next proxy và report. Không lấy directional model cũ hoặc điểm LLM làm xác suất barrier. Không dựng exchange order engine, wallet, dashboard mới hay vòng gọi Gemini mỗi tick.

Hai chế độ dữ liệu đều bắt buộc: Replay snapshot để nghiên cứu; watcher public market data để theo dõi local. Chỉ một watch session hoạt động cho cùng người vận hành/symbol và tối đa một vị thế mở; không khuyến khích churn liên tục.

Bốn phase có lý do: barrier/contract, runtime/persistence, ước lượng xác suất, bề mặt/kiểm chứng. Cost/risk/validation là gate trong các phase, không phải tính năng bỏ lại. Codebase summary đã đọc; đây chỉ là plan, không có code triển khai hoặc kết quả lợi nhuận.

## Tái sử dụng và khoảng trống
- `application/external_analysis/context.py`: canonical feed 6h, feature/source IDs, causal availability; giữ nguyên hướng giá cuối kỳ cho job cũ.
- `application/patterns.py`: đo hình dạng/bối cảnh; không khớp một mẫu không tự động loại mọi cơ hội, nhưng không bỏ qua evidence/cost gate.
- `application/replay.py`: hiện chấm hướng giá tại horizon, **không** chấm first TP/SL hit hoặc fill.
- `application/signals.py`: prediction bất biến và outcome riêng; tái dùng convention, không nhét TP/SL vào `probability_up/down/no_trade` sai nghĩa.
- Existing ingestion chủ yếu snapshots OHLC; cần trade event ordering, availability receipts và public watcher mới.
- `docs/binance-spot-fees.md`: fee register có, slippage/net expectancy còn gated. Không dùng 0 slippage hoặc “phổ biến” tự đặt.

## Phases
| Phase | Nội dung | Trạng thái |
|---|---|---|
| 01 | [Kế hoạch giá, contract và rủi ro](phase-01-entry-barriers-risk.md) | In Progress (Domain & Engine Verified) |
| 02 | [Watcher, lịch sử và lifecycle](phase-02-watcher-lifecycle.md) | In Progress (Simulation Active / Live Deferred) |
| 03 | [Xác suất barrier và kiểm định](phase-03-probability-validation.md) | In Progress (Labeler & CLI Gates Verified) |
| 04 | [UI dễ đọc và nghiệm thu toàn luồng](phase-04-ui-verification.md) | Deferred (Simulation Pivot) |
Thứ tự 01 → 02 → 03 → 04. Một integration owner cho shared models/repository/API và UI; không sửa shared file đồng thời.

Nguồn và adjudication nghiên cứu: [Research decisions](research-decisions.md). Không dùng công thức short hoặc ngưỡng reliability tùy ý từ agent.

## Quan hệ plan
- Đây là mục tiêu barrier/entry mới, không thay nghĩa job dự báo hướng/reveal/vote cũ.
- [Báo cáo dễ đọc](../261010-readable-evidence-report/plan.md): reuse presentation contract, phối hợp thứ tự sửa UI; không bắt probability/data phase chờ UI. Không dependency cấp plan vì không cần output chưa có để bắt đầu/end-to-end riêng.
- [Agent evidence](../261010-agent-evidence-analysis/plan.md), [API research](../261010-external-model-api-research/plan.md), [Replay UX](../261010-replay-result-ux/plan.md), [Historical replay](../261009-historical-replay-research/plan.md): liên quan dữ liệu/nhận định, nhưng không chặn nghiệm thu chức năng cũ và không bị coi hoàn tất bởi plan mới.
- Các gate net-cost/paper trading trong [platform](../261009-shootingstar-research-platform/plan.md) được triển khai cho phạm vi chiến thuật này, không mở khóa news/auto orders/general deployment.
- Chỉ ghi `blockedBy/blocks` khi thực sự phụ thuộc toàn bộ deliverable; overlap/gate riêng mô tả trong phase, tránh khóa plan unrelated hoặc vòng phụ thuộc.

## Gate quan trọng
- Phải chốt số vốn/notional, mức lỗ tối đa mỗi lượt, hạn chờ, freshness/latency và ngân sách watcher/model. Không tự chọn risk % hoặc TP/SL % tùy ý; thiếu → `CONFIG_REQUIRED`, không `BUY`.
- Rule windows/confirmation/buffer/minimum edge/minimum samples được chọn trên train/validation và đóng version trước test; không chọn sau khi thấy outcome.
- Chưa có execution cost methodology/độ tin cậy: hiển thị candidate `WATCH_ONLY`, không kêu mua bằng xác suất bịa. Đạt đủ gates mới có `BUY_ELIGIBLE` dạng hỗ trợ, không là lệnh.
- Probability chỉ TP_FIRST/SL_FIRST/TIMEOUT, null khi thiếu evidence; ambiguous/censored không được coi thắng hoặc timeout. Probability không bằng net profit/expected value.
- Tất cả thời gian UTC epoch/receipts; UI UTC+7; dùng dữ liệu khả dụng tại quyết định. Historical LLM narrative có caveat hồi cứu, không chứng minh prospective.

## Nghiệm thu cuối
Một luồng thật Replay + local watcher: candidate → wait → trigger → explicit paper/manual entry → locked TP/SL → TP/SL/time exit instruction → confirmed outcome riêng, hoặc mất dữ liệu → degraded/unscorable. Không auto trade, không auto Gemini retry vì timeout mơ hồ, không fake fills/cost/probability. Browser desktop/mobile + CLI watcher restart + backend regression trên DB riêng + frontend typecheck/build + report kiểm định độc lập.

## Red-team review — 2026-10-10
Ba reviewer độc lập: safety, lifecycle, statistics. 8 finding gộp thành 7; chấp nhận 7 (5 High, 2 Medium), đã chỉnh plan, không phải kiểm chứng implementation.

| Finding | Mức | Đã áp dụng |
|---|---|---|
| EXIT_REQUIRED còn exposure, chưa được mua lượt mới | High | Phase 02/04: atomic reservation đến confirmed flat |
| Paper outcome không được đóng vị thế manual | High | Phase 02/04: immutable mode, closure authority |
| Manual entry trễ bỏ sót SL quá khứ | High | Phase 02/04: path reconciliation, occurrence/receipt |
| Thiếu bootstrap approval từ zero evidence | High | Phase 02/03: RESEARCH_ONLY shadow tách production |
| Manual mua lệch giá bị reject rồi hệ thống FLAT giả | High | Phase 01/02/04: OFF_PLAN recording, risk/exit warning |
| Confirmation và invalidation cùng nến | Medium | Phase 01: explicit predicate/precedence |
| Trade sau entry cùng millisecond bị bỏ | Medium | Phase 03: source-order boundary/ambiguity |

Scope validation dùng quyết định đã chốt trong hội thoại: chưa mua, long-only, TP/SL, max30m từ entry, watcher dài hơn, không real orders. Risk amounts/wait budget là config user phải nhập trước activation; không tự bịa số trong plan.


## Handoff
Mỗi phase có checklist và evidence gate. Khi triển khai phải resolve risk configuration trước kích hoạt BUY; nghiên cứu/theo dõi vẫn chạy và báo trạng thái trung thực. Không giảm yêu cầu xác suất xuống điểm rule; không gọi observation baseline là xác suất đã hiệu chuẩn.
