# Phase 01 — Đánh giá provider trước khi tích hợp

**Trạng thái:** PENDING; chỉ nghiên cứu tài liệu, chưa có kết quả thực nghiệm. [Kế hoạch](plan.md) · [Nguồn và lý do chọn ứng viên](../../external-model-forecast-design.md).

## Mục tiêu

Quyết định có đáng dùng API ngoài, chọn ứng viên để thử **theo dữ liệu đo**, không theo ấn tượng 'model mạnh'. Nghiên cứu hiện có cho thấy Gemini Flash, OpenAI và Claude đều hỗ trợ output có schema, không chứng minh ai dự báo BTCUSDT tốt hơn.

## Quy trình

1. Chốt 2 ứng viên ban đầu: Gemini Flash và một model dòng tiết kiệm của OpenAI **hoặc** Claude. Ghi đúng model ID/phiên bản và bảng giá tại thời điểm chạy; kiểm tra key, điều khoản dữ liệu free/paid và khả năng giới hạn ngân sách. Chưa cấp key thì chỉ đánh giá giấy tờ, không tuyên bố winner.
2. Định nghĩa đầu vào giống hệt: BTCUSDT Spot, timeframe 1m/5m, lịch sử nến đóng trước `t`, giá mua giả định, horizon. Chốt quy tắc chọn mẫu, nến thiếu, click giữa nến, giá sau horizon và ngưỡng/định nghĩa UP/DOWN/UNSCORABLE **trước** khi so model. Không dùng trả lời người dùng làm nhãn.
3. Chốt schema `UP | DOWN | ABSTAIN`, rationale ngắn, không yêu cầu xác suất; cùng prompt/template cho từng nhà cung cấp ở mức tương đương; không dùng live search/web grounding hoặc dữ liệu tương lai. Nhãn kết quả và điểm số tính trong backend, không tin output LLM tự chấm.
4. Ghi riêng thử nghiệm hồi cứu (có nguy cơ kiến thức tương lai trong trọng số) và thử nghiệm prospective (khóa trước khi kỳ hạn đóng). Chỉ prospective dùng để đánh giá khả năng dự báo nhân quả; lịch sử chỉ có giá trị kiểm tra UX/định dạng và không gọi OOS hợp lệ.
5. Chốt baseline trước: luôn UP, đa số lịch sử **chỉ tính từ quá khứ**, và nếu phù hợp một baseline close-to-close được sửa định nghĩa theo giá mua. Báo số mẫu, tỉ lệ UP/DOWN/ABSTAIN, accuracy trên những lần có dự báo kèm coverage, latency, lỗi provider, chi phí thực tế theo usage; không tính tỷ lệ đúng của tập ABSTAIN như thể đã dự báo. Nếu sau này có xác suất đã hiệu chỉnh thì thêm Brier/calibration ở một vòng đo riêng.
6. Chia dữ liệu cho việc chọn prompt/ứng viên và phần đánh giá cuối; không xem kỳ đánh giá rồi sửa prompt và tái sử dụng để tuyên bố thắng. Không đủ số mẫu/thời kỳ: báo không đủ bằng chứng, tiếp tục thu thập theo kỳ hạn hợp lệ thay vì fake kết luận.

## Gate / bằng chứng

- [ ] Có văn bản chốt định nghĩa `(t, P, horizon)`, gap, nến kết quả, tiêu chí chất lượng, ngân sách API và quyền gửi dữ liệu cho nhà cung cấp.
- [ ] Có bản ghi request/response, version, hash/cutoff, usage/chi phí thật; không lộ key hoặc tương lai trong prompt.
- [ ] Có báo cáo so baseline với số mẫu thực theo horizon và phân biệt hồi cứu/prospective; chưa đủ dữ liệu thì kết luận **chưa đủ dữ liệu**.
- [ ] Quyết định tiếp tục/không tiếp tục có căn cứ, không gọi model nào 'tốt nhất' khi chưa có phép đo.

**Bước tiếp:** Chỉ sau gate này mới triển khai [Phase 02](phase-02-experimental-integration.md) ở nhãn thử nghiệm.
