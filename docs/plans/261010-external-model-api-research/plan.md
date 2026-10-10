---
title: "Thiết kế luồng phân tích Gemini API và thư viện bài học cho Replay"
description: "Tách backend tự train/API, phân tích 6 giờ nến trước t, quản trị bài học có duyệt, UX Replay và kiểm chứng prospective."
status: proposed
priority: P1
tags: [research, replay, external-api, model-evaluation]
blockedBy: []
blocks: []
created: 2026-10-10
---
# Kế hoạch nghiên cứu model API ngoài cho Replay

> **Trạng thái: CHỈ LẬP KẾ HOẠCH.** Chưa kết nối API, chưa chọn model thắng, chưa chạy kiểm định, chưa sửa gate `NO_MODEL`. Hướng tự train cũ được lưu ở [thiết kế tự train](../../self-trained-model-design.md); không bắt người dùng tự train trước khi thử nhận định API. Nghiên cứu nguồn và thiết kế tạm: [model API ngoài](../../external-model-forecast-design.md).

## Mục tiêu

Cho người dùng chọn snapshot, mốc `t`, giá mua giả định `P` và nhận nhận định API về **giá sau 30 phút so với P**. AI đọc 6 giờ OHLCV sạch, kết hợp **định nghĩa + caveat** của bài trading đã duyệt, đề xuất mẫu hình/nhận định và trỏ `lesson_id` thay vì bịa URL. Backend giữ nguồn và chấm; user vote độc lập và **không đi vào train/prompt AI**. Code train model cũ **giữ nguyên chức năng** nhưng nằm trong `application/training/`; API mới độc lập tại `application/external_analysis/`. Chưa có bằng chứng Gemini, OpenAI hay Claude dự báo BTC tốt nhất; báo cáo prospective sẽ trả lời sau khi có dữ liệu.

## Bất biến và phạm vi

- Nến input là BTCUSDT Spot `1m`/`5m`, cửa sổ cố định **6 giờ trước `t`** (~360/72 nến khi đủ), mọi nến đã đóng và `available_at <= t`; snapshot 2 ngày không cho phần sau `t` vào prompt. Chọn mốc gần đầu snapshot thiếu 6h: backend báo `INSUFFICIENT_HISTORY` **trước khi gọi provider**, không nhầm với `ABSTAIN` do model trả lời và không lén dùng tương lai. MVP API chỉ horizon **30m**; Replay cũ cho horizon khác vẫn `NO_MODEL` nếu thiếu model đúng bài toán, không giả mở rộng.
- Tóm tắt/context là **định dạng do dự án định nghĩa**, không phải nhãn AI tự train: bản A gồm OHLCV có thứ tự, bản B là ít phép tính deterministic kèm công thức/source bars và vài nến cuối; thử A/B để biết cách nào hữu ích. Backend tính/serialize, không tạo “mẫu hình đã chứng minh” hay % giả.
- Agent nghiên cứu bài học chạy **ngoài luồng dự báo**: đề xuất nguồn, định nghĩa/rule/caveat/URL; admin duyệt/sửa/từ chối trên UI, lưu revision bất biến trong DB. Model chỉ nhận bài **APPROVED** có text ngắn và link đã kiểm tra, trả ID/timestamp; verifier kiểm ID/timestamp/shape chứ không xác nhận suy luận đúng. Không gọi web trực tiếp khi replay.
- Một request Gemini/model ngoài trả `UP | DOWN | ABSTAIN` và giải thích ngắn ghi rõ do AI tạo; `probability_up/down=null` tới khi có kiểm định riêng. Bảo vệ key/cost/quota/admin route; **tối đa 10 Gemini key** để vận hành/failover hợp lệ, **không lách 429** vì Google áp quota theo project [nguồn](https://ai.google.dev/gemini-api/docs/rate-limits). Không có key thật thì không thể nghiệm thu call API.
- Nhận định **hồi cứu** từ model hiện nay có nguy cơ trọng số đã học tương lai; banner rõ “minh họa hồi cứu”, không gọi historical OOS sạch. **Prospective** lưu dự báo trước outcome rồi mới chấm, dùng để so baseline. Vote của người lưu riêng, không dùng để train model hay để AI dự đoán lần sau. API/UI giữ timestamp UTC epoch ở BE/DB, UTC+7 ở FE.
- `NO_MODEL` của nhánh artifact tự train vẫn trung thực; luồng API có nhãn riêng **thử nghiệm**. Không auto trade, P&L, lời hứa thắng thị trường hay đường tắt mở khóa Phase 02 model point-price cũ.

## Phân vùng BE/FE khi triển khai (chưa có mã mới)

| Tầng | Vị trí dự kiến | Trách nhiệm |
|---|---|---|
| Train giữ lại | `backend/shootingstar/application/training/` | Chuyển `experiment`, `labels`, `modeling`, `splits` sau refs/callers/tests; giữ CLI và output cũ đúng nghĩa close-to-close |
| Chung | `backend/shootingstar/domain/`, storage + `adapters/db/`, `application/replay.py`, `application/features.py` nếu còn dùng chung | Candle, snapshot hash, `available_at`, outcome và vote riêng; không nhân bản logic |
| Phân tích API | `backend/shootingstar/application/external_analysis/` | Lấy nến 6h, kiểm input, đóng gói A/B, prompt, schema verifier, job lock và trưởng thành outcome |
| Provider keys | `backend/shootingstar/adapters/model_api/` | Gemini adapter, key slots tối đa 10, failover an toàn, quota/project, usage/cost, lỗi, không lộ secret |
| Bài học và admin | `backend/shootingstar/api/`, `adapters/db/`, `frontend/src/features/lessons/`, `frontend/src/app/(work)/lessons/review/page.tsx` | Agent nghiên cứu ngoài luồng → PENDING → admin duyệt revision → chỉ APPROVED được đưa vào context/link UI |
| Replay FE | `frontend/src/features/replay/`, `frontend/src/app/api/` | 4 bước Điểm mua → AI thử nghiệm + link học → Vote của tôi → Xem kết quả; server proxy, spinner/lỗi/refresh, không để client tính nhãn |
| Kiểm chứng | `tests/test_causal_replay.py`, `tests/test_api_and_ui.py`, test adapter/repository, browser smoke | Không nhìn trước, key không lộ, lesson revision, rate limit, UX trên snapshot thật, prospective report |

## Hành trình người dùng — nghiệm thu được, không phải wireframe rỗng

1. Chọn snapshot có đủ 6h nến trước mốc muốn thử; click biểu đồ hoặc nhập UTC+7/giá P, horizon 30m. Chart zoom bằng cuộn, pan bằng giữ chuột trái; hiện đoạn 6h sử dụng, giá quan sát khác P và lý do thiếu nến. Không đủ input → không tốn tiền gọi Gemini.
2. Bấm **Phân tích với Gemini (thử nghiệm)** một lần: BE khóa input, gọi API, lưu output và trạng thái. FE hiện đang chuẩn bị/đang gọi/READY/ABSTAIN/FAILED, model ID, phân tích AI, nến được viện dẫn, bài học đã duyệt (link thật từ backend); không có bài duyệt → không bịa link. Với mốc lịch sử có banner leakage-risk, không phát % kiểm định giả.
3. Bấm **Tôi dự đoán** UP/DOWN: khóa vote riêng; người xem AI trước khi vote nên không gọi so sánh mù. AI không học từ lựa chọn này.
4. Bấm **Xem kết quả**: BE chỉ reveal khi đủ điều kiện và chấm theo P. Với **hồi cứu**, nếu snapshot đã chứa nến kết quả thì có thể reveal ngay nhưng luôn ghi “minh họa hồi cứu, không phải dự báo lịch sử công bằng”; nếu thiếu nến thì `UNSCORABLE`. Với **prospective**, nếu thời gian thật chưa tới `t+30m` hoặc nến chưa khả dụng thì `PENDING`; thiếu dữ liệu sau hạn thì `UNSCORABLE`. AI ABSTAIN/lỗi không được chấm như prediction. GET trước reveal ẩn kết quả.
5. Trang quản trị bài học (local/admin-only): agent gửi candidate → UI đọc nguồn/định nghĩa/caveat → sửa/duyệt/từ chối → DB lưu version+reviewer/audit; không bắt người dùng mò DB, không auto publish link.

## Phases theo thứ tự, không vòng phụ thuộc

1. [Phase 01 — Giao thức và tách code train](phase-01-evaluate-providers.md) — **IN-PROGRESS**. Refactor code train vào `application/training/` hoàn tất (81/81 test pass, smoke CLI exit code 0); gate protocol/ngân sách chờ người vận hành cấp key trước khi sang Phase 02.
2. [Phase 02 — Backend Gemini pilot](phase-02-experimental-integration.md) — **IN-PROGRESS**. Causal context 6h, serializer A/B, adapter Gemini (tối đa 10 key, bảo vệ quota), verifier, Alembic migration `3c4d5e6f7a8b`, fail-closed API endpoints và tests hoàn tất (88/88 test pass); gate pilot API thật chờ người vận hành cấp key.
3. [Phase 03 — Bài học và UX](phase-03-lesson-review-ux.md) — **IN-PROGRESS**. SSRF validator, Lesson DB models/repo/migration `4d5e6f7a8b9c`, API routes, Next.js page và review component hoàn tất (91/91 test pass, Next build pass); gate browser smoke đang mở.
4. [Phase 04 — Đo thực tế](phase-04-prospective-evaluation.md) — **PENDING**. Log prospective khóa trước giá tương lai, baseline/cost/report theo số mẫu thật; không đủ mẫu thì ghi chưa đủ, không tuyên bố winner.

## Tiền điều kiện & gate chung

- [ ] Người vận hành cấp key hợp lệ và cho phép gửi dữ liệu qua bậc dịch vụ đã chọn; khóa tất cả API có phí sau auth + budget/rate, không yêu cầu key để *viết plan*. 10 key cùng project **không** có thêm quota.
- [ ] BE test theo quy ước repo `uv run --no-project pytest tests`; FE `npm --prefix frontend run typecheck` hoặc build; smoke job+UI bằng snapshot thực và báo status/result thật, không suy từ compile.
- [ ] Tài liệu `docs/backend/README.md`, `docs/frontend/README.md`, `docs/local-run.md` cập nhật sau triển khai; trạng thái kế hoạch chỉ đổi khi có bằng chứng từng phase, không đánh dấu đã nghiệm thu chỉ từ plan này.
