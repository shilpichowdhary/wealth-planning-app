# Wealth Planning App — Start Backend + Frontend
# Usage: .\run_server.ps1
#
# Starts:
#   1. FastAPI backend (Uvicorn) on 127.0.0.1:8088
#   2. Next.js frontend on 127.0.0.1:3080
#
# IIS site "WealthPlanning" on port 8081 proxies external traffic to both.
# PIDs are saved to backend.pid / frontend.pid for later shutdown.

Set-Location $PSScriptRoot

$BACKEND_HOST  = "127.0.0.1"
$BACKEND_PORT  = "8088"
$FRONTEND_PORT = "3080"

# ── Helper: check PID file ────────────────────────────────────────────
function Test-PidFile {
    param([string]$File, [string]$Label)
    $pidPath = Join-Path $PSScriptRoot $File
    if (Test-Path $pidPath) {
        $savedPid = (Get-Content $pidPath).Trim()
        if ($savedPid -and $savedPid -match '^\d+$') {
            $running = Get-Process -Id ([int]$savedPid) -ErrorAction SilentlyContinue
            if ($running) {
                Write-Host "$Label is already running (PID: $savedPid)." -ForegroundColor Red
                Write-Host "Run .\stop_server.ps1 first." -ForegroundColor Yellow
                return $true
            }
        }
        Remove-Item $pidPath -Force
        Write-Host "Removed stale $File" -ForegroundColor Gray
    }
    return $false
}

# ── Pre-flight checks ─────────────────────────────────────────────────
if (Test-PidFile "backend.pid" "Backend") { exit 1 }
if (Test-PidFile "frontend.pid" "Frontend") { exit 1 }

# Check venv exists
if (-not (Test-Path "$PSScriptRoot\venv\Scripts\python.exe")) {
    Write-Host "Python venv not found. Run: python -m venv venv" -ForegroundColor Red
    exit 1
}

# Check node_modules exists
if (-not (Test-Path "$PSScriptRoot\frontend\node_modules")) {
    Write-Host "node_modules not found. Run: cd frontend && npm install" -ForegroundColor Red
    exit 1
}

# ── Start backend ─────────────────────────────────────────────────────
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Wealth Planning App" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Starting backend (FastAPI/Uvicorn)..." -ForegroundColor Yellow
$backendProc = Start-Process -FilePath "$PSScriptRoot\venv\Scripts\python.exe" `
    -ArgumentList "-m", "uvicorn", "backend.main:app", "--host", $BACKEND_HOST, "--port", $BACKEND_PORT `
    -WorkingDirectory $PSScriptRoot `
    -WindowStyle Hidden `
    -PassThru

$backendProc.Id | Out-File -FilePath "$PSScriptRoot\backend.pid" -Encoding ascii -NoNewline
Write-Host "  Backend started (PID: $($backendProc.Id)) on http://${BACKEND_HOST}:${BACKEND_PORT}" -ForegroundColor Green

# ── Build frontend if needed ──────────────────────────────────────────
$nextDir = Join-Path $PSScriptRoot "frontend\.next"
if (-not (Test-Path $nextDir)) {
    Write-Host "Building frontend (first run)..." -ForegroundColor Yellow
    $env:NEXT_PUBLIC_API_URL = "http://team-dashboard.lighthouse-canton.com:8081"
    Push-Location "$PSScriptRoot\frontend"
    & npx next build
    Pop-Location
    if (-not (Test-Path $nextDir)) {
        Write-Host "Frontend build failed." -ForegroundColor Red
        exit 1
    }
    Write-Host "  Build complete." -ForegroundColor Green
}

# ── Start frontend ────────────────────────────────────────────────────
Write-Host "Starting frontend (Next.js)..." -ForegroundColor Yellow

# Use node directly (not npx) so the PID we capture is the actual server process
$nextBin = Join-Path $PSScriptRoot "frontend\node_modules\next\dist\bin\next"
$frontendProc = Start-Process -FilePath "node.exe" `
    -ArgumentList $nextBin, "start", "-p", $FRONTEND_PORT `
    -WorkingDirectory "$PSScriptRoot\frontend" `
    -WindowStyle Hidden `
    -PassThru

$frontendProc.Id | Out-File -FilePath "$PSScriptRoot\frontend.pid" -Encoding ascii -NoNewline
Write-Host "  Frontend started (PID: $($frontendProc.Id)) on http://${BACKEND_HOST}:${FRONTEND_PORT}" -ForegroundColor Green

# ── Wait for services ─────────────────────────────────────────────────
Write-Host ""
Write-Host "Waiting for services to be ready..." -ForegroundColor Gray
Start-Sleep -Seconds 5

# Test backend health
try {
    $health = Invoke-RestMethod -Uri "http://${BACKEND_HOST}:${BACKEND_PORT}/health" -TimeoutSec 5
    Write-Host "  Backend health: $($health.status)" -ForegroundColor Green
} catch {
    Write-Host "  Backend not responding yet (may still be starting)" -ForegroundColor Yellow
}

# ── Summary ───────────────────────────────────────────────────────────
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Services running:" -ForegroundColor Cyan
Write-Host "    Backend:  http://${BACKEND_HOST}:${BACKEND_PORT}  (PID: $($backendProc.Id))" -ForegroundColor White
Write-Host "    Frontend: http://${BACKEND_HOST}:${FRONTEND_PORT}  (PID: $($frontendProc.Id))" -ForegroundColor White
Write-Host "    External: http://team-dashboard.lighthouse-canton.com:8081" -ForegroundColor White
Write-Host ""
Write-Host "  To stop: .\stop_server.ps1" -ForegroundColor Gray
Write-Host "========================================" -ForegroundColor Cyan
