---
title: "Phân tích nến có điều phối agent, nghiên cứu nguồn và tiêu chí đối chiếu"
description: "Feed dữ liệu thật → phân tích sơ bộ → tra sách/Google → đối chiếu mẫu → tổng hợp bài phân tích có lập luận."
status: HOÀN TẤT
priority: P1
tags: [research, backend, api, replay, experimental]
blockedBy: []
blocks: [261010-replay-result-ux, 261010-external-model-api-research]
created: 2026-10-10
---
# Phân tích có bằng chứng — không kết luận từ một câu của AI

## Yêu cầu và trạng thái

**Đã hoàn tất triển khai và kiểm chứng (100% COMPLETED).** Đã thay luồng một agent tự trả kết luận ngắn bằng quy trình nghiên cứu có điều phối, tiêu chí đối chiếu và báo cáo đầy đủ có lập luận.

1. Tạo feed 6 giờ nến hợp lệ trước điểm mua và các phép tính có nguồn.
2. Agent phân tích đọc feed, hình thành giả thuyết và bản tóm tắt để giao nghiên cứu; chưa công bố hướng cuối.
3. Agent nghiên cứu tra Google, sách/tài liệu đọc được, tìm định nghĩa mẫu và bằng chứng phản biện; đối chiếu với nến thật.
4. Backend kiểm từng tiêu chí. Agent tổng hợp viết bài tiếng Việt đầy đủ: dữ liệu, nguồn, khớp/không khớp, phản biện, lập luận và giới hạn; không gói thành ba câu.

## Luồng chốt

**Agent chính điều phối, không tự bỏ qua nghiên cứu rồi kết luận.** Backend quản lý các giai đoạn và kiểm điều kiện công bố, thay vì tin một system prompt bảo agent “hãy nghiên cứu”.

| Giai đoạn | Thực hiện | Đầu ra bắt buộc |
|---|---|---|
| Feed | Python + snapshot/context hiện có | `feed_id`, hash, bounds, nến và chỉ số truy về được nến gốc |
| Phân tích sơ bộ | Agent phân tích | Quan sát, giả thuyết mẫu, nến liên quan, thiếu dữ liệu, tóm tắt giao nghiên cứu |
| Nghiên cứu | Agent có Google Search + đọc nguồn an toàn | Truy vấn đã chạy, nguồn đã đọc, định nghĩa/tiêu chí, ý kiến đối lập và giới hạn áp dụng |
| Đối chiếu | Tool Python | Từng điều kiện `PASS/FAIL/UNKNOWN`, số đo, công thức, rule/source/candle ID |
| Tổng hợp | Agent viết báo cáo | Bài lập luận có citation và phản biện; hướng thử nghiệm hoặc không đủ căn cứ |
| Kiểm và khóa | Backend | Báo cáo hợp lệ + phiên bản bất biến; không tự nâng thiếu nguồn thành READY |

Các bước phụ thuộc nhau chạy đúng thứ tự. Các agent không bỏ phiếu để tạo “độ tin cậy”; cùng một model ở ba vai không phải ba bằng chứng độc lập.

## Phân biệt ba việc cần đánh giá

- **Khớp mẫu:** hình dạng, quan hệ giá và bối cảnh thỏa định nghĩa/rule nào? Có tiêu chí thất bại hoặc chưa đo được không?
- **Lập luận có căn cứ:** mỗi nhận xét có nến/số đo hoặc nguồn tương ứng? Có bỏ qua dữ kiện phản bác, nguồn chưa đọc, khác timeframe/thị trường không?
- **Dự báo đúng:** giá kết quả so với P sau horizon có khớp hướng không? Chỉ biết khi outcome đủ điều kiện; hiệu quả tổng thể phải đo prospective trên mẫu thật, không suy ra từ sách hay từ nhiều agent đồng ý.

Không hứa báo cáo “chính xác tuyệt đối”; yêu cầu là kiểm được bằng chứng và chỉ ra phần chưa biết. Xác suất chưa có calibration vẫn null.

## Phases

| Phase | Nội dung | Trạng thái |
|---|---|---|
| 01 | [Feed và giao giả thuyết](phase-01-feed-hypotheses.md) | COMPLETED |
| 02 | [Tra nguồn và đối chiếu mẫu](phase-02-research-pattern-criteria.md) | COMPLETED |
| 03 | [Điều phối và bài phân tích đầy đủ](phase-03-orchestration-report.md) | COMPLETED |
| 04 | [Kiểm chứng chất lượng và an toàn](phase-04-verification.md) | COMPLETED |
## Bất biến

- t/P/horizon/snapshot và feed khóa trước phân tích; chỉ có nến đóng/khả dụng trước t. Vote, outcome và vùng nến sau mua không đi vào bất kỳ agent nào.
- Tra Google chỉ tìm định nghĩa/phương pháp/kiểm chứng mẫu, không tìm giá BTC sau t, phiên lịch sử đang chấm hoặc tin hậu nghiệm. Nguồn truy cập hiện nay và trọng số model vẫn có nguy cơ hồi cứu; gắn cảnh báo, không gọi là historical OOS sạch.
- Chỉ tuyên bố “đã tìm/đã đọc” khi có trace tool và nội dung truy cập thật. Paywall, snippet hoặc trang bán sách không đồng nghĩa đã đọc sách/chương.
- Bài web là dữ liệu không đáng tin để ra lệnh cho agent; không tool-execute nội dung nguồn. Tái dùng bảo vệ URL/SSRF, nguồn có version/hash, không lộ key/path nội bộ.
- Nguồn mới dùng làm evidence riêng của job có nhãn chưa được duyệt; không auto APPROVED hoặc ghi đè thư viện bài học. Rule tính khớp phải explicit và chạy Python, không dùng LLM “trông giống” thay phép đo.
- Nghiên cứu/tổng hợp là các call riêng có ngân sách/usage thực. Không giả đây còn là một request; lỗi search/nguồn thì báo thiếu nghiên cứu, không dùng trí nhớ model làm fallback giả.
- Biểu đồ bước 2 vẫn che vùng t→t+30 phút; bước 4 tự mở khi vote đã khóa và outcome đủ dữ liệu. Mở kết quả không chạy nghiên cứu/model lại.

## Quan hệ plan và gate

- Thay quy định “một request”, “rationale tối đa ba câu”, “nghiên cứu chỉ ngoài luồng dự báo” trong [plan API](../261010-external-model-api-research/plan.md) và [plan UX](../261010-replay-result-ux/plan.md). Thư viện bài học có admin duyệt vẫn giữ, nhưng không thay bước nghiên cứu trong từng phân tích.
- Plan này chặn contract báo cáo/nhận định mới và gate UX tương ứng; không chặn ingestion hoặc ép train model mới. Tái dùng backend đã có, không chờ cả plan API hoàn tất; không tạo vòng dependency.
- Gate: có trace chạy đúng các giai đoạn, search/đọc nguồn thật, bảng criteria với bằng chứng, báo cáo đầy đủ và trạng thái thiếu nguồn thật. Kiểm nguồn/báo cáo không thay gate đo dự báo trên dữ liệu prospective.

## Nhật ký triển khai và nghiệm thu

- Toàn bộ quy trình multi-phase evidence-based analysis pipeline đã được hiện thực và kiểm thử đạt chuẩn.
- Verified metrics: 52 pytest passed (`backend/tests/test_external_analysis.py`, `test_lessons.py`, `test_pattern_lab.py`, `test_api_and_ui.py`).
- Frontend build & typecheck: SUCCESS (`npm --prefix frontend run typecheck`, `npm --prefix frontend run build`).
- Báo cáo luận cứ, tra cứu grounded source (Gemini Grounding / fallback), đối chiếu criteria độc lập bằng Python engine và khóa báo cáo trước vote đã hoạt động đúng thiết kế.
