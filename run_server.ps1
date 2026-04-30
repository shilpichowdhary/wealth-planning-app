# Wealth Planning App — Start Backend + Frontend
# Usage: .\run_server.ps1
#
# Starts:
#   1. FastAPI backend (Uvicorn) on 127.0.0.1:8089
#   2. Next.js frontend on 127.0.0.1:3080
#
# IIS site "WealthPlanning" on port 8081 proxies external traffic to both.
# PIDs are saved to backend.pid / frontend.pid for later shutdown.

Set-Location $PSScriptRoot

$BACKEND_HOST  = "127.0.0.1"
$BACKEND_PORT  = "8089"
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

# Build frontend if missing or stale ----------------------------------
# 'next start' serves the prebuilt bundle in .next/. If any source file
# is newer than .next/BUILD_ID we MUST rebuild; otherwise the server
# ships the old code regardless of how many times we restart. This
# previously bit us during the deck-pipeline rollout: page.tsx edits
# never made it into the served bundle until the build was redone.
function Get-EnvValue {
    param([string]$EnvFile, [string]$Key)
    if (-not (Test-Path $EnvFile)) { return $null }
    foreach ($line in Get-Content $EnvFile) {
        if ($line -match "^\s*$Key\s*=\s*(.*?)\s*$") {
            return $matches[1].Trim('"').Trim("'")
        }
    }
    return $null
}

function Test-FrontendStale {
    $nextDir = Join-Path $PSScriptRoot "frontend\.next"
    $buildId = Join-Path $nextDir "BUILD_ID"
    if (-not (Test-Path $buildId)) { return $true }
    $buildTime = (Get-Item $buildId).LastWriteTime

    # 1. Source roots: anything that, when edited, requires a rebuild.
    $sourceDirs = @("app", "components", "lib", "public") |
        ForEach-Object { Join-Path $PSScriptRoot "frontend\$_" }
    foreach ($dir in $sourceDirs) {
        if (-not (Test-Path $dir)) { continue }
        $newer = Get-ChildItem -Path $dir -Recurse -File -ErrorAction SilentlyContinue |
            Where-Object { $_.LastWriteTime -gt $buildTime } |
            Select-Object -First 1
        if ($newer) {
            Write-Host "  Stale: $($newer.FullName.Substring($PSScriptRoot.Length + 1))" -ForegroundColor Gray
            return $true
        }
    }

    # 2. Top-level config files. .env is included so any env edit triggers
    #    a rebuild (NEXT_PUBLIC_* vars are baked into the bundle at build time).
    $sourceFiles = @(
        ".env", ".env.local", ".env.production", ".env.production.local",
        "package.json", "package-lock.json",
        "tailwind.config.ts", "tailwind.config.js",
        "next.config.js", "next.config.mjs", "next.config.ts",
        "tsconfig.json", "postcss.config.js", "postcss.config.mjs"
    ) | ForEach-Object { Join-Path $PSScriptRoot "frontend\$_" }
    foreach ($f in $sourceFiles) {
        if ((Test-Path $f) -and ((Get-Item $f).LastWriteTime -gt $buildTime)) {
            Write-Host "  Stale: $((Get-Item $f).Name)" -ForegroundColor Gray
            return $true
        }
    }

    # 3. Sanity: confirm the bundle actually contains the NEXT_PUBLIC_API_URL
    #    that .env says it should. If a previous build was poisoned by an
    #    env-var override (the run_server.ps1 bug we just fixed), the bundle
    #    may have a stale URL baked in even though all files are "fresh".
    $expected = Get-EnvValue (Join-Path $PSScriptRoot "frontend\.env") "NEXT_PUBLIC_API_URL"
    if ($expected) {
        $sample = Get-ChildItem -Path "$nextDir\static\chunks" -Recurse -Filter "*.js" -ErrorAction SilentlyContinue |
            Select-Object -First 30
        $found = $false
        foreach ($f in $sample) {
            # Select-String -Quiet -SimpleMatch works across all PS versions;
            # avoids the Get-Content -Raw incompatibility on some hosts.
            if (Select-String -Path $f.FullName -Pattern $expected -SimpleMatch -Quiet -ErrorAction SilentlyContinue) {
                $found = $true; break
            }
        }
        if (-not $found) {
            Write-Host "  Stale: bundle does not contain expected NEXT_PUBLIC_API_URL ($expected)" -ForegroundColor Gray
            return $true
        }
    }

    return $false
}

if (Test-FrontendStale) {
    Write-Host "Building frontend (sources changed since last build)..." -ForegroundColor Yellow
    # Clear any NEXT_PUBLIC_* env vars leaking from the caller's session so
    # `next build` reads frontend/.env as the only source of truth. A previous
    # version of this script set NEXT_PUBLIC_API_URL=http://...:8081 (wrong
    # URL, no /api) which lingered in the user's PowerShell session even
    # after we removed that line, silently re-poisoning every subsequent
    # build. .env says https://...:8081/api — that must win.
    Get-ChildItem env: | Where-Object { $_.Name -like "NEXT_PUBLIC_*" } | ForEach-Object {
        Write-Host "  Clearing leaked env var: $($_.Name)" -ForegroundColor Gray
        Remove-Item "env:$($_.Name)"
    }
    Push-Location "$PSScriptRoot\frontend"
    & npx next build
    $buildExit = $LASTEXITCODE
    Pop-Location
    if ($buildExit -ne 0 -or -not (Test-Path "$PSScriptRoot\frontend\.next\BUILD_ID")) {
        Write-Host "Frontend build failed (exit $buildExit). Aborting." -ForegroundColor Red
        # Kill the backend we just started so we don't leave a half-up service.
        Stop-Process -Id $backendProc.Id -Force -ErrorAction SilentlyContinue
        Remove-Item "$PSScriptRoot\backend.pid" -Force -ErrorAction SilentlyContinue
        exit 1
    }
    Write-Host "  Build complete." -ForegroundColor Green
} else {
    Write-Host "Frontend build is up-to-date - skipping rebuild." -ForegroundColor Gray
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
