# Phase 01 — Ngôn ngữ và contract trình bày

## Context và trạng thái
[Plan](plan.md). Priority P1; Complete. Không đổi công thức, hash hay dữ liệu job cũ.

## Kiến trúc
Feed canonical → context trình bày deterministic tại backend → prompt tổng hợp mới. Context đọc cho người không thay feed thô; không gửi vote/outcome hoặc nến sau t. Backend tính feature; định dạng phần trăm là đổi cách biểu diễn ratio, không phép đo mới.

## Files
Root tuyệt đối: `D:/AShiroru/ProgramCode/Project/Team/ShootingStar/`.
- Modify `backend/shootingstar/adapters/model_api/gemini_adapter.py`: synthesis nhận context dễ đọc; instruction cho toàn bộ bài và rationale, ví dụ số/giờ.
- Modify `backend/shootingstar/application/external_analysis/service.py`: khóa đúng version prompt mới trên job mới và truyền version đúng DTO; đọc references bằng LSP trước thay API/symbol xuất ra.
- Create `backend/shootingstar/application/external_analysis/report_presentation.py`: glossary và format deterministic từ feed, không DB/network, chỉ dùng giá trị đã có. Chỉ một module, không framework template mới.
- Modify `backend/tests/test_external_analysis.py`: regression cho đơn vị và bất biến job nếu conventions phù hợp; không test source/prompt wording.
- Intentionally unchanged `context.py`, models/migrations, key manager, research matching, vote/reveal.

## Contract hiển thị
| Feature | Nhãn chính | Đơn vị/ý nghĩa |
|---|---|---|
| latest_close_vs_p_pct | Chênh lệch giá đóng cửa cuối với giá mua giả định | ratio → %, giữ dấu |
| range_high_6h / range_low_6h | Giá cao nhất / thấp nhất trong 6 giờ | USDT |
| volatility_6h_pct | Biên độ giá trong 6 giờ | ratio → %; không gọi độ lệch chuẩn |
| total_volume_6h | Tổng khối lượng trong 6 giờ | BTC |
| return_1h | Thay đổi giá trong 1 giờ gần nhất | ratio → %; không gọi lợi nhuận giao dịch |
| last_candle_body_ratio | Phần thân nến cuối | % tổng biên độ nến |
| last_candle_upper_wick_ratio / last_candle_lower_wick_ratio | Phần bóng trên / dưới nến cuối | % tổng biên độ nến |

- Ngày giờ `dd/MM/yyyy HH:mm:ss (UTC+7)`, chuyển bằng timezone rõ, không đổi timestamp gốc. Không làm tròn lên giây/phút kế tiếp ở cutoff.
- Giá USDT tối đa 4 chữ số thập phân theo độ chính xác feed; volume BTC tối đa 4; ratio hiển thị % đủ tới 4 chữ số thập phân cho feed đang round 6 decimals. Bỏ negative zero, giữ âm thật; null không thành 0; không làm số khác 0 thành 0 do format.
- Tên model/hash/IDs/công thức/version giữ nguyên cho technical details và citation, không dịch identifier gốc.
- Prompt: câu ngắn, tiếng Việt tự nhiên, đoạn có ý rõ, thuật ngữ giải thích lần đầu; không epoch/tên feature nội bộ làm nhãn chính. Viết nội dung section không lặp tiêu đề/đánh số UI. Cho Markdown đoạn/list/emphasis; không HTML/ảnh nhúng. Kết luận và giới hạn đầy đủ, không tự thêm xác suất/khuyến nghị lợi nhuận.

## Bước triển khai
1. Kiểm tra consumers/version prompt hiện có; chọn version mới theo convention sau refs, không để job mới mang `v1` nếu prompt đã đổi.
2. Tạo mapping chín feature; giá trị/unit lấy canonical. Field lạ/thiếu không suy nghĩa hoặc bịa số; lưu raw để kiểm tra.
3. Build context đọc cho người tại backend; giữ toàn bộ provenance và causal feed thô không đổi. Không nhân đôi danh sách nến trong prompt.
4. Bổ sung instruction trong synthesis; các vai analyst/research không đổi mục tiêu hoặc quy trình. Chỉ thay các đoạn ngôn ngữ bị người đọc nhìn thấy nếu cần, cùng version tương ứng.
5. Job cũ không migrate/rewrite/re-generate. Format presentation là view, không phải một AI prediction mới.

## Kiểm chứng
- Regression deterministic: ratio âm nhỏ/zero, giá/volume, thiếu field; giờ UTC gần chuyển ngày sang UTC+7; snapshot/feed trước và sau formatter giữ nguyên giá trị/hash.
- Smoke context với feed job thật, không gọi paid API chỉ để thử formatting. Nếu cần kiểm chứng ngôn ngữ synthesis thật, chạy một job mới được phép; ghi model/version/sections, không dùng nó làm bằng chứng accuracy.
- `pytest backend/tests/test_external_analysis.py backend/tests/test_api_and_ui.py` qua DB test riêng; không override DB config để dùng production.

## Checklist và rủi ro
- [x] Glossary/đơn vị đúng; negative zero xử lý đúng.
- [x] Version mới chỉ job mới; raw immutable.
- [x] Smoke và tests có output, không có nến/outcome tương lai trong context.
- Risk: model vẫn có thể viết số sai. Phase 02 dùng canonical cho khối dữ liệu, không tin AI tự thuật như nguồn số liệu.
- Risk: tính lại feature ở client. Chỉ format số API; không copy công thức.

## Tiếp theo
Phase 02 dùng mapping/format contract này để trình bày báo cáo cũ và mới.
