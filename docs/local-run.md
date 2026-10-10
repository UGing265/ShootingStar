# Running ShootingStar Locally (Two-Terminal Workflow)

ShootingStar runs locally on Windows without requiring Docker containers or external orchestrators.

---

## Prerequisites Checklist

1. **Python Virtual Environment:** `.venv` created in repository root with `pip install -e ".[dev]"`.
2. **Node.js Environment:** Node 18+ and npm installed.
3. **Database:** PostgreSQL instance running or configured in `.env`.

---

## Step-by-Step Launch

### Terminal A — Backend API (Port 8000)

Open PowerShell at repository root:

```powershell
# 1. Ensure .env exists with your database configuration
if (-not (Test-Path .env)) { Copy-Item .env.example .env }

# 2. Apply database migrations
.venv\Scripts\alembic.exe -c backend/alembic.ini upgrade head

# 3. Start the FastAPI backend
.venv\Scripts\python.exe -m uvicorn shootingstar.api.app:app --host 127.0.0.1 --port 8000
```

Verify backend health by visiting `http://127.0.0.1:8000/health` in your browser. You should receive:
```json
{
  "status": "ok",
  "database": "connected",
  "database_status": "connected",
  "engine": "PostgreSQL",
  "timestamp_utc": "..."
}
```

---

### Terminal B — Next.js Frontend (Port 3000)

Open a second PowerShell window at repository root:

```powershell
# 1. Navigate to the frontend directory
Set-Location frontend

# 2. Ensure frontend .env.local exists
if (-not (Test-Path .env.local)) { Copy-Item .env.example .env.local }

# 3. Ensure dependencies are installed
npm ci

# 4. Start Next.js development server
npm run dev
```

Visit the application in your browser: `http://127.0.0.1:3000`

---

## Stopping Services

In each PowerShell terminal, press `Ctrl + C` once to gracefully shut down the service.

---

## Troubleshooting & Diagnostics

### Port 8000 or 3000 Already in Use
Check for running processes on the designated ports:
```powershell
netstat -ano | findstr "8000 3000"
```
Terminate conflicting process using:
```powershell
Stop-Process -Id <PID> -Force
```

### Backend `/health` Shows `degraded`
If the database connection is offline or invalid, `/health` will return HTTP 503 with `"database_status": "offline"`. Verify your PostgreSQL credentials and server status in `.env`.

### Prospective One-Command Launcher
A consolidated PowerShell launcher (`scripts/run-local.ps1`) is prospective for future release after automated browser and live execution gates are fully certified. Use the two-terminal procedure above for manual operation.
