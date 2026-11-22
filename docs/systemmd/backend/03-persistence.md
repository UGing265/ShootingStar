# Backend: lưu trữ

## Nguồn sự thật

| Loại | Nơi | Ghi chú |
|---|---|---|
| Quan hệ | PostgreSQL hoặc SQLite theo `SHOOTINGSTAR_DATABASE_URL` | Không có DB mặc định; thiếu biến thì không chạy |
| Test | `SHOOTINGSTAR_TEST_DATABASE_URL` | Tách khỏi DB thật |
| Nến | Parquet snapshot bất biến, id là SHA-256 | Đường dẫn file không trả ra API |
| Phản hồi gốc Binance | Thư mục raw | Dùng làm bằng chứng nguồn |
| Replay | JSON trong thư mục simulations | |

## Schema và migration

- Mô tả hiện hành: `docs/database-schema.dbml` (import vào dbdiagram.io).
- Quản lý bằng Alembic: `backend/alembic/`, cấu hình `backend/alembic.ini`. Chạy: `alembic -c backend/alembic.ini upgrade head`.
- Model: `adapters/db/models.py`; truy cập qua `adapters/db/repository.py` và `session.py`.
- Mỗi thay đổi schema cần: model, Alembic revision có `downgrade`, cập nhật DBML, test.

## Nhóm bảng

Dữ liệu giá (`ingestion_runs`, `snapshots`, `canonical_candles`, `rejected_records`, `audit_logs`), báo cáo (`external_analysis_jobs`), trade plan (`trade_watches`, `candidate_plans`, `trade_observations`). Trong cây hiện tại, model của lessons và pattern_* đã bị xoá khỏi `models.py` nhưng chưa có Alembic drop; DB đã tạo bằng head cũ có thể còn các bảng đó.
