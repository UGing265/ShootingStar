---
title: "Nghiên cứu và thử model API ngoài cho Replay"
description: "So sánh Gemini/OpenAI/Claude với baseline bằng dữ liệu thật trước khi tích hợp nhận định thử nghiệm vào Replay."
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

Tìm cách cho người dùng nhận nhận định UP/DOWN từ API model ngoài **mà không ngụy nhận đó là xác suất đã kiểm định hoặc dự báo lịch sử không nhìn trước**. Đo model có ích hơn baseline hay không, chi phí/lượt và độ tin cậy thực tế; sau đó mới quyết định tích hợp. Không cần train lại mỗi lượt dự báo, nhưng không có bằng chứng model bên ngoài đã học đúng bài toán BTCUSDT Spot theo giá mua tùy ý.

## Ranh giới và bất biến

- Đầu vào `(snapshot, t, giá mua giả định, horizon)` và nến đóng khả dụng `available_at <= t`; không gửi nến/nhãn/outcome tương lai trong prompt. Dùng 1m hoặc 5m; `30m`–`24h` là horizon, không phải timeframe nến. UTC epoch trong API, hiển thị UTC+7.
- Tách **nhận định hồi cứu thử nghiệm** (API model hiện nay nhìn ngày xưa: không chứng minh tính nhân quả trọng số) với **dự báo tiến về phía trước** (lưu trước rồi chấm khi thị trường trưởng thành). Không gộp số liệu hai luồng.
- Dự báo API ban đầu chỉ `UP | DOWN | ABSTAIN`, không bịa xác suất. `probability_up/down` vẫn null nếu chưa được hiệu chỉnh và đánh giá. Không thay `NO_MODEL` của nhánh artifact tự train bằng một con số API.
- Chỉ backend gọi nhà cung cấp bằng key cấu hình local/admin; frontend không chạm key. Không cho API ngoài tính lại nhãn, outcome hoặc P&L; backend là nguồn sự thật.
- Khoá mỗi câu trả lời trước reveal; lưu phiên bản provider/model, prompt, snapshot/hash, thời điểm nến cuối, horizon, request/response và usage. Bảo vệ secret/đường dẫn khỏi public DTO.
- Không cam kết accuracy, tài chính, hay 'Gemini tốt nhất' trước khi so baseline trên dữ liệu đo được.

## Cấu trúc dự kiến khi triển khai (chưa tạo mã)

| Trách nhiệm | Điểm tích hợp dự kiến | Đầu ra |
|---|---|---|
| Lấy dữ liệu nhân quả | `backend/shootingstar/application/replay.py` + storage snapshot có checksum | Chỉ nến đóng trước mốc, giá mua và horizon |
| Gọi provider, cô lập key/usage | Adapter backend mới trong `backend/shootingstar/adapters/` | JSON theo schema `UP/DOWN/ABSTAIN`, lỗi minh bạch |
| Khóa, lưu, chấm nhận định | `backend/shootingstar/application/`, DB repository/migration nếu cần | Bản ghi lịch sử/tiến về phía trước bất biến, nhãn backend khi trưởng thành |
| Public API | `backend/shootingstar/api/` | Trạng thái thử nghiệm riêng, không giả `SimulationAIPredictionDTO` đã kiểm định |
| UI | `frontend/src/features/replay/` và Next.js proxy trong `frontend/src/app/api/` | Nhãn ‘API thử nghiệm’, hiển thị provider/version, không lẫn với model được kiểm định |
| Kiểm chứng | `tests/test_causal_replay.py`, `tests/test_api_and_ui.py` và test adapter mới | No-future-candles, lock-before-reveal, lỗi provider, key không lộ, đúng nhãn theo giá mua |

## Phases và gate

1. [Phase 01 — Đo lường & chọn cách thử](phase-01-evaluate-providers.md) — **pending**. Chốt quy tắc dữ liệu, ngân sách, chính sách lưu dữ liệu, hai ứng viên (Gemini Flash và một đối chứng OpenAI hoặc Claude), baseline, tiêu chí quyết định trước khi xem kết quả; chỉ kết luận sau khi thực sự có log và báo cáo.
2. [Phase 02 — Thử tích hợp có giới hạn](phase-02-experimental-integration.md) — **pending, phụ thuộc Phase 01**. Backend-only provider trial và UI ghi rõ *thử nghiệm*; prospective ghi trước kết quả và kiểm tra hợp đồng API. Không bật mặc định hay mở khóa xác suất đã kiểm định.

**Không thuộc kế hoạch này:** tự train/fine-tune, auto trade, gửi dữ liệu bí mật, dựng backtest 'đúng trước tương lai' bằng LLM hiện nay, hay thay thế Phase 02 tự train đang chưa nghiệm thu ở kế hoạch lịch sử. Chỉ đổi thứ tự ưu tiên nghiên cứu; không tự ý thay trạng thái kế hoạch cũ.

## Điều kiện bắt đầu và câu hỏi còn mở

- Trước khi thử API trả phí cần người vận hành cấp API key, xác nhận ngân sách tối đa và bậc dịch vụ/điều khoản dữ liệu; **chưa đòi nhập key ngay để viết thiết kế**.
- Ưu tiên bắt đầu với dự báo tiến về phía trước để đo nhân quả, hay xem minh họa hồi cứu trước? Có thể làm cả hai **với nhãn và báo cáo tách rời**.
- Chốt quy tắc nến khi click/gap và `t+horizon`, cửa sổ nến được phép gửi, horizon có thể chấm, tiêu chí chất lượng và số mẫu trước chạy thử.

## Kiểm tra tài liệu/khi triển khai

- [ ] Nguồn bảng giá/điều khoản vẫn đúng vào ngày chạy; dự toán không vượt ngân sách.
- [ ] Phase 01 có kết quả thật (hoặc ghi không đủ mẫu); không chọn provider bằng tập test đã xem.
- [ ] Phase 02 có test backend/API, smoke UI thực tế và kiểm chứng không lộ key; vẫn phân biệt nhận định thử nghiệm với `NO_MODEL` chính thức.
