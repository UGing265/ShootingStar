# Backend: danh mục API

**26 route = 25 API JSON + 1 trang HTML (`GET /`)**. Mỗi dòng là một cặp method và path đã ghép prefix; không có path nào trùng method. Lệnh đếm: `grep -rE "^@(router|app)\.(get|post|put|patch|delete)\(" backend/shootingstar/api`. Cách tính: `app.py` 1, `read_routes.py` 6, `ingestion_routes.py` 4, `replay_routes.py` 4, `external_routes.py` 5, `trade_plan_routes.py` 6. Sinh OpenAPI tại `/docs` và `/openapi.json` khi chạy server. Đếm lại khi thêm hoặc xoá route.

Cột Gate: `-` là mở; `admin` là phải gửi header `X-Admin-Key` trùng `SHOOTINGSTAR_ADMIN_KEY` (thiếu hoặc sai thì `403`, key chưa cấu hình cũng `403`).

## Hệ thống và trang

| Method | Path | Gate | Mô tả |
|---|---|---|---|
| GET | `/` | - | Trang HTML phục vụ trực tiếp từ FastAPI (giao diện dashboard cũ, không phải Next.js) |
| GET | `/health` | - | Kiểm tra kết nối DB, không lộ chuỗi kết nối |
| GET | `/narrative` | - | Trả markdown mô tả định hướng từ `docs/landing-page-narrative.md`; `404` nếu thiếu file |

## Đọc dữ liệu (`read_routes.py`)

| Method | Path | Gate | Mô tả |
|---|---|---|---|
| GET | `/ingestion-runs` | - | Danh sách lần lấy dữ liệu, phân trang cursor, `limit` 1 đến 100 |
| GET | `/snapshots` | - | Danh sách snapshot, phân trang cursor |
| GET | `/snapshots/{snapshot_id}/quality` | - | Chất lượng và nguồn gốc của snapshot |
| GET | `/snapshots/{snapshot_id}/candles` | - | Nến trong khoảng (`start_ms`, `end_ms`, `limit`) từ Parquet; xác minh SHA-256 trước khi trả |

## Ingestion (`/ingestion`)

| Method | Path | Gate | Mô tả |
|---|---|---|---|
| POST | `/ingestion/preview` | - | Xem trước khoảng lấy, không ghi gì; trả token 15 phút |
| POST | `/ingestion/jobs` | - | Tạo job lấy nến, `202`, chạy nền |
| GET | `/ingestion/jobs` | - | Danh sách job gần đây (`limit`, mặc định 20) |
| GET | `/ingestion/jobs/{job_id}` | - | Trạng thái và kết quả job |

## Replay (`/replay`)

| Method | Path | Gate | Mô tả |
|---|---|---|---|
| POST | `/replay/jobs` | - | Tạo mô phỏng tại mốc `t`; `201`; chỉ dùng nến đã đóng trước `t`; lỗi `404` nếu thiếu file snapshot |
| GET | `/replay/jobs/{job_id}` | - | Xem job; kết quả thật ẩn đến khi reveal |
| POST | `/replay/jobs/{job_id}/vote` | - | Khoá vote UP hoặc DOWN của người dùng |
| POST | `/replay/jobs/{job_id}/reveal` | - | Mở kết quả thật, chấm cả chiến thuật và vote |

## Báo cáo Gemini (`/external-analysis`)

Toàn nhóm bị chặn `503` nếu `SHOOTINGSTAR_EXTERNAL_API_ENABLED` không bật, rồi mới đến kiểm `X-Admin-Key`.

| Method | Path | Gate | Mô tả |
|---|---|---|---|
| GET | `/external-analysis/scoreboard` | admin | So Gemini với baseline trên cùng tập đủ dữ liệu (`snapshot_id`, `horizon`) |
| POST | `/external-analysis/jobs` | admin | Tạo job báo cáo, `202`, chạy nền; `mock_mode` dùng phản hồi giả lập, không gọi Gemini |
| GET | `/external-analysis/jobs/{job_id}` | admin | Trạng thái và báo cáo |
| POST | `/external-analysis/jobs/{job_id}/vote` | admin | Ghi vote người dùng |
| POST | `/external-analysis/jobs/{job_id}/reveal` | admin | Mở outcome và chấm |

## Trade watch và kế hoạch (không có prefix)

Mỗi route gắn `Depends(verify_admin_key)` riêng, không qua cổng `SHOOTINGSTAR_EXTERNAL_API_ENABLED`.

| Method | Path | Gate | Mô tả |
|---|---|---|---|
| POST | `/trade-watches` | admin | Tạo phiên theo dõi, `201`; `502` nếu lấy dữ liệu sàn lỗi, `409` nếu xung đột |
| GET | `/trade-watches/{watch_id}` | admin | Xem phiên |
| POST | `/trade-watches/{watch_id}/stop` | admin | Dừng phiên |
| GET | `/trade-plans/{candidate_id}` | admin | Xem kế hoạch ứng viên |
| POST | `/trade-plans/{candidate_id}/entry-observations` | admin | Ghi quan sát vào lệnh, `201` |
| POST | `/trade-plans/{candidate_id}/exit-observations` | admin | Ghi quan sát ra lệnh, `201` |

Nhóm này chưa có trang frontend nào gọi và chưa được coi là nghiệm thu.

## Quy ước

- Mã lỗi: `400` hoặc `422` đầu vào sai, `403` thiếu quyền, `404` không có, `409` xung đột, `502` lỗi nguồn ngoài, `503` tính năng bị tắt.
- Lỗi trả JSON `{ "detail": ... }`. Không trả đường dẫn file, chuỗi kết nối hay khoá.
- Thời gian là epoch mili giây UTC; việc đổi sang UTC+7 chỉ ở frontend.
- Danh sách lớn dùng cursor `<iso_time>|<id>`. Không dùng offset.
- Job chạy lâu (ingestion, báo cáo Gemini) trả `202` rồi client hỏi lại bằng `GET .../{id}`. Replay tạo job trả `201` ngay.
- `GET /health` khi DB không kết nối được trả `status: degraded`, `database: offline`, không lộ chuỗi kết nối.
- Replay và báo cáo Gemini: người dùng khoá vote trước reveal; không đổi vote sang hướng khác sau khi khoá.
- Lỗi: route tự `raise HTTPException` (ví dụ `external_routes.py` ánh xạ `ValueError` thành 400 hoặc 404). `domain/exceptions.py` có nhưng `api/` chưa import. Không để lộ traceback.
- Đổi contract route thì cập nhật proxy `frontend/src/app/api/**` và `features/*/types.ts`.
- Kiểm tra: `pytest backend/tests` (hoặc `backend/tests/test_api_and_ui.py` khi đổi contract).
- Quy trình thêm route: schema vào `api/schemas.py`, nghiệp vụ ở `application/`, thêm test trong `backend/tests/`, đếm lại số route ở file này.
