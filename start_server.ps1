# Wealth Planning App -- start_server.ps1
#
# Standardized start script. See ~/.claude/skills/server-control/SKILL.md.
#
# Hybrid app: launches FastAPI backend (uvicorn) + Next.js frontend together.
# Diverges from the single-process standard by tracking TWO PID files
# (backend.pid + frontend.pid) and TWO port pairs. The CONFIG block below
# enumerates them; stop_server.ps1 mirrors the structure.
#
# Modes:
#   .\start_server.ps1               # normal: rebuild frontend if stale, launch both
#   .\start_server.ps1 -Build        # force frontend rebuild before launch
#   .\start_server.ps1 -NoBuild      # skip stale check, launch with existing bundle
#   .\start_server.ps1 -AutoStart    # boot mode: implies -NoBuild, no prompts, no interactive checks

[CmdletBinding()]
param(
    [switch]$Build,
    [switch]$NoBuild,
    [switch]$AutoStart
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# === CONFIG ===
$AppName            = "Wealth Planning App"
$BindHost           = "127.0.0.1"
$BackendPort        = 8089
$FrontendPort       = 3080
$ExternalUrl        = "https://team-dashboard.lighthouse-canton.com:8081/"
$BackendPidFile     = Join-Path $PSScriptRoot "backend.pid"
$FrontendPidFile    = Join-Path $PSScriptRoot "frontend.pid"
$ModeFile           = Join-Path $PSScriptRoot "server.mode"
$LogDir             = Join-Path $PSScriptRoot "logs"
$BackendStdoutLog   = Join-Path $LogDir "backend.out.log"
$BackendStderrLog   = Join-Path $LogDir "backend.err.log"
$FrontendStdoutLog  = Join-Path $LogDir "frontend.out.log"
$FrontendStderrLog  = Join-Path $LogDir "frontend.err.log"
$VenvPython         = Join-Path $PSScriptRoot "venv\Scripts\python.exe"
$NextBin            = Join-Path $PSScriptRoot "frontend\node_modules\next\dist\bin\next"
# === END CONFIG ===

if ($AutoStart) { $NoBuild = $true }

if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }

# --- Pre-flight: stale PID ---
function Test-PidFile {
    param([string]$File, [string]$Label)
    if (-not (Test-Path $File)) { return $false }
    $savedPid = (Get-Content $File -ErrorAction SilentlyContinue).Trim()
    if ($savedPid -and $savedPid -match '^\d+$') {
        $running = Get-Process -Id ([int]$savedPid) -ErrorAction SilentlyContinue
        if ($running) {
            Write-Host "$Label is already running (PID $savedPid). Run .\stop_server.ps1 first." -ForegroundColor Red
            return $true
        }
    }
    Remove-Item $File -Force -ErrorAction SilentlyContinue
    return $false
}
if (Test-PidFile $BackendPidFile  "Backend")  { exit 1 }
if (Test-PidFile $FrontendPidFile "Frontend") { exit 1 }

# --- Pre-flight: dependencies ---
if (-not (Test-Path $VenvPython)) {
    Write-Host "Python venv not found at $VenvPython. Run: python -m venv venv" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path "$PSScriptRoot\frontend\node_modules")) {
    Write-Host "node_modules not found. Run: cd frontend; npm install" -ForegroundColor Red
    exit 1
}

# --- Frontend build invalidation (preserved from original run_server.ps1) ---
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
    #    env-var override (the run_server.ps1 bug we previously fixed), the bundle
    #    may have a stale URL baked in even though all files are "fresh".
    $expected = Get-EnvValue (Join-Path $PSScriptRoot "frontend\.env") "NEXT_PUBLIC_API_URL"
    if ($expected) {
        $sample = Get-ChildItem -Path "$nextDir\static\chunks" -Recurse -Filter "*.js" -ErrorAction SilentlyContinue |
            Select-Object -First 30
        $found = $false
        foreach ($f in $sample) {
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

# --- Banner header ---
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  $AppName" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# --- Frontend rebuild (skipped under -AutoStart / -NoBuild) ---
if (-not $NoBuild) {
    $needsBuild = [bool]$Build
    if (-not $needsBuild) { $needsBuild = Test-FrontendStale }
    if ($needsBuild) {
        Write-Host "Building frontend (sources changed since last build)..." -ForegroundColor Yellow
        # Clear any NEXT_PUBLIC_* env vars leaking from the caller's session so
        # `next build` reads frontend/.env as the only source of truth. A previous
        # version of this script set NEXT_PUBLIC_API_URL=http://...:8081 (wrong
        # URL, no /api) which lingered in the user's PowerShell session even
        # after we removed that line, silently re-poisoning every subsequent
        # build. .env says https://...:8081/api -- that must win.
        Get-ChildItem env: | Where-Object { $_.Name -like "NEXT_PUBLIC_*" } | ForEach-Object {
            Write-Host "  Clearing leaked env var: $($_.Name)" -ForegroundColor Gray
            Remove-Item "env:$($_.Name)"
        }
        Push-Location "$PSScriptRoot\frontend"
        try {
            & npx next build
            $buildExit = $LASTEXITCODE
        } finally { Pop-Location }
        if ($buildExit -ne 0 -or -not (Test-Path "$PSScriptRoot\frontend\.next\BUILD_ID")) {
            Write-Host "Frontend build failed (exit $buildExit). Aborting." -ForegroundColor Red
            exit 1
        }
        Write-Host "  Build complete." -ForegroundColor Green
    } else {
        Write-Host "Frontend build is up-to-date - skipping rebuild." -ForegroundColor Gray
    }
} else {
    Write-Host "Skipping frontend build check ($(if ($AutoStart) { '-AutoStart' } else { '-NoBuild' }))." -ForegroundColor Gray
}

# --- Start backend ---
Write-Host "Starting backend (FastAPI/Uvicorn)..." -ForegroundColor Yellow
$backendProc = Start-Process -FilePath $VenvPython `
    -ArgumentList "-m", "uvicorn", "backend.main:app", "--host", $BindHost, "--port", "$BackendPort" `
    -WorkingDirectory $PSScriptRoot `
    -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput $BackendStdoutLog `
    -RedirectStandardError  $BackendStderrLog
if (-not $backendProc) {
    Write-Host "Failed to launch backend." -ForegroundColor Red
    exit 1
}
$backendProc.Id | Out-File -FilePath $BackendPidFile -Encoding ascii -NoNewline
Write-Host "  Backend started (PID $($backendProc.Id)) on http://${BindHost}:${BackendPort}" -ForegroundColor Green

# --- Start frontend ---
# Use node directly (not npx) so the captured PID is the actual server process.
Write-Host "Starting frontend (Next.js)..." -ForegroundColor Yellow
$frontendProc = Start-Process -FilePath "node.exe" `
    -ArgumentList $NextBin, "start", "-p", "$FrontendPort" `
    -WorkingDirectory "$PSScriptRoot\frontend" `
    -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput $FrontendStdoutLog `
    -RedirectStandardError  $FrontendStderrLog
if (-not $frontendProc) {
    Write-Host "Failed to launch frontend. Stopping backend so we don't leave a half-up service." -ForegroundColor Red
    Stop-Process -Id $backendProc.Id -Force -ErrorAction SilentlyContinue
    Remove-Item $BackendPidFile -Force -ErrorAction SilentlyContinue
    exit 1
}
$frontendProc.Id | Out-File -FilePath $FrontendPidFile -Encoding ascii -NoNewline
Write-Host "  Frontend started (PID $($frontendProc.Id)) on http://${BindHost}:${FrontendPort}" -ForegroundColor Green

"hybrid" | Out-File -FilePath $ModeFile -Encoding ascii -NoNewline

# --- Wait + health check (skipped under -AutoStart) ---
if (-not $AutoStart) {
    Write-Host ""
    Write-Host "Waiting for services to be ready..." -ForegroundColor Gray
    Start-Sleep -Seconds 5
    try {
        $health = Invoke-RestMethod -Uri "http://${BindHost}:${BackendPort}/health" -TimeoutSec 5
        Write-Host "  Backend health: $($health.status)" -ForegroundColor Green
    } catch {
        Write-Host "  Backend not responding yet (may still be starting)" -ForegroundColor Yellow
    }
}

# --- Standardized banner ---
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "$AppName" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ("Backend PID  : {0}" -f $backendProc.Id)  -ForegroundColor Green
Write-Host ("Frontend PID : {0}" -f $frontendProc.Id) -ForegroundColor Green
Write-Host ("Internal URL : http://{0}:{1} (backend) / http://{0}:{2} (frontend)" -f $BindHost, $BackendPort, $FrontendPort)
Write-Host ("External URL : {0}" -f $ExternalUrl)
Write-Host ("PID file     : {0}, {1}" -f $BackendPidFile, $FrontendPidFile)
Write-Host ("Log          : {0}" -f $LogDir)
Write-Host ""
Write-Host "Stop with: .\stop_server.ps1" -ForegroundColor Gray
