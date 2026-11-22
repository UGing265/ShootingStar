# ShootingStar — Backend Service

The backend ingests market data, manages immutable Parquet snapshots, and serves replay and experimental forecast APIs. Forecast results are research observations, not trading advice or validated probabilities.

## 1. Prerequisites

- Python 3.11+ (tested on Python 3.14).
- PostgreSQL or SQLite configured with `SHOOTINGSTAR_DATABASE_URL`.
- Backend virtual environment, for example `backend/.venv`.

## 2. Environment Configuration

Copy the example environment configuration into `.env` at repository root:

```powershell
Copy-Item .env.example .env
```

Configure `SHOOTINGSTAR_DATABASE_URL` for your local database in `.env`.

> Tests run directly on this main database (no separate test DB). Tests only create rows with their own ids and delete exactly those rows; back up with `pg_dump --format=custom` before large changes.

> **Security invariant:** Never commit `.env` or hardcode credentials. `/health` reports degraded/offline status without returning the database connection string.

## 3. Installation & Database Migration

Activate the virtual environment and install packages:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\alembic.exe upgrade head
```

## 4. Running the Backend Service

Launch the FastAPI application on `127.0.0.1:8000`:

```powershell
.\.venv\Scripts\python.exe -m uvicorn shootingstar.api.app:app --host 127.0.0.1 --port 8000
```

- **Interactive API Documentation:** `http://127.0.0.1:8000/docs`
- **Health Check:** `http://127.0.0.1:8000/health`
- **Legacy Static Dashboard:** `http://127.0.0.1:8000/`

## 5. Verification & Testing

Tests use the configured main database; they must create their own IDs and delete only their own rows.

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest
```

## 6. CLI Ingestion & Historical Replay

In addition to running the web server, ShootingStar provides CLI tools for historical market data ingestion:

```powershell
# Run bounded Binance Spot historical ingestion for an arbitrary date window
.\.venv\Scripts\shootingstar.exe fetch-history --symbol BTCUSDT --timeframe 1m --start 2024-03-01T00:00:00 --end 2024-03-31T23:59:59

# Or pass millisecond Unix timestamps:
.\.venv\Scripts\shootingstar.exe fetch-history --symbol BTCUSDT --timeframe 1m --start 1709251200000 --end 1711929599000
```

Options:
- `--symbol`: Trading pair symbol (default: `BTCUSDT`).
- `--timeframe`: Candle timeframe (`1m` or `5m`, default: `1m`).
- `--start`: Start time in ISO 8601 string or Unix millisecond timestamp (required).
- `--end`: End time in ISO 8601 string or Unix millisecond timestamp (required).

Fetched candles are deduplicated, validated, registered in the database, and persisted into an immutable Parquet snapshot under `data/snapshots/`.

## 7. Experimental 6h Gemini forecast

`forecast-6h-v1` resamples closed `1m`/`5m` candles into a compact causal technical digest and makes one logical Gemini request without web grounding. Default horizon: 360 minutes; default lookback: 14 days. This is not the separate replay strategy engine and does not change its `NO_MODEL` gate.

- `POST /external-analysis/jobs` creates a background job; `GET /external-analysis/jobs/{id}` reads it. `GET /external-analysis/scoreboard?snapshot_id=...&horizon=360&lookback_days=14` compares existing forecasts with baselines.
- External-analysis routes require `SHOOTINGSTAR_EXTERNAL_API_ENABLED` to be enabled and `X-Admin-Key` matching `SHOOTINGSTAR_ADMIN_KEY`. Configure `SHOOTINGSTAR_GEMINI_KEYS` or `GEMINI_API_KEY` server-side; `SHOOTINGSTAR_GEMINI_MODEL`, `SHOOTINGSTAR_GEMINI_TIMEOUT_SECONDS` and `SHOOTINGSTAR_GEMINI_COOLDOWN_SECONDS` are optional. Never expose credentials. Production mock forecasts are disabled.
- Before reveal, users must lock a vote. Outcome is the close of the candle containing `t + horizon` versus purchase price. `abs(move_pct) < 0.5` is `FLAT`; a missing target candle is `UNSCORABLE`.
- Scoreboard excludes `FLAT`, unscorable outcomes and rows without all three directions from the common accuracy cohort. It reports sample counts and Wilson 95% intervals. The 0.3% and 1% threshold counts are sensitivity checks.
- Retrospective results are vulnerable to model memorization. `possible_memorization` flags `gemini-2.5-flash` predictions before 2025-02-01 UTC; an unknown model is not flagged, which is not evidence of a safe cutoff.

From `backend/`, list snapshots and run baseline-only evaluation without Gemini calls or job writes:

```powershell
.\.venv\Scripts\shootingstar.exe list-snapshots
.\.venv\Scripts\shootingstar.exe forecast-batch --snapshot <snapshot-id> --dry-run --limit 200
```

Remove `--dry-run` only after enabling external API access and reviewing quota and cost. Batch defaults: `--horizon 360 --step-hours 6 --lookback-days 14 --limit 50`; `--snapshot` is required. Use `--start`/`--end` with ISO timestamps to bound the range; step must be at least the horizon. Resume skips completed/in-progress points and retries `FAILED`/`FAILED_INTERRUPTED` jobs using the existing job ID. Batch stops on quota exhaustion or three consecutive errors and prints a resume command.
 
**Baseline-only measurement, 2026-11-22:** on the snapshot covering 2025-02-01 through 2026-11-22, a 2,580-point dry-run produced 1,273 scored non-FLAT points: always-UP 49.88%, momentum-6h 46.50%. These are retrospective baseline results, not profit or a guarantee. **Gemini accuracy has not yet been measured.**

Details and research caveats: [external-model-forecast-design.md](../external-model-forecast-design.md).