# Backend: nơi lưu dữ liệu

Cột và quan hệ chi tiết nằm ở [../../database-schema.dbml](../../database-schema.dbml) (nguồn: `backend/shootingstar/adapters/db/models.py`). File này chỉ nói bảng nào giữ vai trò gì và dữ liệu nằm ở đâu.

## Bốn nơi lưu

| Nơi | Giữ gì | Ghi bởi |
|---|---|---|
| CSDL (`SHOOTINGSTAR_DATABASE_URL`) | metadata, nến chuẩn, job báo cáo, trade watch, audit | `adapters/db/` |
| Parquet `data/snapshots/` | nến bất biến của từng snapshot, có SHA-256 | `adapters/storage.py` |
| Raw `data/raw/` | JSON Binance gốc của mỗi lần lấy | `adapters/storage.py` |
| JSON `data/simulations/` | từng job replay | `application/replay.py` |

Thư mục `data/` tồn tại cả ở gốc repo và ở `backend/` (`backend/data/` bị git-ignore). Đường dẫn ghi trong `snapshots.file_path` là đường dẫn tương đối, nên vị trí thật phụ thuộc thư mục chạy lúc ghi. Mọi chỗ đọc file snapshot phải qua `resolve_snapshot_file_path` (thử cwd, gốc repo, `backend/`). API công khai không trả đường dẫn nội bộ.

## Bảng CSDL (9)

| Bảng | Vai trò | Khoá chính |
|---|---|---|
| `canonical_candles` | nến chuẩn hoá; duy nhất theo (venue, symbol, timeframe, open_time_ms) | `id` (BigInteger) |
| `rejected_records` | bản ghi bị loại khi kiểm chất lượng | `id` |
| `ingestion_runs` | một lần lấy dữ liệu và kết quả | `id` (UUID dạng chuỗi) |
| `snapshots` | metadata snapshot; id là SHA-256 nội dung | `id` (64 ký tự) |
| `audit_logs` | nhật ký thao tác | `id` |
| `external_analysis_jobs` | job báo cáo Gemini: trạng thái, evidence envelope, vote, reveal | `id` |
| `trade_watches` | phiên theo dõi vào lệnh, có lease | `id` |
| `candidate_plans` | kế hoạch vào lệnh ứng viên | `id` |
| `trade_observations` | quan sát vào hoặc ra lệnh của kế hoạch | `id` |

Khoá ngoại: `snapshots.ingestion_run_id` trỏ `ingestion_runs.id`; `candidate_plans.watch_id` trỏ `trade_watches.id`.

Replay không có bảng: job nằm ở `data/simulations/*.json` và được nạp lại khi khởi động service.

## Migration (Alembic)

- Thư mục `backend/alembic/versions/`; head hiện tại ghi trong `database-schema.dbml` (`7b8c9d0e1f2a`, bỏ bảng self-learning).
- Chạy migration trên DB thật chỉ khi có lệnh của người vận hành. Lệnh: [../../run-backend.md](../../run-backend.md).

## Ba bất biến

1. Snapshot Parquet không sửa sau khi ghi; id là hash nội dung, `GET .../candles` xác minh SHA-256 trước khi trả.
2. Dữ liệu đã sinh (job, vote, reveal, nến) không bị xoá hay tính lại im lặng.
3. Không có DB mặc định: thiếu `SHOOTINGSTAR_DATABASE_URL` thì backend không khởi tạo kết nối.
