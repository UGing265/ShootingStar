<#
.SYNOPSIS
    ShootingStar Local Development Launcher (Dual Backend & Frontend Process Manager)

.DESCRIPTION
    Automates prerequisite validation, virtual environment activation, schema migrations,
    FastAPI Uvicorn server, and Next.js Turbopack frontend server with graceful termination.

.PARAMETER BackendOnly
    Starts only the FastAPI backend server on the configured port.

.PARAMETER FrontendOnly
    Starts only the Next.js frontend server on the configured port.

.PARAMETER Port
    Backend API server port (default: 8000).

.PARAMETER FrontendPort
    Next.js frontend web port (default: 3000).

.PARAMETER SkipMigration
    Skips running Alembic database migrations.
#>

[CmdletBinding()]
param(
    [switch]$BackendOnly,
    [switch]$FrontendOnly,
    [int]$Port = 8000,
    [int]$FrontendPort = 3000,
    [switch]$SkipMigration
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path "$PSScriptRoot\..").Path

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "     ShootingStar Research Platform - Local Runner       " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Validate Prerequisite Tools
Write-Host "`n[1/5] Checking environment prerequisites..." -ForegroundColor Yellow

$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Write-Error "Python virtual environment not found at .venv. Please run: python -m venv .venv; .\.venv\Scripts\pip install -e ."
    exit 1
}

$NodeCmd = Get-Command "node" -ErrorAction SilentlyContinue
$NpmCmd = Get-Command "npm" -ErrorAction SilentlyContinue

if (-not $NodeCmd -or -not $NpmCmd) {
    Write-Error "Node.js and npm must be installed and available in PATH."
    exit 1
}

$NodeVer = node --version
$NpmVer = npm --version
Write-Host "  [OK] Python: $VenvPython" -ForegroundColor Green
Write-Host "  [OK] Node.js: $NodeVer" -ForegroundColor Green
Write-Host "  [OK] npm: $NpmVer" -ForegroundColor Green

# 2. Environment Configuration Files
Write-Host "`n[2/5] Checking configuration files..." -ForegroundColor Yellow

$RootEnv = Join-Path $ProjectRoot ".env"
$RootEnvExample = Join-Path $ProjectRoot ".env.example"
if (-not (Test-Path $RootEnv)) {
    if (Test-Path $RootEnvExample) {
        Write-Host "  Creating .env from .env.example..." -ForegroundColor Cyan
        Copy-Item $RootEnvExample $RootEnv
    } else {
        Write-Warning "  Warning: .env and .env.example missing at project root."
    }
} else {
    Write-Host "  [OK] Root .env present" -ForegroundColor Green
}

$FrontendDir = Join-Path $ProjectRoot "frontend"
$FrontendEnvLocal = Join-Path $FrontendDir ".env.local"
$FrontendEnvExample = Join-Path $FrontendDir ".env.example"
if (-not (Test-Path $FrontendEnvLocal)) {
    if (Test-Path $FrontendEnvExample) {
        Write-Host "  Creating frontend/.env.local from frontend/.env.example..." -ForegroundColor Cyan
        Copy-Item $FrontendEnvExample $FrontendEnvLocal
    }
} else {
    Write-Host "  [OK] frontend/.env.local present" -ForegroundColor Green
}

# 3. Database Migrations
if (-not $FrontendOnly -and -not $SkipMigration) {
    Write-Host "`n[3/5] Running database migrations..." -ForegroundColor Yellow
    Push-Location (Join-Path $ProjectRoot "backend")
    try {
        & $VenvPython -m alembic upgrade head
        Write-Host "  [OK] Database schema is up to date" -ForegroundColor Green
    } catch {
        Write-Warning "  Alembic migration warning: $_. Verify database connectivity if using PostgreSQL."
    } finally {
        Pop-Location
    }
} else {
    Write-Host "`n[3/5] Skipping database migrations." -ForegroundColor DarkGray
}

# 4. Process Management & Teardown Setup
Write-Host "`n[4/5] Preparing services..." -ForegroundColor Yellow

$RunningProcesses = [System.Collections.Generic.List[System.Diagnostics.Process]]::new()

function Stop-AllServices {
    Write-Host "`nShutting down ShootingStar services..." -ForegroundColor Red
    foreach ($p in $RunningProcesses) {
        if ($p -and -not $p.HasExited) {
            Write-Host "  Terminating PID $($p.Id)..." -ForegroundColor DarkYellow
            try {
                $p.Kill()
            } catch {
                # Ignore process kill errors on shutdown
            }
        }
    }
    Write-Host "All services stopped." -ForegroundColor Green
}

# 5. Launch Services
Write-Host "`n[5/5] Launching applications..." -ForegroundColor Yellow

if (-not $FrontendOnly) {
    Write-Host "  Starting FastAPI backend on http://127.0.0.1:$Port..." -ForegroundColor Cyan
    $bePsi = New-Object System.Diagnostics.ProcessStartInfo
    $bePsi.FileName = $VenvPython
    $bePsi.Arguments = "-m uvicorn shootingstar.api.app:app --app-dir backend --host 127.0.0.1 --port $Port"
    $bePsi.WorkingDirectory = $ProjectRoot
    $bePsi.UseShellExecute = $false
    $bePsi.EnvironmentVariables["PYTHONPATH"] = (Join-Path $ProjectRoot "backend")
    $beProc = [System.Diagnostics.Process]::Start($bePsi)
    $RunningProcesses.Add($beProc)
    Write-Host "  [OK] Backend started (PID: $($beProc.Id))" -ForegroundColor Green
}

if (-not $BackendOnly) {
    Write-Host "  Starting Next.js frontend on http://127.0.0.1:$FrontendPort..." -ForegroundColor Cyan
    $fePsi = New-Object System.Diagnostics.ProcessStartInfo
    $fePsi.FileName = "npm.cmd"
    $fePsi.Arguments = "run dev -- -p $FrontendPort"
    $fePsi.WorkingDirectory = $FrontendDir
    $fePsi.UseShellExecute = $false
    $feProc = [System.Diagnostics.Process]::Start($fePsi)
    $RunningProcesses.Add($feProc)
    Write-Host "  [OK] Frontend started (PID: $($feProc.Id))" -ForegroundColor Green
}

Write-Host "`n==========================================================" -ForegroundColor Green
Write-Host "  ShootingStar is running!" -ForegroundColor Green
if (-not $FrontendOnly) {
    Write-Host "  - API Backend:   http://127.0.0.1:$Port" -ForegroundColor White
    Write-Host "  - API Docs:      http://127.0.0.1:$Port/docs" -ForegroundColor White
}
if (-not $BackendOnly) {
    Write-Host "  - Web Overview:  http://127.0.0.1:$FrontendPort" -ForegroundColor White
    Write-Host "  - Landing Page:  http://127.0.0.1:$FrontendPort/about" -ForegroundColor White
}
Write-Host "`nPress Ctrl+C to terminate all services." -ForegroundColor Yellow
Write-Host "==========================================================" -ForegroundColor Green

try {
    while ($true) {
        Start-Sleep -Seconds 1
        foreach ($p in $RunningProcesses) {
            if ($p.HasExited) {
                Write-Host "`nProcess PID $($p.Id) exited unexpectedly with code $($p.ExitCode)." -ForegroundColor Red
                return
            }
        }
    }
} finally {
    Stop-AllServices
}
