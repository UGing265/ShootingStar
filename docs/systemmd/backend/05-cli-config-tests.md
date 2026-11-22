# Backend: CLI, cấu hình, kiểm thử

Cách chạy từng lệnh nằm ở [../../run-backend.md](../../run-backend.md). File này chỉ liệt kê có gì.

## CLI `shootingstar` (8 lệnh)

Đăng ký trong `backend/shootingstar/cli/main.py` (lệnh `forecast-batch` ở `forecast_batch_command.py`). Đếm: `grep -n "add_parser(" backend/shootingstar/cli/*.py`.

| Lệnh | Việc |
|---|---|
| `info` | In thông tin hệ thống và cấu hình |
| `fetch-pilot` | Lấy nến Binance Spot bị giới hạn (pilot) |
| `fetch-history` | Lấy lịch sử theo khoảng ngày tuỳ ý, có giới hạn |
| `list-snapshots` | Liệt kê snapshot trong DB |
| `show-snapshot` | Xem metadata một snapshot |
| `serve` | Chạy web server (uvicorn) |
| `forecast-batch` | Chấm baseline dự báo 6h hoặc chạy job Gemini hàng loạt, có thể tiếp tục; `--dry-run` chỉ tính baseline |
| `watch-entry` | Theo dõi công khai BTCUSDT cho setup vào nhanh |

`forecast-batch` không dry-run chỉ chạy khi `SHOOTINGSTAR_EXTERNAL_API_ENABLED` bật.

## Biến môi trường

Nạp từ `.env` (cwd, nếu không có thì gốc repo) bằng `load_env_file` (`adapters/db/session.py`). Mặc định không ghi đè biến đã có sẵn trong shell: biến shell cũ cùng tên thắng `.env`. Mẫu: `.env.example`. Không commit `.env`.

| Biến | Dùng cho |
|---|---|
| `SHOOTINGSTAR_DATABASE_URL` | Kết nối DB; không có mặc định |
| `SHOOTINGSTAR_TEST_DATABASE_URL` | DB cho test |
| `SHOOTINGSTAR_EXTERNAL_API_ENABLED` | Bật nhóm `/external-analysis` và `forecast-batch` thật (mặc định tắt, `503`) |
| `SHOOTINGSTAR_ADMIN_KEY` | Khoá header `X-Admin-Key` cho route admin |
| `SHOOTINGSTAR_GEMINI_KEYS` | Danh sách khoá Gemini (xoay vòng) |
| `GEMINI_API_KEY` | Một khoá Gemini |
| `SHOOTINGSTAR_GEMINI_MODEL`, `GEMINI_MODEL` | Tên model |
| `SHOOTINGSTAR_GEMINI_TIMEOUT_SECONDS`, `GEMINI_TIMEOUT_SECONDS` | Hạn chờ mỗi lần gọi |
| `SHOOTINGSTAR_GEMINI_COOLDOWN_SECONDS` | Thời gian nghỉ của khoá bị giới hạn |

Ghi giá trị thật của khoá vào `.env`, không vào docs hay brief.

## Phụ thuộc

Python 3.11 trở lên. Gói chính (`backend/pyproject.toml`): `httpx`, `pyarrow`, `sqlalchemy`, `alembic`, `psycopg2-binary`, `numpy`, `fastapi`, `uvicorn`; thêm `pytest` ở `[dev]`.

## Kiểm thử (`backend/tests/`, pytest, 16 file)

| File | Phủ |
|---|---|
| `test_api_and_ui.py` | Contract API, trang `/`, resolver đường dẫn snapshot, snapshot mất file |
| `test_domain_contracts.py` | Domain model và quy tắc |
| `test_storage_and_ingestion.py` | Storage, ingestion |
| `test_persistence.py` | Repository, DB |
| `test_causal_replay.py` | Replay nhân quả |
| `test_barrier_evaluation.py`, `test_entry_strategy.py`, `test_trade_watch.py` | Chiến thuật vào lệnh, chạm mục tiêu hoặc cắt lỗ, trade watch |
| `test_external_analysis_api.py`, `test_external_analysis_pipeline.py` | Route và pipeline báo cáo |
| `test_forecast_baselines_outcome.py`, `test_forecast_digest.py`, `test_forecast_indicators.py`, `test_forecast_batch_resume.py` | Dự báo 6h: baseline, digest, chỉ báo, batch tiếp tục |
| `test_verify_stage_tolerance.py` | Bước kiểm số của pipeline |
| `test_gemini_json_parsing.py` | Đọc JSON Gemini chứa ký tự điều khiển |

Test chạy trên DB chính (xem [../governance.md](../governance.md)): chỉ tạo và xoá dòng của chính nó.
