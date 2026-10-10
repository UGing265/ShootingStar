---
title: "Thiết kế luồng phân tích Gemini API và thư viện bài học cho Replay"
description: "Tách backend tự train/API, phân tích 6 giờ nến trước t, quản trị bài học có duyệt, UX Replay và kiểm chứng prospective."
status: proposed
priority: P1
tags: [research, replay, external-api, model-evaluation]
blockedBy: [261010-replay-result-ux, 261010-agent-evidence-analysis]
blocks: []
created: 2026-10-10
---
# Kế hoạch nghiên cứu model API ngoài cho Replay

> **Trạng thái: CHỈ LẬP KẾ HOẠCH.** Chưa kết nối API, chưa chọn model thắng, chưa chạy kiểm định, chưa sửa gate `NO_MODEL`. Hướng tự train cũ được lưu ở [thiết kế tự train](../../self-trained-model-design.md); không bắt người dùng tự train trước khi thử nhận định API. Nghiên cứu nguồn và thiết kế tạm: [model API ngoài](../../external-model-forecast-design.md).

**Cập nhật UX 2026-10-10 — đang chờ plan [Replay dễ đọc và kết quả tự mở](../261010-replay-result-ux/plan.md):** Gate UX Replay Phase 03 phải có lời nhận định tiếng Việt dễ hiểu, preview chart ở bước 2/4 và lưu dự đoán bước 3 xong tự mở bước 4/reveal, không thêm lần bấm “Xem kết quả”. Chỉ dẫn cũ về nút riêng bên dưới không còn là yêu cầu hiện hành. Quan hệ blocked chỉ áp nghiệm thu UX, không thay gate key thật/quota/bài học/đánh giá prospective; không đánh dấu tính năng đã triển khai từ plan này.

**Yêu cầu phân tích mới — blocked gate report:** [plan điều phối agent có bằng chứng](../261010-agent-evidence-analysis/plan.md) thay thiết kế one-shot/rationale ngắn/research chỉ ngoài luồng. Mỗi job mới phải có feed, phân tích sơ bộ, Google/sách nguồn đọc thật, diagnostic criteria và bài tổng hợp đầy đủ. Phần lesson/admin APPROVED vẫn giữ riêng; nguồn mới của job không tự thành bài học APPROVED. Các pass/build pilot cũ bên dưới không nghiệm thu pipeline mới; không chặn ingestion/tự train/quản trị đã có.

## Mục tiêu

Cho người dùng chọn snapshot, mốc t, giá mua P và nhận bài phân tích thử nghiệm về giá sau30 phút so với P. Backend khóa feed6h hợp lệ, main điều phối analyst → research Google/tài liệu → tool kiểm criteria → synthesis có nguồn/phản biện. Giữ library APPROVED làm nguồn đã duyệt, nguồn tra mới là evidence riêng có access/hash/provenance và nhãn chưa duyệt. Train cũ độc lập; vote không đi vào prompt/training. Không chọn model thắng hoặc hứa accuracy trước đo prospective.

## Bất biến và phạm vi

- Nến input là BTCUSDT Spot `1m`/`5m`, cửa sổ cố định **6 giờ trước `t`** (~360/72 nến khi đủ), mọi nến đã đóng và `available_at <= t`; snapshot 2 ngày không cho phần sau `t` vào prompt. Chọn mốc gần đầu snapshot thiếu 6h: backend báo `INSUFFICIENT_HISTORY` **trước khi gọi provider**, không nhầm với `ABSTAIN` do model trả lời và không lén dùng tương lai. MVP API chỉ horizon **30m**; Replay cũ cho horizon khác vẫn `NO_MODEL` nếu thiếu model đúng bài toán, không giả mở rộng.
- Tóm tắt/context là **định dạng do dự án định nghĩa**, không phải nhãn AI tự train: bản A gồm OHLCV có thứ tự, bản B là ít phép tính deterministic kèm công thức/source bars và vài nến cuối; thử A/B để biết cách nào hữu ích. Backend tính/serialize, không tạo “mẫu hình đã chứng minh” hay % giả.
- Nghiên cứu **trong từng job** là bước bắt buộc của pipeline mới: tìm định nghĩa/phương pháp/mẫu và phản biện bằng Google + đọc nguồn thật, không tìm outcome phiên BTC đang chấm. Catalogue lesson/admin duyệt vẫn có, không thay nghiên cứu per-job. Nguồn ad hoc giữ riêng và chưa duyệt, không auto APPROVED.
- Nhiều call có vai/phiên bản/usage rõ (analyst, grounded research, trích criteria JSON, synthesis), cuối cùng UP/DOWN/ABSTAIN và **bài đầy đủ**, không giới hạn ba câu. probability=null đến khi kiểm định riêng. Giữ key/admin/budget/quota hiện có; 10 key không tăng project quota. Chưa có capability/key thật thì chưa nghiệm thu Google hoặc model call.
- Nhận định **hồi cứu** từ model hiện nay có nguy cơ trọng số đã học tương lai; banner rõ “minh họa hồi cứu”, không gọi historical OOS sạch. **Prospective** lưu dự báo trước outcome rồi mới chấm, dùng để so baseline. Vote của người lưu riêng, không dùng để train model hay để AI dự đoán lần sau. API/UI giữ timestamp UTC epoch ở BE/DB, UTC+7 ở FE.
- `NO_MODEL` của nhánh artifact tự train vẫn trung thực; luồng API có nhãn riêng **thử nghiệm**. Không auto trade, P&L, lời hứa thắng thị trường hay đường tắt mở khóa Phase 02 model point-price cũ.

## Phân vùng BE/FE khi triển khai (chưa có mã mới)

| Tầng | Vị trí dự kiến | Trách nhiệm |
|---|---|---|
| Train giữ lại | `backend/shootingstar/application/training/` | Chuyển `experiment`, `labels`, `modeling`, `splits` sau refs/callers/tests; giữ CLI và output cũ đúng nghĩa close-to-close |
| Chung | `backend/shootingstar/domain/`, storage + `adapters/db/`, `application/replay.py`, `application/features.py` nếu còn dùng chung | Candle, snapshot hash, `available_at`, outcome và vote riêng; không nhân bản logic |
| Phân tích API | `backend/shootingstar/application/external_analysis/` | Lấy nến 6h, kiểm input, đóng gói A/B, prompt, schema verifier, job lock và trưởng thành outcome |
| Provider keys | `backend/shootingstar/adapters/model_api/` | Gemini adapter, key slots tối đa 10, failover an toàn, quota/project, usage/cost, lỗi, không lộ secret |
| Bài học và research | `application/external_analysis/research_agent.py`, `api/`, `adapters/db/`, frontend lessons | Catalogue/admin giữ PENDING→APPROVED riêng; per-job research có Google/read-source trace, không tự duyệt nguồn |
| Replay FE | `frontend/src/features/replay/`, `frontend/src/app/api/` | Điểm mua → stages và bài đầy đủ + chart che → vote khóa → tự kết quả + vùng mở/highlight; proxy an toàn, không client metric |
| Kiểm chứng | `tests/test_causal_replay.py`, `tests/test_api_and_ui.py`, test adapter/repository, browser smoke | Không nhìn trước, key không lộ, lesson revision, rate limit, UX trên snapshot thật, prospective report |

## Hành trình người dùng — nghiệm thu được, không phải wireframe rỗng

1. Chọn snapshot có đủ 6h nến trước mốc muốn thử; click biểu đồ hoặc nhập UTC+7/giá P, horizon 30m. Chart zoom bằng cuộn, pan bằng giữ chuột trái; hiện đoạn 6h sử dụng, giá quan sát khác P và lý do thiếu nến. Không đủ input → không tốn tiền gọi Gemini.
2. Bấm **Phân tích với Gemini (thử nghiệm)** tạo một job; BE chạy các vai/call tuần tự, FE hiển thị stage và bài đầy đủ (nguồn/criteria/phản biện/giới hạn). Google thật và nguồn đã đọc có trace; thiếu source/capability thì RESEARCH_INCOMPLETE, không fake READY. Banner hồi cứu và không % giả vẫn giữ.
3. Bấm **Tôi dự đoán** UP/DOWN: khóa vote riêng; người xem AI trước khi vote nên không gọi so sánh mù. AI không học từ lựa chọn này.
4. Lưu vote thành công **tự sang bước4 và tự reveal**, không bấm “Xem kết quả” thêm; mở vùng t→t+30m/highlight/đánh dấu điểm mua và nến kết quả khi đủ dữ liệu. Hồi cứu có caveat; prospective giữ PENDING trước khi đủ thời gian/nến; thiếu/gap UNSCORABLE. Không dùng outcome sửa bài đã khóa hoặc chạy provider lại; GET trước reveal ẩn outcome.
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
