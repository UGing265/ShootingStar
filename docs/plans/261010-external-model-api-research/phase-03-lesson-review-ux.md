# Phase 03 — Thư viện bài học đã duyệt và UX Replay API

**Trạng thái:** IN-PROGRESS (Mã nguồn SSRF validator, Lesson DB models/repo/migration `4d5e6f7a8b9c`, API routes và Next.js page/component đã hoàn tất; browser smoke đang mở). [Plan](plan.md).

## BE — agent nghiên cứu nguồn tách khỏi dự báo

1. Agent **chạy ngoài luồng dự báo** đề xuất nguồn/URL bài trading từ tài liệu có thể đọc, trích định nghĩa ngắn, quy tắc/điều kiện nhận diện, ví dụ và giới hạn của mẫu hình, ghi tên tác giả/tổ chức + ngày truy cập. Không đi tìm tin/web khi user bấm dự báo lịch sử; bài mới không tự duyệt. Không lưu nguyên sách/bài có bản quyền; tóm tắt ngắn và link tới nguồn gốc.
2. Tạo bảng/DB migration trong `backend/shootingstar/adapters/db/models.py`, `repository.py`, `alembic/versions/`: `Lesson` (ID, nguồn, URL chuẩn hóa, trạng thái), `LessonRevision` bất biến (version, định nghĩa ngắn, caveat, source snippet/hash nếu được phép, ngày kiểm tra, reviewer, timestamp), `ReviewEvent` (ai duyệt/sửa/từ chối, lý do). Trạng thái `PENDING/APPROVED/REJECTED`; bản đã duyệt mới vào context. Mọi dự báo tham chiếu `lesson_id + revision_id`, không trỏ vào bản mutable để thay đổi lịch sử.
3. Backend kiểm tra URL chỉ `https://`, domain công khai, không theo redirect vào private/loopback/metadata IP (SSRF), giới hạn kích thước/timeout khi lấy bài; link sống **không chứng minh nội dung đúng** nên reviewer phải xem bài gốc và đối chiếu tóm tắt. Chỉ đưa **định nghĩa + caveat + URL nguồn đã duyệt** của số bài liên quan vào prompt; chọn bài trước call theo từ khóa/loại mẫu đã duyệt hoặc catalogue nhỏ cố định, không để agent tự tìm web. Model trả `lesson_ids` và candle timestamps liên quan; verifier allowlist phiên bản/mốc có trong input, không đảm bảo mô hình hiểu bài hay mẫu hình có predictive edge.
4. API review chỉ cho local/admin đã xác thực: liệt kê bài `PENDING`, xem revision gốc/URL, chỉnh nội dung, approve/reject theo version, xem audit; không public write route không auth. Nếu chưa có admin auth phù hợp, **không bật UI/endpoint ghi** cho tới khi bảo vệ được; không bắt người dùng thao tác DB bằng tay. Public read chỉ trả bài APPROVED có trường an toàn, không lộ internal paths/key.

## FE — UX quản trị bài học

- Tạo trang quản trị `frontend/src/app/(work)/lessons/review/page.tsx` và feature `frontend/src/features/lessons/`; Next server proxy gọi backend, kiểm session/quyền admin **ở cả BE lẫn FE**, không chỉ ẩn nút. Tab `Chờ duyệt / Đã duyệt / Từ chối`; thẻ bài có tiêu đề, tên nguồn, URL link mở tab mới an toàn, đoạn nguồn ngắn, bản tóm tắt và caveat; hành động **Xem bài gốc**, **Sửa bản tóm tắt**, **Duyệt**, **Từ chối** (kèm lý do). Confirm trước approve; trạng thái/số phiên bản/audit rõ, không có nút xuất bản tự động từ agent.
- Empty state: “Chưa có bài chờ duyệt”; nguồn lỗi: “Không truy cập được URL, chưa thể duyệt”; không hiện tài liệu chưa duyệt cho model hoặc người dùng như kiến thức đã xác minh. Dùng màu/nét/typography theo `docs/DESIGN.md`, UTC+7 cho thời gian review.

## FE — UX mô phỏng 4 bước giữ nguyên hành trình hiện tại

1. **Điểm mua:** Snapshot selector, chart tương tác (wheel zoom, giữ chuột trái pan, click chọn), nhập `t` UTC+7 và giá mua `P` thủ công, horizon **30m cho nhánh thử nghiệm đầu tiên**; hiện khoảng 6 giờ sẽ gửi và độ phủ. Nếu chỉ có <6h/gap không đạt: disabled **Phân tích với Gemini**, nêu thiếu bao nhiêu lịch sử/khoảng nào, dẫn về `/data` chọn/nạp snapshot có lịch sử trước `t`. Đổi snapshot/t/P/horizon trước submit vô hiệu hóa job preview; job cũ bất biến và chỉ mở lại bằng ID.
2. **AI phân tích:** Nút bắt đầu gọi API tạo job đúng một lần, spinner/poll trạng thái `PREPARING/CALLING/READY/ABSTAIN/FAILED/INSUFFICIENT_HISTORY`, chi phí/lượt được cảnh báo trước khi gửi; timeout/429 hiển thị lý do và trạng thái, không hiện UP/DOWN giả. Khi READY: hiển thị **‘Nhận định API thử nghiệm — không phải dự báo đã kiểm định’**, model/version, hướng hoặc ABSTAIN, rationale được gắn nhãn “AI viết”, mốc nến AI viện dẫn và link bài học **đã duyệt** kèm lưu ý link giải thích khái niệm, không bảo đảm thắng. Không có catalog: không hiện link giả. Hồi cứu thêm banner **‘Model hiện nay có thể đã biết tương lai của mốc lịch sử’**; prospective ghi mốc khóa dự báo.
3. **Dự đoán của tôi:** Người dùng có thể chọn UP/DOWN của chính mình, lưu bất biến riêng; AI **không học từ lựa chọn này**. Người đã xem AI trước khi chọn: không gọi đây là so sánh mù. Cho tiếp tục ngay cả khi AI ABSTAIN/lỗi, nhưng không ghi như AI đã đoán.
4. **Kết quả:** Nút **Xem kết quả** chỉ sau bước khóa yêu cầu. **Hồi cứu:** snapshot có nến kết quả thì có thể trả EVALUATED ngay, nhưng luôn gắn nhãn *minh họa hồi cứu*; thiếu nến/gap → UNSCORABLE. **Prospective:** chưa tới `t+30m` theo thời gian thật hoặc nến chưa khả dụng → PENDING; đến hạn nhưng không đủ nến → UNSCORABLE; đủ dữ liệu → EVALUATED và so **giá mua P**. AI/user chấm riêng và loại ABSTAIN khỏi accuracy. GET job trước reveal không bao giờ chứa outcome. Refresh trở lại job bằng ID, không tự tạo request API/chi phí mới.

## Kiểm chứng / gate

- [x] BE test agent candidate → pending → chỉnh → approve/reject → revision bất biến → prediction trỏ revision; trang/route không auth bị từ chối; SSRF/redirect private và URL giả bị chặn (Đã xác nhận trong `backend/tests/test_lessons.py`).
- [ ] FE browser smoke với snapshot đủ/thiếu 6h, job READY/ABSTAIN/FAILED/429, hồi cứu/prospective, link bài duyệt đúng revision, chọn người, reveal bị chặn/trưởng thành, refresh không gọi API tính phí lần hai; chart hành vi giữ nguyên (Gate đang mở chờ kiểm thử trình duyệt thực tế).
- [x] `npm --prefix frontend run typecheck`, `npm --prefix frontend run build`, `uv run --no-project pytest backend/tests` pass toàn bộ (91/91 test pass, Next.js build thành công); bảo vệ fail-closed không lộ secret.

**Bước tiếp:** Chỉ đánh giá độ chính xác API bằng log khóa trước thị trường ở [Phase 04](phase-04-prospective-evaluation.md).
