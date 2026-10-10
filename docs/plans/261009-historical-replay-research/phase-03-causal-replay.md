# Phase 03 — Mô phỏng dự đoán tại điểm mua

**Trạng thái:** Chưa triển khai/chưa nghiệm thu. Xem [plan.md](plan.md). Đây là **luồng chính**; ý tưởng tua từng nến và con trỏ phiên cũ hoãn, không nằm trong gate phase này.

**Yêu cầu UX mới (2026-10-10):** Theo [plan Replay dễ đọc](../261010-replay-result-ux/plan.md), sau khi lưu lựa chọn ở bước 3 thì tự chuyển bước 4 và tự gọi reveal; không bắt bấm “Xem kết quả” lần nữa. Bước 2 có chart lịch sử trước mua, bước 4 có chart đối chiếu khi đủ dữ liệu. Nội dung cũ nói bấm riêng bên dưới chỉ là lịch sử thiết kế; gate khóa vote/đủ nến và hạn chế model giữ nguyên. Phase này chưa nghiệm thu cho tới khi plan UX mới hoàn tất.

## Tab và hành trình

1. **Điểm mua:** Người dùng chọn snapshot; **click/chạm biểu đồ để chọn mốc mua** (thời gian và giá quan sát tại điểm) **hoặc nhập ngày/giờ và giá thủ công**. Có thể sửa giá/mốc trước job; chart vẽ chấm tại tọa độ đã chọn và đường ngang giá mua giả định, giá nến thực tế hiển thị riêng nếu lệch. Chọn mốc thời lượng dự đoán hoặc nhập thời lượng trong khoảng 30 phút–tối đa một ngày. Không gọi đây là giá khớp lệnh.
2. **Dự báo AI:** Bấm job; backend đưa `(t, giá mua giả định, horizon)` cùng nến đã đóng/khả dụng tới `t` vào model đúng nhãn **giá tương lai so với giá mua đầu vào**. Hiển thị đang chạy/lỗi/hoàn tất; chỉ khi model đã kiểm định đúng loại mới trả UP/DOWN, xác suất và bằng chứng thực; không có thì báo thiếu điều kiện, không đoán giả.
3. **Dự đoán của tôi:** Sau AI, người dùng chọn **UP hoặc DOWN**; lưu lựa chọn riêng, không ghi đè AI và không dùng lựa chọn đó để học. Người đã thấy AI trước khi chọn nên chỉ **độc lập về bản ghi**, không phải phép so công bằng giữa hai người dự báo mù.
4. **Kết quả:** Sau khi đã khóa AI và UP/DOWN của người, người dùng bấm **“Xem kết quả”**. Nếu có nến đóng hợp lệ ở mốc sau horizon, backend so giá sau đó với **giá mua giả định đã nhập** và chấm AI/người đúng-sai **riêng**; thiếu thì `PENDING`/`UNSCORABLE` kèm lý do. Backend không đưa giá tương lai vào job AI và không trả outcome qua route job trước thao tác xem kết quả. API lịch sử công khai vẫn có thể cho người dùng xem trước, nên đây không phải blind test.

## Đã chốt và còn mở trước khi triển khai

- **Chốt:** chart click hoặc nhập ngày/giờ và giá đều tạo `(t, giá mua giả định)`; hai giá trị này đi vào AI cùng lịch sử trước `t`, giá mua đồng thời làm mốc chấm. Cho chọn mốc hoặc nhập horizon trong 30 phút–tối đa một ngày; AI hiện trước, người chọn UP/DOWN sau; chỉ bấm **“Xem kết quả”** sau khi khóa cả hai mới mở outcome.
- **Còn mở kỹ thuật:** Quy tắc chọn nến đã đóng khi click giữa nến/gap và khi `t+horizon` nằm giữa nến; bước chọn/nhập horizon hợp lệ, timezone hiển thị. Không đưa nến tương lai vào feature; 1 ngày = 24 giờ cần xác nhận nếu có cách hiểu khác.

## Backend, frontend và tính toàn vẹn

- Backend lưu ID/hash snapshot, mốc UTC, giá mua giả định, horizon, model artifact/version/cutoff, dự báo AI (bất biến), lựa chọn người (riêng), outcome và lý do trạng thái. API job tách tạo/truy vấn trạng thái/khóa lựa chọn; endpoint **“Xem kết quả”** kiểm tra lựa chọn đã khóa và đủ nến trước khi phát outcome; route truy vấn job không lộ outcome sớm. Chỉ trả ID công khai, không lộ file path/DB URL.
- Frontend tab Điểm mua/Dự báo AI/Dự đoán của tôi/Kết quả dùng API làm nguồn duy nhất cho label/xác suất/chấm điểm; render chart marker và đường giá, trạng thái mạng mất, refresh/resume; không tính lại kết quả trên client.
- Model không được học từ lựa chọn người; dữ liệu kết quả thị trường có thể vào **đợt huấn luyện model phiên bản mới** sau đánh giá riêng ở Phase 02. Không thay model của job đã hoàn tất hay dùng kỳ vừa chấm để tự khoe model mới tốt hơn.

### File BE/FE và thứ tự cutover (plan, chưa code)

| Sửa/tạo | Công việc |
|---|---|
| **Sửa/thay** `backend/shootingstar/application/replay.py` | Hiện tại quản lý session trong RAM, step từng nến, horizon cố định 30m. Chuyển sang job theo **một điểm chọn**, snapshot ID/hash, giá/mốc/horizon, artifact hợp lệ; trả trạng thái job và chứng cứ. Bỏ state `step`/prediction tự sinh mỗi nến nếu không còn caller. Không dùng RAM-only cho lịch sử job cần sống qua refresh/restart. |
| **Sửa/thay** `backend/shootingstar/api/replay_routes.py`, `backend/shootingstar/api/schemas.py`, `backend/shootingstar/api/app.py` | Contract dự kiến: tạo job, GET job/trạng thái **không kèm outcome**, ghi UP/DOWN của người **một lần**, thao tác “Xem kết quả” kiểm tra khóa lựa chọn/nến rồi trả outcome; kiểm tra quyền và input tại backend, không lộ file path/DB URL. Gỡ route `/replay/sessions/{id}/step` và schema cũ sau khi migrate mọi caller, không giữ shim. |
| **Sửa** `backend/shootingstar/adapters/db/models.py`, `repository.py`; **thêm** migration trong `alembic/versions/` | Persist job/AI prediction bất biến, user prediction tách riêng, outcome độc lập, snapshot/model/hash/cutoff/horizon; khóa idempotent khi bấm nhanh và giữ state khi backend restart. Kiểm tra dữ liệu cũ trước khi xóa session-only path. |
| **Sửa** `frontend/src/app/(work)/replay/page.tsx`, `frontend/src/features/replay/replay-player.tsx`, `frontend/src/features/replay/types.ts`, `frontend/src/shared/ui/sidebar.tsx` | Đổi nhãn `/replay` từ “Tua nến” sang “Mô phỏng”; thay player bằng 4 tab/step chính. Khi snapshot trống dẫn `/data`. Tái dùng UI chart hoặc phần vẽ chung từ `frontend/src/features/data/candlestick-chart.tsx` **chỉ cho OHLCV/marker/đường giá**, không nhân bản logic chỉ số. |
| **Sửa/thay** `frontend/src/app/api/replay/sessions/` và route con đang gọi `step` | Proxy server-only cho contract job/vote/outcome mới; update toàn bộ caller, xóa proxy cũ không còn dùng. `frontend/src/shared/api-client.ts` giữ fetch FastAPI phía server. |
| **Sửa/thêm test** `tests/test_api_and_ui.py`, test application replay và persistence theo convention repo | Ranh giới cutoff/horizon, refresh/restart, bấm đôi, chọn người sau AI, lộ outcome sớm, hai bản chấm riêng, thiếu model, thay snapshot/checksum, không dùng vote để train. |

**Trình tự:** chốt quy tắc chọn nến khi click/gap, bước chọn thời lượng dự đoán/nến kết quả và timezone → DB migration + model hợp lệ có **giá mua giả định làm đầu vào và mốc chấm** → BE job/prediction/vote/**reveal outcome** → FE marker/tab/Next proxy → đổi điều hướng, migrate mọi caller rồi xóa `step`/test cũ chỉ khóa luồng tua, thay bằng test job theo điểm chọn → smoke browser trên snapshot thật. Bản prediction cũ nếu không có contract tương thích thì không gán lại thành prediction của người/job mới.

## Gate kiểm chứng

- [ ] Trên snapshot thực, chọn điểm/giá khác nhau: marker đặt đúng tọa độ; đường ngang đúng giá nhập; giữ nguyên điểm qua refresh; giá quan sát của nến được hiển thị riêng.
- [ ] Cùng snapshot/model/điểm/horizon cho AI dự đoán nhất quán; thay nến tương lai không đổi dự báo; chặn model học/chọn cấu hình sau thời điểm chọn hoặc sai horizon; không có model thì không hiện xác suất.
- [ ] AI dự báo được lưu **trước** lựa chọn người; người chọn UP/DOWN không đổi bản AI; kết quả thị trường sau horizon chấm riêng cả hai; test `PENDING`, `UNSCORABLE`, ranh giới đóng nến/latency và checksum mismatch.
- [ ] Browser smoke các tab/job trên snapshot thật, kiểm tra lỗi/refresh/mobile và chứng cứ kết quả. Không dùng mock như bằng chứng model dự đoán tốt.

**Không thuộc scope:** tua từng nến, ví tiền, lệnh giao dịch, P&L, phí/trượt giá, real-time, model Gemini/LLM.
