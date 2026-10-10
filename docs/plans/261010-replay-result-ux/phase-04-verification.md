# Phase 04 — Kiểm chứng và cập nhật tài liệu

## Context và trạng thái

[Plan tổng](plan.md), [Nhận định](phase-01-readable-analysis.md), [Chart](phase-02-chart-preview.md), [Tự mở kết quả](phase-03-auto-result.md).

**Đã nghiệm thu và hoàn tất.** Đã chạy kiểm tra toàn bộ suite liên quan:
- `npm run typecheck`: Passed (0 errors).
- `npm run build`: Compiled successfully in 385ms, generated 15/15 routes.
- `pytest`: 36 test passed (10 domain contracts, 10 causal replay, 16 external analysis workflow & gates).
- Subagent code-reviewer (`ReplayUXReviewer`): Status clean, resolved edge cases, zero regressions.

## Tiền điều kiện an toàn

1. Backend/frontend chạy local theo `docs/backend/README.md`, `docs/frontend/README.md`. Dùng DB/schema riêng cho test; không để test rơi vào DB đang dùng.
2. Snapshot thực đã đăng ký, file còn tồn tại và checksum khớp; đủ 6 giờ nến trước mua và nến cần chấm. Chọn thêm điểm gần cuối snapshot để kiểm thiếu dữ liệu.
3. API có key/admin hợp lệ nếu nghiệm thu provider thật. Không đưa key vào plan, screenshot hoặc browser. Không có key thì ghi rõ thiếu bằng chứng ngôn ngữ response thật, không dùng demo làm bằng chứng Gemini tuân thủ.
4. Mock/dữ liệu dựng chỉ cho regression/kiểm lỗi mạng trong môi trường test, phải gắn nhãn. Browser smoke chính dùng snapshot thật; không tạo/chèn snapshot giả trong DB vận hành.

## Contract tests

Dùng interpreter trong môi trường backend đã cài dependency và **PostgreSQL test DB riêng** đã cấu hình theo `docs/backend/README.md`. Không chuyển suite hiện hữu sang SQLite cho gate này: [suy diễn từ migration/test] `audit_logs.id` dùng BIGINT, test insert không cấp id, có nguy cơ không tự tăng trên SQLite; không mở scope sửa DB dialect chỉ để qua nghiệm thu UX. Ví dụ PowerShell tại root, sau khi cấu hình `.env`:

```powershell
python -c "from shootingstar.adapters.db.session import get_database_url; from sqlalchemy.engine import make_url; a=make_url(get_database_url()); b=make_url(get_database_url(test_mode=True)); assert b.get_backend_name() == 'postgresql'; assert (a.host, a.port, a.database) != (b.host, b.port, b.database); print('PostgreSQL test database is separate')"
python -m pytest backend/tests/test_external_analysis.py backend/tests/test_api_and_ui.py backend/tests/test_causal_replay.py
npm --prefix frontend run typecheck
```

Trước chạy xác nhận interpreter là environment backend, test fixture đọc đúng TEST_DATABASE_URL; không in DB URL vận hành. Build nếu có thay đổi contract/import/render ảnh hưởng bundling:

```powershell
npm --prefix frontend run build
```

Regression lâu dài chỉ cho hành vi người dùng có thể gặp:

- Vote đã khóa: gửi lại cùng hướng không đổi; gửi hướng khác bị từ chối; reveal trước vote bị từ chối; job cũ đã reveal nhưng chưa vote không được nhận vote sau khi biết kết quả.
- Input A/B có t/P/h đúng; dùng fixture snapshot thật trong test để bắt payload tại đầu vào adapter: thay nến tương lai không làm nó lọt vào context, vote không có trong input. Browser network không nhìn thấy payload server gửi Gemini, không dùng screenshot chart làm bằng chứng context.
- Score external serialize đúng true/false/null; chưa reveal, PENDING, UNSCORABLE, ABSTAIN/thiếu prediction không bị chấm SAI.
- Nến kết quả chưa đóng/khả dụng trong prospective không được chấm sớm; kết quả đã chấm không bị thay khi mở lại.
- Job cũ giữ rationale/model/prompt version gốc.
- Bounds preview persist đúng context đã dùng; timestamp nến tham chiếu persist và qua mapper tới API, không lộ trước reveal. Job cũ thiếu metadata giữ null, không chấm lại hoặc đặt marker đoán.
- Timestamp local đi qua `SimulationOutcome` → `SimulationJob.to_dict`/JSON lưu → `SimulationJob.from_dict` → `_to_job_response` → DTO API với cùng giá trị; regression cho job mới và JSON job cũ không có trường này (null, không marker đoán). Kiểm hành vi lưu/đọc và API thật trong test, không test nguyên văn hoặc forwarding bằng mock echo.

Không test literal chữ UI/prompt, số dòng source, wiring/copy/forward hoặc mock echo. Không thêm framework test UI mới cho scope này; kiểm luồng bằng browser thật.

## Browser smoke — các kịch bản bắt buộc

| Kịch bản | Bằng chứng cần quan sát |
|---|---|
| Gemini phân tích đủ bước | Tiến trình từng vai hiển thị rõ; bài phân tích mới tiếng Việt đầy đủ có nguồn, bảng criteria và phản biện; chart/bounds metadata khớp job, giá mua và nến nhắc tới; không gọi provider ở browser. Chứng cứ context không có tương lai lấy từ contract test backend |
| Gemini B | UI nói rõ tóm tắt/chỉ số + nến cuối; không nói toàn chart được gửi; giữ cảnh báo |
| Bước 2 che vùng dự đoán | Điểm mua (t, P) rõ; bên trái chỉ nến quá khứ, bên phải t→t+30 phút có lớp che và nhãn. Không có nến/volume/tooltip/giá tương lai trong response dùng vẽ; trục giá không dựa vào tương lai; zoom/pan/resize không làm lộ |
| Nhận định cũ còn tiếng Anh | Nội dung giữ nguyên, nhãn/giới hạn tiếng Việt rõ; không tự gọi AI lại. Không coi bản cũ đã được dịch hoặc hứa prompt mới tuân thủ khi chưa kiểm response |
| Chọn tăng/giảm bước 3 | Một lần lưu; tự bước 4; loading rồi mở vùng đã che trên cùng khung thời gian, highlight đoạn mua→+30 phút, đánh dấu điểm mua và điểm kết quả; không bấm xem kết quả thêm |
| Lỗi reveal sau vote thành công | Hiện vote đã lưu; thử lại chỉ reveal; không call Gemini hoặc đổi vote |
| Vote chưa xác nhận/lỗi | Không mở outcome trước khi backend xác nhận; timeout kiểm job hiện có thay vì tạo job mới |
| AI ABSTAIN hoặc local NO_MODEL | Người vẫn xem được kết quả thị trường; AI ghi không dự đoán/chưa có model, không ghi SAI |
| Snapshot thiếu/gap tại horizon hoặc reveal lỗi | Vùng dự đoán giữ chưa mở/không có kết quả hợp lệ; vẫn có điểm mua và mốc thời gian horizon. PENDING/UNSCORABLE/lỗi có lý do, không dựng giá/marker kết quả hoặc điểm giả |
| Nội bộ horizon 1h/4h/24h | Nhãn theo job và chart chứa cả mua/kết quả; không hardcode “sau 30 phút” |
| Mua giữa nến hoặc giá ngoài range | Marker đúng thời điểm/giá; giá đóng nến tham chiếu được phân biệt với giá intrabar chính xác |
| Đổi tab, quay lại, đổi form bước 1 | Chart kết quả vẫn đúng job cũ; không đổi snapshot/giá/horizon theo form |
| Reset/đổi job khi request cũ đang chờ | Response cũ không hiển thị lên job mới |
| Wheel, drag >3px, click, resize | Zoom/pan rõ; drag không chọn lại mua; chart redraw sau đổi tab và resize |
| Mobile ~390px và bàn phím | Kết luận/cảnh báo/nút chọn/biểu đồ nhìn được, không bị cắt; không bắt hover mới hiểu kết quả |

Không dùng một kết quả đúng của AI để tuyên bố độ chính xác hoặc khả năng kiếm lời. Tính năng được nghiệm thu là **hiển thị và thao tác đúng**, không phải model dự đoán tốt.

## Bằng chứng bàn giao khi thực hiện sau này

- Output lệnh và số pass/fail thực tế, môi trường test riêng, ghi rõ lệnh không chạy hoặc blocker còn thiếu.
- Screenshot bước 2 và bước 4 trên cùng job/snapshot; ID an toàn, UTC+7, markers thấy được, không lộ secret/path nội bộ.
- Network quan sát vote trước reveal, không call create/Gemini khi đổi tab/thử lại reveal; trường hợp lỗi/thiếu nến cũng có bằng chứng.
- Bản ghi lỗi/giới hạn ngôn ngữ provider nếu có; không ghi “đã hết tiếng Anh” chỉ vì prompt đã được đổi.

## Tài liệu cập nhật sau khi có bằng chứng

- `docs/frontend/README.md`: hành trình bốn bước mới, chart/UTC+7, giải thích trạng thái và nút thử lại.
- `docs/backend/README.md`: score nullable, vote/reveal guard, phiên bản prompt mới, nến tham chiếu khi contract đổi.
- Plan này và hai plan liên quan: chỉ đổi checklist/status sau gate thật; bỏ blockedBy khi plan này completed và đã đối chiếu.
- Không tạo changelog thứ hai nếu repo chưa có convention. Dùng tài liệu hiện có, bỏ script smoke/scaffolding của lượt triển khai.

## Checklist

- [ ] Contract tests trong DB riêng pass; lỗi mới được sửa theo nguyên nhân, không repin wording tests.
- [ ] Typecheck/build cần thiết pass.
- [ ] Smoke thực tế đủ ba yêu cầu người dùng và các trạng thái lỗi/thiếu nến.
- [ ] Giữ caveat thử nghiệm, không mock/metric giả, không lộ secrets.
- [ ] Tài liệu và plan có bằng chứng tương ứng, không nâng trạng thái quá phần đã nghiệm thu.
- [ ] Không commit/push khi chưa có yêu cầu.
