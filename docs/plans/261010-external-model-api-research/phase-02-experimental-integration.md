# Phase 02 — Tích hợp API thử nghiệm có giới hạn

**Trạng thái:** PENDING, phụ thuộc [Phase 01 — đánh giá](phase-01-evaluate-providers.md). [Kế hoạch](plan.md). Đây không phải nghiệm thu Phase 02 model tự train của kế hoạch Replay lịch sử.

## Contract dự kiến

- Nhận định API là luồng riêng: `source=external_experimental`, `UP | DOWN | ABSTAIN`, giải thích từ nhà cung cấp **được ghi rõ là output của model**, `probability_up/down=null` tới khi có kiểm định calibration; lỗi provider không biến thành UP/DOWN ngẫu nhiên.
- Người dùng chọn snapshot, `t`, `P`, horizon từ luồng hiện có; backend kiểm tra checksum/mốc nến `available_at <= t`, ràng buộc kết quả chỉ ở backend. Lưu dự báo + version/prompt/hash/cutoff/chi phí trước khi cho reveal; kết quả và vote người vẫn lưu/chấm riêng, không huấn luyện theo vote.
- Hồi cứu dùng nhãn **'minh họa hồi cứu, có nguy cơ model đã biết tương lai'**; prospective mới được chấm như dự báo khóa trước sự kiện. Không chuyển output của API thử nghiệm vào nhánh artifact đã kiểm định mà `backend/shootingstar/application/replay.py` đang gate `NO_MODEL`.

## Các bước triển khai khi phase được duyệt

1. **Backend adapter:** thêm adapter provider trong `backend/shootingstar/adapters/`; cấu hình key qua env local, dùng output JSON schema theo [tài liệu provider](../../external-model-forecast-design.md), cố định model ID/version, timeout và giới hạn token/chi phí. Test response `ABSTAIN`, lỗi/throttle/timeout, malformed JSON và không để key xuất hiện trong log hoặc response.
2. **Application/state:** thêm service riêng trong `backend/shootingstar/application/` lấy nến từ snapshot được backend xác minh, không cho nến sau `t`; khóa input+output theo job; lưu bản ghi theo DB repository/migration phù hợp thay vì trông chờ bộ nhớ tiến trình. Test sửa nến sau `t` không thay input, lock trước reveal và không học từ user vote.
3. **API:** thêm schema/route trong `backend/shootingstar/api/` với phân quyền local/admin, không mở endpoint có chi phí công khai. DTO có `source`, provider/version, trạng thái và lý do; không trả file path/key/prompt chứa secret. Test create/get/reveal, không có outcome trước reveal và kết quả PENDING/UNSCORABLE khi thiếu nến.
4. **UI:** thêm proxy Next.js server và nhánh UI ghi rõ 'nhận định API thử nghiệm' trong `frontend/src/features/replay/`; giữ nhánh dự báo artifact `NO_MODEL` nguyên nghĩa; hiển thị UP/DOWN/ABSTAIN, lý do, version và trạng thái đang chạy/lỗi; không trình bày % chưa kiểm định. UI UTC+7 và tuân thủ `docs/DESIGN.md`.
5. **Đánh giá:** chạy hai đường riêng: demo hồi cứu không được gọi backtest nhân quả; prospective persist trước thị trường thật, kiểm tra điểm theo giá nhập sau horizon, so baseline có số mẫu và chi phí API. Thực hiện smoke thật (API và UI) ngoài test fixture trước khi gọi hoàn tất.

## Điều kiện nghiệm thu

- [ ] Không có path/secret lọt frontend/API; provider bị lỗi không trả dự báo giả.
- [ ] Dữ liệu sau `t` không vào prompt, job không cho đổi prediction đã khóa và outcome bị ẩn trước reveal.
- [ ] Nhãn 'thử nghiệm/hồi cứu/prospective' hiển thị đúng; phần % luôn trống nếu chưa calibration.
- [ ] Test `uv run --no-project pytest tests/test_causal_replay.py tests/test_api_and_ui.py` và `npm --prefix frontend run typecheck` pass; smoke API và UI bằng snapshot thật ghi lại trạng thái.
- [ ] Báo cáo rõ chưa có bằng chứng accuracy nếu cohort prospective chưa đủ mẫu; `NO_MODEL` của pipeline tự train không bị báo nhầm là được giải khóa.
