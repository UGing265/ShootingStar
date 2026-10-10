---
title: "Replay: nhận định dễ hiểu, preview biểu đồ và kết quả tự mở"
description: "Làm rõ nhận định AI, bổ sung biểu đồ đối chiếu và bỏ lần bấm xem kết quả sau bước 3."
status: pending
priority: P1
tags: [frontend, backend, api, experimental]
blockedBy: [261010-agent-evidence-analysis]
blocks: [261009-historical-replay-research, 261010-external-model-api-research]
created: 2026-10-10
---
# Replay — nhận định dễ hiểu và kết quả tự mở

## Trạng thái và phạm vi

**Chỉ lập kế hoạch. Chưa triển khai, chưa nghiệm thu.** Người dùng yêu cầu dừng sửa code. Các hunk triển khai tạm của lượt này đã được loại bỏ; những thay đổi source khác có sẵn/phát sinh ngoài công việc lập plan được giữ nguyên, không restore toàn file. Không chạy test/build, không tạo job AI hoặc gửi dự đoán để chứng nhận tính năng.

**Cập nhật yêu cầu nghiên cứu:** phần nhận định/report mới đang **blocked** bởi [pipeline agent có bằng chứng](../261010-agent-evidence-analysis/plan.md). Người dùng không muốn một câu kết luận tự phát hoặc bài tối đa ba câu: cần main điều phối feed → phân tích sơ bộ → tra sách/Google → đối chiếu criteria → agent tổng hợp viết bài đầy đủ. Chart/mask/auto-result giữ nguyên; scope nghiên cứu mới thay phần rút gọn trước đó.

Ba yêu cầu:
1. Người dùng hiểu AI đang đoán điều gì, vì sao và mức giới hạn của nhận định.
2. Có preview biểu đồ tại phần nhận định AI và phần kết quả thực tế.
3. Lựa chọn ở bước 3 lưu thành công thì tự sang bước 4 và tự tải kết quả; không bấm “Xem kết quả” thêm lần nữa.

Không tự train/chọn model mới, auto trade, P&L hoặc mở rộng horizon Gemini. Theo yêu cầu bổ sung, có pipeline nhiều vai phân tích–nghiên cứu–tổng hợp; không dùng các agent bỏ phiếu để thay bằng chứng.

## UX chốt cho plan

- **Bước 2:** tiến trình từng vai, sau đó tóm tắt và **bài phân tích đầy đủ** với nguồn đã đọc, số đo, bảng tiêu chí khớp/không khớp/chưa rõ, lập luận và phản biện. Không giới hạn ba câu. Nêu rõ giá so với P và horizon; giá dùng chấm là đóng cửa của nến hệ thống chọn, không phải giá chính xác từng giây. Thiếu research nói rõ, không một câu từ main thành report READY.
- **Vùng dự đoán trên chart bước 2:** đánh dấu điểm mua (t, P); chỉ thấy nến quá khứ bên trái. Bên phải giữ chỗ từ t tới t+30 phút nhưng che toàn bộ đồ thị/khối lượng/tooltip tương lai, nhãn “Vùng dự đoán — chưa mở”. Che theo thời gian, không theo mức giá.
- **Bước 3:** nút “Tôi đoán tăng/giảm” ghi lựa chọn rồi tự mở bước 4. Chú thích trước nút: “Chọn xong sẽ lưu dự đoán và hiển thị kết quả. Bạn không thể đổi lựa chọn đã lưu.”
- **Bước 4:** hiện đang tải ngay; đủ dữ liệu thì mở vùng đã che, highlight đoạn từ mua tới +30 phút, đánh dấu điểm mua và điểm kết quả trên nến thật, kèm bảng đối chiếu. Giữ cùng khung thời gian để nhìn rõ trước/sau. Thiếu nến/lỗi thì giữ trạng thái chưa mở, nói rõ lý do; chỉ có “Kiểm tra lại”/“Thử lại”, không có thao tác mở kết quả lần hai. Nhánh nội bộ dùng horizon đã lưu thay vì hardcode 30 phút.
- Thông tin model, phiên bản prompt và cấu hình A/B nằm trong mục “Chi tiết kỹ thuật”, không chen vào lời giải thích chính.

## Bất biến

- Backend là nguồn giá kết quả, hướng và đúng/sai. Browser chỉ vẽ nến và hiển thị DTO.
- Preview AI chỉ có nến đã đóng/khả dụng tới thời điểm mua; phần sau mua là vùng thời gian trống được che, không tải tương lai rồi che bằng giao diện. Không lộ qua tooltip, volume, pan/zoom hoặc scale trục giá.
- Chart kết quả dùng snapshot, thời gian, giá và horizon của **job đã lưu**, không dùng form đã sửa hoặc snapshot đang chọn ở bước 1.
- Giữ cảnh báo: đây là nhận định thử nghiệm trên lịch sử; model có thể đã học thông tin sau mốc đang thử. Không gọi là dự báo lịch sử công bằng hoặc xác suất đã kiểm chứng.
- Nhận định đã lưu bất biến. Prompt mới có phiên bản mới; không dịch bằng nội dung tự bịa, không gọi model thêm lần để dịch hoặc đánh giá lại tự động.
- Đổi tab/thử lại reveal không tạo job mới, không gọi Gemini, không gửi lại vote. Kết quả `PENDING`/`UNSCORABLE` không chấm ĐÚNG/SAI.
- Hiển thị UTC+7; lưu và truyền UTC epoch. Chart có wheel zoom, drag pan, phân biệt drag/click, hoạt động sau đổi tab/resize.

## Phases

| Phase | Nội dung | Trạng thái |
|---|---|---|
| 01 | [Nhận định AI dễ đọc](phase-01-readable-analysis.md) | Pending |
| 02 | [Biểu đồ preview và đối chiếu](phase-02-chart-preview.md) | Pending |
| 03 | [Tự mở kết quả sau lựa chọn](phase-03-auto-result.md) | Pending |
| 04 | [Kiểm chứng và cập nhật tài liệu](phase-04-verification.md) | Pending |

Thứ tự: contract/ngôn ngữ ở Phase 01; chart ở Phase 02; tích hợp điều hướng ở Phase 03; nghiệm thu cả luồng ở Phase 04. Một người sở hữu `replay-player.tsx` xuyên ba phase, không cho worker ghi đồng thời file này.

## Quan hệ plan

- Chặn **gate UX Replay Phase 03**, không chặn ingestion/nghiên cứu còn lại, của [historical replay](../261009-historical-replay-research/plan.md) và [external model API](../261010-external-model-api-research/plan.md).
- **Blocked report/nhận định mới:** [plan điều phối–nghiên cứu](../261010-agent-evidence-analysis/plan.md) sở hữu backend stages/nguồn/criteria/report; UX tích hợp progress/bài viết/citations, không tự tạo pipeline song song. Không cần chặn chart riêng, ingestion hoặc toàn bộ API cũ.
- Yêu cầu ngày 2026-10-10 thay chỉ dẫn cũ phải bấm “Xem kết quả”. Hai plan liên quan được cập nhật `blockedBy` và ghi rõ thay đổi này.
- API/proxy/chart cơ bản đã tồn tại trong source; không đợi toàn bộ hai plan lớn hoàn tất mới thực hiện UX này. Gate key thật/độ chính xác prospective của plan API vẫn giữ riêng.
- `plans/` và `docs/development-rules.md` không có trong cây đã kiểm tra; dùng `docs/plans/` và quy chuẩn dự án đang có. Không tạo convention thứ hai.

## Nghiệm thu cuối

- Người dùng đọc được câu trả lời cho: AI đoán cao/thấp hơn giá nào, sau bao lâu, dựa trên nến nào, và điều gì chưa được chứng minh.
- Bài phân tích mới có feed/evidence, nghiên cứu thật, bảng criteria và phản biện; hướng cuối chỉ sau các stage/gate. Ba câu/one-shot không còn tiêu chí nghiệm thu, bài dài không tự chứng minh accuracy.
- Bước 2/4 đều có chart đúng job: bước 2 che vùng sau điểm mua nhưng giữ mốc +30 phút; bước 4 mở vùng, highlight khoảng dự đoán và đánh dấu hai điểm khi đủ dữ liệu. Thiếu dữ liệu không được mở hoặc dựng kết quả giả.
- Chọn dự đoán một lần: lưu thành công, tự bước 4, tự tải kết quả. Lỗi reveal không làm mất lựa chọn hoặc gọi model lại.
- Hai nhánh Gemini thử nghiệm/model nội bộ được kiểm tra; nhãn thời lượng lấy từ job, không hardcode 30 phút cho nhánh nội bộ.
- `npm run typecheck`/build và backend contract tests chạy trong DB riêng; browser smoke trên snapshot thật. Chỉ đánh dấu hoàn tất khi có output, không coi plan này là bằng chứng chạy được.

## Nhật ký lập kế hoạch

Ảnh người dùng là bằng chứng UX khó đọc/thiếu chart/thừa nút. Đã đối chiếu renderer, vote/reveal, prompt và DTO hiện tại; dừng triển khai theo yêu cầu mới. Không thay đổi provider, quota, DB hay kết quả đã lưu. Không commit/push.
