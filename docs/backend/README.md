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
# In repository root
.venv\Scripts\python.exe -m pip install -e ".[dev]"
.venv\Scripts\alembic.exe upgrade head
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
.venv\Scripts\python.exe -m pytest
```
