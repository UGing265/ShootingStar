# Các hướng đi tổng thể cho dự đoán BTCUSDT

Ngày: 2026-11-22 · Trạng thái: **đang giữ hướng A**, các hướng khác để user cân nhắc sau.

## Vì sao có tài liệu này
Buổi brainstorm ngày 2026-11-22 chỉ đưa 3 phương án, cả 3 đều lấy Gemini làm người dự đoán. Tiền đề "Gemini dự đoán" chưa được chất vấn. Tài liệu này ghi đủ các hướng khác để quyết bằng số liệu, không bằng lý lẽ.

## Số liệu thật đã có (snapshot 1m 2025-02-01 đến 2026-11-22, mốc cách 6h)
- 2.580 mốc; vùng đi ngang ±0.5% loại 1.307; còn 1.273 mốc chấm được.
- Luôn TĂNG 49,88% · Luôn GIẢM 50,12% · Theo đà 6h 46,50% · Ngược đà 6h 53,50% (CI 95% tính tay khoảng 50,8% đến 56,2%).
- "Ngược đà" tìm ra SAU khi nhìn dữ liệu, có nguy cơ data snooping; chưa trừ phí 0,2%/lượt.
- Biến động 6h trung vị 0,49%.
- **Gemini thật (2026-11-22, 158 job, 75 mốc chấm được, prompt forecast-6h-v1, lookback 14 ngày):** Gemini 37/75 = **49,3%** (CI 95% 38,3 đến 60,4). Cùng tập mốc: luôn TĂNG 38,7%, luôn GIẢM 61,3%, theo đà 36,0%, ngược đà 64,0%. Theo mức tự tin: LOW 6/15, MEDIUM 20/39, HIGH 11/21. Gemini đoán GIẢM 64% số lần.
- Kết luận tạm: chưa có dấu hiệu Gemini hơn tung đồng xu; thua luật đơn giản trên cùng tập; mức tự tin không phân biệt được. Mẫu còn nhỏ (±11%).

## Các hướng

| # | Hướng | Ai dự đoán | Lợi | Hại |
|---|---|---|---|---|
| A | **Gemini dự đoán** (đang làm) | LLM đọc digest chỉ số Python | Có lời giải thích tiếng Việt, trỏ chỉ số kiểm được | Tốn API; nghiên cứu nghiêng về LLM không hơn cách đơn giản cho chuỗi thời gian |
| B | Luật Python + Gemini chỉ diễn giải | Luật cố định (vd ngược đà 6h) | Miễn phí, đo ngay, ổn định | Luật chọn sau khi nhìn dữ liệu dễ ảo; phải kiểm trên giai đoạn tách riêng |
| C | Máy học đơn giản (logistic regression / gradient boosting) trên cùng digest | Model tự train | Rẻ, chuẩn khoa học, đo calibration được | Đi ngược quyết định đã gỡ tự train (`docs/plans/261121-remove-self-learning`); cần chia train/test theo thời gian |
| D | Gemini hỏi 3 đến 5 lần, lấy đa số | LLM nhiều lượt | Độ tự tin đáng tin hơn tự khai | Tốn gấp 3 đến 5 lần API |
| E | Gửi ảnh biểu đồ cho Gemini | LLM nhìn hình | Giống người đọc chart | Khó kiểm lý do, không trỏ được chỉ số |
| F | **Đổi câu hỏi:** đoán "có chạy mạnh không" (biến động) thay vì "lên hay xuống" | Bất kỳ | Biến động dự đoán được tốt hơn hướng đi (kết quả kinh điển, họ GARCH) | Không trả lời trực tiếp "mua hay bán" |
| G | Dựa vào tin tức | LLM đọc tin có timestamp | Có thông tin biểu đồ không có | Dự án riêng; cần nguồn uy tín, lọc `published_at <= t` |

## Phần dùng lại được cho mọi hướng
Digest Python (`application/forecast/`), luật so sánh, chấm điểm + vùng đi ngang, scoreboard, `forecast-batch`, snapshot gần 2 năm. Chỉ `stages/analyst_stage.py` gắn riêng với Gemini; đổi hướng là thay bước này.

## Tiêu chí quyết định (đề xuất)
1. Đo Gemini trên khoảng 300 mốc chấm được (khoảng 600 lượt gọi).
2. Gemini vượt rõ cả "luôn TĂNG" và "ngược đà 6h" (khoảng tin cậy không chồng) → giữ A.
3. Không vượt → Gemini chuyển sang vai trò giải thích (B); cân nhắc F.
4. Muốn chuẩn khoa học và chấp nhận mở lại tự train → C.
5. Kiểm "ngược đà" trên giai đoạn tách riêng (2025 và 2026) trước khi tin.

## Cách chấm điểm phụ có thể thêm (không tốn API, tính lại trên job đã lưu)
- Lời/lỗ nếu làm theo, trừ phí 0,2%: dùng cả mốc đi ngang, trả lời "làm theo có lời không".
- Chốt lời/cắt lỗ chạm trước (barrier, có sẵn `application/barrier_evaluation.py`).

## Nguồn
- Tan et al., NeurIPS 2024: https://arxiv.org/abs/2406.16964 (phạm vi: forecaster gắn LLM, không phải prompt đọc chỉ số)
- Xiong et al., ICLR 2024: https://arxiv.org/abs/2306.13063 (tự khai độ tin quá mức; hỏi nhiều lần tốt hơn)
- Wei 2024, IJFE: https://onlinelibrary.wiley.com/doi/full/10.1002/ijfe.2863 (TA crypto sau kiểm data snooping không có lời thật)
- arXiv 2410.06935 (ML + chỉ báo trên BTC khoảng 55 đến 65%, trần lạc quan)
- Hewamalage et al.: https://arxiv.org/pdf/2203.10716 (bắt buộc so baseline)

## Câu hỏi mở
- Có mở lại tự train cho hướng C không?
- Có muốn thêm "ngược đà 6h" làm baseline thứ 3 không?
- Có thêm điểm phụ lời/lỗ sau phí không?
