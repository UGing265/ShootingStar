---
title: "Báo cáo phân tích dễ đọc bằng tiếng Việt"
description: "Thay bản debug bằng báo cáo có ngày giờ UTC+7, số rõ đơn vị, định dạng bài viết và nguồn kiểm được."
status: in_progress
priority: P1
tags: [frontend, backend, replay, experimental]
blockedBy: []
blocks: [261010-external-model-api-research]
created: 2026-10-10
---
# Báo cáo phân tích dễ đọc

## Mục tiêu
Người dùng yêu cầu “biến nó thành có thể đọc” sau ảnh báo cáo chứa epoch millisecond, tên biến tiếng Anh, số khoa học và Markdown thô. Chỉ lập kế hoạch; chưa triển khai, chưa nghiệm thu.

Chọn chế độ fast: vấn đề và luồng đã xác định; không nghiên cứu provider mới, không mở rộng pipeline. Dùng `docs/plans/` theo quy chuẩn repository; `plans/` và `docs/development-rules.md` không tìm thấy trong lần scan.

## Bằng chứng mã nguồn
- `frontend/src/features/replay/replay-player.tsx:1277-1304`: bảy phần hiện in chuỗi trong `<p>` với `whiteSpace: pre-line`; không render Markdown, font nội dung 13px.
- `frontend/src/features/replay/external-types.ts:95-110`: feed là `Record<string, unknown>`; cần type/guard rõ trước trình bày.
- `backend/shootingstar/application/external_analysis/context.py:249-312`: các trường mang tên `_pct` thực tế lưu `unit=ratio`, chưa nhân 100. Volume là base volume BTC; `volatility_6h_pct` là biên độ cao–thấp chia giá thấp, không phải độ lệch chuẩn.
- `backend/shootingstar/adapters/model_api/gemini_adapter.py:737-757`: prompt yêu cầu tiếng Việt nhưng gửi feed thô; chưa có contract ngôn ngữ, đơn vị, ngày giờ cho người đọc.
- `docs/DESIGN.md`: body 17px, caption 14px; nền sáng, border mảnh, không shadow trang trí.

## Quyết định
1. Khối “Câu hỏi và dữ liệu” lấy trực tiếp feed/job đã lưu, không dựa vào số AI kể lại. Bảng số đo có tên Việt, đơn vị và giải thích ngắn.
2. Sáu phần phân tích còn lại giữ đầy đủ lập luận/citation, render Markdown an toàn. Không rút toàn bộ báo cáo xuống ba câu.
3. Backend tạo context trình bày deterministic cho prompt mới: ngày giờ UTC+7, số đúng đơn vị, glossary tiếng Việt; giữ feed nguyên bản cho phân tích và provenance. Browser chỉ format giá trị API, không tính lại feature.
4. Job cũ đọc được ngay bằng metadata canonical + renderer; không gọi Gemini để dịch, không sửa bản ghi. Nguyên văn cũ có thể mở trong “Chi tiết kỹ thuật”. Không dùng regex tổng quát để đoán đơn vị hoặc thay mọi số 13 chữ số.
5. Không đổi timeout/key rotation, nghiên cứu nguồn, thuật toán mẫu, outcome/vote, chart hoặc schema DB trong phạm vi này.

## Phases
| Phase | Nội dung | Trạng thái |
|---|---|---|
| 01 | [Ngôn ngữ và contract trình bày](phase-01-presentation-contract.md) | Complete |
| 02 | [Giao diện đọc báo cáo và nghiệm thu](phase-02-report-reader.md) | In Progress (Implementation Verified / Awaiting Visual Acceptance) |

Thứ tự 01 → 02. Một người sở hữu tích hợp `replay-player.tsx`; không cần hydration vì dưới ba phase.

## Quan hệ plan
- [Pipeline bằng chứng](../261010-agent-evidence-analysis/plan.md) và [Replay UX](../261010-replay-result-ux/plan.md) ghi đã hoàn tất theo các tên status không chuẩn (`HOÀN TẤT`, `complete`). Không tự đổi trạng thái lịch sử hoặc coi mọi gate đã được xác minh lại. Đây là bổ sung readability, tái dùng output hiện có, không đợi toàn bộ nghiên cứu.
- Chặn riêng gate **báo cáo dễ đọc** của [model API](../261010-external-model-api-research/plan.md); không chặn thử nghiệm prospective, ingestion hay thư viện bài học. Plan API cần note blocked ở gate tương ứng; hai bên khai báo quan hệ.
- Historical replay phụ thuộc UX/API hiện có; không thêm dependency trực tiếp trùng lặp. Next.js/platform chung không cần thay phạm vi.

**Chiến thuật mới:** [Điểm vào/TP/SL tối đa 30 phút](../261010-fast-entry-30m-strategy/plan.md) là mode riêng, không chỉ đổi wording report. Hai plan chia sẻ renderer/format/unit nhưng không phụ thuộc toàn bộ nhau; trước sửa `replay-player.tsx` và glossary, integration owner xác minh component hiện tại, backend presentation metadata là nguồn duy nhất. Không coi readability hoàn tất là đã kiểm định chiến thuật.

## Bất biến
- Giữ dữ liệu số, feed hash, UTC epoch, source IDs/URLs và bản dự báo đã khóa.
- Không biến tỷ lệ feature thành xác suất thành công; probability null vẫn “Chưa hiệu chuẩn”.
- Không gọi nguồn chưa đọc là đã đọc, không giấu phản biện hoặc caveat hồi cứu.
- Tất cả trường trình bày dùng job đã lưu; không lấy form/snapshot đang chọn.
- Thiếu feed/section là trạng thái thiếu dữ liệu thật, không điền đoạn AI giả.

## Gate bàn giao
- Ảnh trước/sau trên job thật giống tình huống người dùng: không epoch/tên biến/Markdown thô trong phần dữ liệu chính; đủ bảy phần khi job có dữ liệu.
- `0.001768` ratio → `0,1768%`; `-0.000005` → `-0,0005%`; volume `969.9297` → `969,9297 BTC`; không gán USDT cho volume, không làm mất dấu âm hoặc số nhỏ.
- Browser desktop/mobile, nguồn dẫn an toàn, mở technical details, refresh job cũ: không phát sinh POST job/Gemini/vote/reveal.
- Backend tests tương ứng trên DB test riêng; frontend typecheck/build. Output thực tế mới được đánh dấu hoàn tất.

## Câu hỏi mở
Không có quyết định sản phẩm cần hỏi thêm. Triển khai phải xác minh contract phiên bản prompt hiện có và lựa chọn parser Markdown tương thích package lock trước khi chỉnh code.
