# Backend: tầng, phụ thuộc, module

Gói Python `backend/shootingstar/`. CLI `shootingstar` đăng ký qua `backend/pyproject.toml`.

```text
cli/  api/            # điểm vào: argparse CLI, FastAPI
   \  /
application/          # nghiệp vụ: ingestion, replay, forecast, external_analysis, trade_watch
   |    \
domain/  adapters/    # domain: model, quy tắc, exception; adapters: Binance, DB, storage, Gemini
```

## Quy tắc phụ thuộc

- `domain/` không import tầng nào khác.
- `application/` import `domain/`, gọi `adapters/` qua đối tượng truyền vào; không import `api/` hay `cli/`.
- `adapters/` làm việc với bên ngoài (Binance, DB, file, Gemini).
- `api/` và `cli/` chỉ nhận input, gọi `application/`, trả output; không tính nghiệp vụ.

[CHƯA KIỂM CHỨNG] Import vòng chưa được quét tự động; cần `import-linter` nếu muốn ép.

## Module theo thư mục

### `domain/`

| File | Vai trò |
|---|---|
| `models.py` | `Venue`, `Symbol`, `Timeframe`, `Provenance`, `Candle`, `DataQualityReport` |
| `trade_plan.py` | Enum và dataclass kế hoạch vào lệnh 30 phút: `RiskConfig`, `EntryZone`, `CandidatePlan`, `EntryObservation`, `ExitObservation` |
| `exceptions.py` | Exception miền (`DomainError`...) |

### `application/`

| File / thư mục | Vai trò |
|---|---|
| `ingestion.py` | Lấy nến Binance theo trang, kiểm tra chất lượng, ghi snapshot |
| `replay.py` | Mô phỏng chiến thuật offline theo mốc `t`, vote, reveal, lưu JSON |
| `entry_strategy.py` | Engine chiến thuật vào lệnh xác định (vùng vào, rủi ro) |
| `barrier_evaluation.py` | Chấm kết quả chạm mục tiêu hay cắt lỗ trước trên đường giá thật |
| `trade_watch.py` | Vòng đời trade watch: theo dõi, rào chắn, lease |
| `contracts.py` | Giao diện và hợp đồng dùng chung của tầng application |
| `forecast/` | Nguyên liệu dự báo nhân quả, không gọi mạng hay model: `candle_window`, `resample`, `indicators`, `technical_digest`, `agreement_score`, `baselines`, `outcome`, `scoreboard`, `errors` |
| `external_analysis/` | Báo cáo Gemini: `service.py` (vòng đời job), `forecast_pipeline.py` (chuỗi feed, analyst, verify, report), `stages/` (4 bước), `contracts.py`, `job_dto.py` |

### `adapters/`

| File / thư mục | Vai trò |
|---|---|
| `binance.py` | Nến Binance Spot `klines` |
| `binance_market_events.py` | Sự kiện thị trường công khai và quy tắc sàn |
| `storage.py` | Raw archive, snapshot Parquet, `resolve_snapshot_file_path` |
| `db/` | `models.py` (SQLAlchemy), `repository.py`, `session.py` (engine, nạp `.env`) |
| `model_api/` | `gemini_adapter.py` (một lần gọi có schema), `gemini_transport.py` (HTTP, retry, cooldown key), `key_manager.py`, `prompts/forecast_6h_prompt.py` |

### `api/`

| File | Vai trò |
|---|---|
| `app.py` | Khởi tạo FastAPI, lifespan (quét job bị gián đoạn), đăng ký 5 router, trang `/` |
| `read_routes.py` | Đọc: health, ingestion runs, snapshots, quality, candles, narrative |
| `ingestion_routes.py` | Xem trước và tạo job lấy nến |
| `replay_routes.py` | Job mô phỏng |
| `external_routes.py` | Báo cáo Gemini, scoreboard; gate admin |
| `trade_plan_routes.py` | Trade watch và kế hoạch |
| `schemas.py` | DTO Pydantic dùng chung |

### `cli/`

`main.py` (đăng ký lệnh), `forecast_batch_command.py` (lệnh `forecast-batch`). Danh sách lệnh: [05-cli-config-tests.md](05-cli-config-tests.md).
