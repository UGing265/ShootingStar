# Phase 04 — Chấm thử nghiệm 30 phút và quyết định model

**Trạng thái:** PENDING, sau [Phase 03 — UX và bài học](phase-03-lesson-review-ux.md). [Plan](plan.md). Đây là **báo cáo tương lai thật**; không dùng replay hồi cứu để tự công bố chiến thắng.

## Cách đo

1. Chốt trước ngày bắt đầu: model ID/phiên bản, prompt/context A hoặc B, version lesson catalog, snapshot/timeframe, 6h input, ngân sách, khoảng lấy mẫu prospective, số mẫu tối thiểu, xử lý `ABSTAIN` và baseline. Không điều chỉnh sau khi xem outcome rồi dùng cùng cohort để tuyên bố thắng.
2. Với mỗi dự báo prospective: lưu request metadata/context hash và output bất biến **trước khi** giá của `t+30m` được phép xem; phiên bản model/lesson và key index (không secret). Backend trưởng thành outcome theo nến đã đóng hợp lệ, so giá sau 30m với **P do người dùng nhập**; thiếu nến/gap/giá ngang ngưỡng quy định → `PENDING/UNSCORABLE` kèm lý do. Không tự tạo P&L hay lợi nhuận không có phí/trượt giá.
3. Tính theo số mẫu thật và từng timeframe: số job, được chấm, thiếu dữ liệu, UP/DOWN/ABSTAIN, coverage, accuracy có mẫu số rõ, sai số nếu có quy tắc thống kê được chốt, latency và chi phí thực; baseline *luôn UP* và *đa số tính chỉ từ lịch sử trước thời điểm dự báo*. Nếu không đủ mẫu thì hiển thị **chưa đủ bằng chứng**, không tự nhận 'Gemini dự báo tốt'.
4. So Gemini với ứng viên đối chứng **chỉ nếu** đã thử cùng rule/cùng thời kỳ & ngân sách cho phép; ghi mọi khác biệt về prompt/context/version và không lén chọn cấu hình trên kỳ đánh giá cuối. Báo cáo API inference tách biệt với nhánh tự train close-to-close và với “minh họa hồi cứu”.

## BE/FE và giao nhận

- BE `backend/shootingstar/application/external_analysis/` chạy maturation/report có truy vết theo job/version; DB repository chỉ dùng dữ liệu đã persist, không lấy vote của người làm nhãn AI. API read report trong `backend/shootingstar/api/` chỉ trả metrics thật và mẫu số; không trả secret, path nội bộ hoặc dữ liệu riêng chưa duyệt.
- FE thêm thẻ báo cáo trên trang nghiên cứu/replay (`frontend/src/features/replay/` hoặc `research/` theo convention khi triển khai): rõ **‘Dự báo thử nghiệm — prospective’**, thời gian đo UTC+7, số mẫu đạt gate, bảng so baseline, tỷ lệ ABSTAIN, phí/lượt; không trộn bảng hồi cứu; empty state “Chưa đủ dự báo đã trưởng thành”.
- [ ] Có log khóa trước outcome, báo cáo bằng truy vấn thật cùng một protocol, không có kết quả gán lại sau reveal.
- [ ] Test cutoff/maturation/sai thiếu nến, baseline không dùng dữ liệu tương lai, chi phí và mẫu số; smoke CLI/API/report bằng job thật.
- [ ] Nếu kết quả yếu/không đủ: vẫn là *thử nghiệm*, ABSTAIN hoặc vô hiệu hóa phát số liệu; không chuyển sang trạng thái model đã kiểm định và không mở khóa artifact cũ.
