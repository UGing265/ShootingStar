# ShootingStar — Backend Service

The backend provides market data ingestion, immutable Parquet snapshot management, walk-forward ML experiment execution, pattern recognition, and read-only REST APIs for the Next.js frontend.

## 1. Prerequisites

- Python 3.11+ (tested on Python 3.14)
- PostgreSQL (14+ recommended) or PostgreSQL-compatible database
- Virtual environment in repository root (`.venv`)

## 2. Environment Configuration

Copy the example environment configuration into `.env` at repository root:

```powershell
Copy-Item .env.example .env
```

Edit `.env` to configure your local PostgreSQL database URL:

```ini
SHOOTINGSTAR_DATABASE_URL=postgresql+psycopg2://user:password@127.0.0.1:5432/shootingstar_db
SHOOTINGSTAR_TEST_DATABASE_URL=postgresql+psycopg2://user:password@127.0.0.1:5432/shootingstar_test_db
```

> **Security Invariant:** Never commit `.env` or hardcode database connection strings. The `/health` endpoint strictly prevents credential or connection string leakage, returning HTTP 503 with `"database_status": "offline"` if the database is disconnected.

## 3. Installation & Database Migration

Activate the virtual environment and install packages:

```powershell
# In repository root: install backend in editable mode
.venv\Scripts\python.exe -m pip install -e "backend[dev]"

# Run migrations (from backend directory or passing config)
Set-Location backend
..\.venv\Scripts\alembic.exe upgrade head
Set-Location ..
```

## 4. Running the Backend Service

Launch the FastAPI application on `127.0.0.1:8000`:

```powershell
.venv\Scripts\python.exe -m uvicorn shootingstar.api.app:app --host 127.0.0.1 --port 8000
```

- **Interactive API Documentation:** `http://127.0.0.1:8000/docs`
- **Health Check:** `http://127.0.0.1:8000/health`
- **Legacy Static Dashboard:** `http://127.0.0.1:8000/`

## 5. Verification & Testing

Run the full pytest suite (52+ tests verifying causal boundaries, latency gating, and API contracts):

```powershell
# Run full backend pytest suite
.venv\Scripts\python.exe -m pytest backend/tests
# Or from inside backend directory:
# cd backend && ..\.venv\Scripts\python.exe -m pytest
```

## 6. CLI Ingestion & Historical Replay

In addition to running the web server, ShootingStar provides CLI tools for historical market data ingestion:

```powershell
# Run bounded Binance Spot historical ingestion for an arbitrary date window
.venv\Scripts\python.exe -m shootingstar.cli.main fetch-history --symbol BTCUSDT --timeframe 1m --start 2024-03-01T00:00:00 --end 2024-03-31T23:59:59

# Or pass millisecond Unix timestamps:
.venv\Scripts\python.exe -m shootingstar.cli.main fetch-history --symbol BTCUSDT --timeframe 1m --start 1709251200000 --end 1711929599000
```

Options:
- `--symbol`: Trading pair symbol (default: `BTCUSDT`).
- `--timeframe`: Candle timeframe (`1m` or `5m`, default: `1m`).
- `--start`: Start time in ISO 8601 string or Unix millisecond timestamp (required).
- `--end`: End time in ISO 8601 string or Unix millisecond timestamp (required).

Fetched candles are deduplicated, validated, registered in the database, and persisted into an immutable Parquet snapshot under `data/snapshots/`.
