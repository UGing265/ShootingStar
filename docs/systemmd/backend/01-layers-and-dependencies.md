# Backend: tầng và phụ thuộc

Gói Python: `backend/shootingstar/`. CLI `shootingstar` đăng ký qua `pyproject.toml`.

```text
cli/  api/            # điểm vào: argparse CLI, FastAPI
   \  /
application/          # nghiệp vụ: ingestion, replay, external_analysis, trade_watch, ...
   |    \
domain/  adapters/    # domain: model, quy tắc, exception; adapters: Binance, DB, storage, Gemini
```

## Quy tắc phụ thuộc

- `domain/` không import tầng nào khác. Chứa `models.py` (Candle, Timeframe...), `trade_plan.py`, `exceptions.py`.
- `application/` import `domain/` và gọi `adapters/` qua đối tượng được truyền vào. Không import `api/` hoặc `cli/`.
- `adapters/` làm việc với bên ngoài: `binance.py`, `storage.py` (Parquet/raw), `db/` (SQLAlchemy models, repository, session), `model_api/` (Gemini).
- `api/` và `cli/` chỉ nhận input, gọi `application/`, trả output. Không tính toán nghiệp vụ.

## Thư mục

| Thư mục | Nội dung |
|---|---|
| `api/` | `app.py` (khởi tạo, đăng ký router), `ingestion_routes`, `replay_routes`, `external_routes`, `trade_plan_routes`, `read_routes`, `schemas` |
| `application/` | `ingestion`, `replay`, `entry_strategy`, `barrier_evaluation`, `trade_watch`, `patterns` (chỉ diagnostics), `external_analysis/` |
| `adapters/` | `binance`, `binance_market_events`, `storage`, `db/*`, `model_api/*` |

[CHƯA KIỂM CHỨNG] Phụ thuộc ngược (import vòng) chưa được quét tự động; cần công cụ như `import-linter` nếu muốn ép.
