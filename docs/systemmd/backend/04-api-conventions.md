# Backend: quy ước API

- FastAPI, app khởi tạo ở `api/app.py`. Mỗi nhóm route một file `api/*_routes.py`, đăng ký bằng `include_router`.
- Việc lâu (ingestion, replay, external analysis) trả `202` kèm `id`; client hỏi lại bằng `GET .../{id}`.
- `GET /health` trả `status` và `database`. DB không kết nối được thì `status: degraded`, `database: offline`; không lộ chuỗi kết nối.
- Replay: payload vote có cờ `is_locked`. `[CHƯA KIỂM CHỨNG]` backend có chặn vote lần hai hay không. `reveal` chỉ có ý nghĩa sau vote.
- Thời gian trong payload là epoch millisecond UTC.
- Lỗi: route hiện tự `raise HTTPException` (ví dụ `external_routes.py` ánh xạ `ValueError` thành 400/404). `domain/exceptions.py` có nhưng `api/` chưa import. Không để lộ traceback.
- Đổi contract route thì cập nhật proxy route trong `frontend/src/app/api/**` và `features/*/types.ts`.
- Kiểm tra: `pytest backend/tests` (hoặc `backend/tests/test_api_and_ui.py` khi đổi contract).
