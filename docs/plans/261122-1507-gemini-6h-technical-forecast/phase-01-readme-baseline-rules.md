# Phase 01 — README: luật so sánh (baseline)

**Worker:** command-code flash · **Ưu tiên:** trung bình · **Trạng thái:** pending

## File sở hữu
- `README.md` (root) — chỉ thêm 1 mục, không sửa phần khác.

## Nội dung cần thêm (mục "Chấm điểm dự đoán: so với luật đơn giản")
- Mỗi mốc t, 3 bên cùng đoán giá t+6h cao hơn hay thấp hơn giá mua P:
  - **Luật luôn TĂNG:** không nhìn dữ liệu, luôn đoán TĂNG.
  - **Luật theo đà 6h:** close(t) > close(t−6h) → TĂNG, ngược lại GIẢM.
  - **Gemini:** phân tích kỹ thuật từ digest Python.
- Hai luật chạy độc lập, không nhìn câu trả lời Gemini, Python tính, không tốn API.
- Chấm: |Δ| < 1% so với P = đi ngang, không chấm.
- Gemini chỉ có giá trị khi thắng rõ cả hai luật trên nhiều trăm mốc.
- Bảng ví dụ 3 lượt (copy từ brainstorm: lượt 1 60.000→61.000, thực tế 62.000; lượt 2 62.000→61.000, thực tế 60.000; lượt 3 60.000→60.500, thực tế 61.500; kết quả 2/3, 3/3, 2/3).
- Ghi chú: mốc trước 2025-02 có thể bị Gemini "nhớ" giá → thống kê tách riêng.
- Nguồn: Hewamalage et al. https://arxiv.org/pdf/2203.10716 ; Hyndman & Koehler 2006 https://www.doi.org/10.1016/J.IJFORECAST.2006.03.001

## Ràng buộc
- Tiếng Việt, ngắn, không em/en dash trong văn bản. Không đổi phần khác của README.

## Nghiệm thu
- `git diff README.md` chỉ có mục mới; bảng render đúng markdown; số trong ví dụ khớp.
