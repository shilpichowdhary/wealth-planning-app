# Wealth Planning App -- stop_server.ps1
#
# Standardized stop script. See ~/.claude/skills/server-control/SKILL.md.
#
# Safety invariant:
#   This script will ONLY signal processes whose executable path or
#   command line is anchored under $PSScriptRoot. It will NEVER pattern-
#   match against unrelated node/python/cmd processes elsewhere on the
#   VM. See reference/core.md for the rationale (KB_POC, 2026-05-02).
#
# Hybrid app: stops both backend (uvicorn :8089) and frontend (next :3080),
# tracked via two PID files.

[CmdletBinding()]
param([switch]$Quiet)

$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot

# === CONFIG ===
$AppName            = "Wealth Planning App"
$Ports              = @(8089, 3080)
$PidFiles           = @(
    (Join-Path $PSScriptRoot "backend.pid"),
    (Join-Path $PSScriptRoot "frontend.pid")
)
$ModeFile           = Join-Path $PSScriptRoot "server.mode"
$LegacyPidFiles     = @()
$EnableOrphanSweep  = $false
$OrphanProcessNames = @("node","python")
# === END CONFIG ===

function Write-Info($m, $c="Gray") { if (-not $Quiet) { Write-Host $m -ForegroundColor $c } }

Write-Info "========================================" Cyan
Write-Info "$AppName -- stopping" Cyan
Write-Info "========================================" Cyan

function Stop-ProcTree([int]$ProcessId) {
    $children = Get-CimInstance Win32_Process -Filter "ParentProcessId = $ProcessId" -ErrorAction SilentlyContinue
    foreach ($child in $children) { Stop-ProcTree ([int]$child.ProcessId) }
    try {
        Stop-Process -Id $ProcessId -Force -ErrorAction Stop
        Write-Info "Stopped PID $ProcessId" Green
    } catch {
        if ($_.Exception.Message -match "Cannot find a process") {
            Write-Info "PID $ProcessId already gone" Gray
        } else {
            Write-Info "Error stopping PID $ProcessId : $($_.Exception.Message)" Red
        }
    }
}

# 1. Stop tracked PIDs (each PID file is the head of its own tree)
$foundPid = $false
foreach ($pidPath in @($PidFiles) + $LegacyPidFiles) {
    if (-not (Test-Path $pidPath)) { continue }
    $savedPid = (Get-Content $pidPath -ErrorAction SilentlyContinue).Trim()
    if ($savedPid -and $savedPid -match '^\d+$') {
        $foundPid = $true
        Stop-ProcTree ([int]$savedPid)
    }
    Remove-Item $pidPath -Force -ErrorAction SilentlyContinue
}
Remove-Item $ModeFile -Force -ErrorAction SilentlyContinue

if (-not $foundPid) {
    Write-Info "No PID file found -- nothing was tracked." Yellow
}

# 2. Optional orphan sweep -- repo-scoped (disabled by default)
if ($EnableOrphanSweep) {
    $repoRoot = $PSScriptRoot
    $candidates = Get-Process -Name $OrphanProcessNames -ErrorAction SilentlyContinue
    foreach ($p in $candidates) {
        try {
            $proc = Get-CimInstance Win32_Process -Filter "ProcessId = $($p.Id)" -ErrorAction SilentlyContinue
            if (-not $proc) { continue }
            $cmd = $proc.CommandLine
            $exe = $proc.ExecutablePath
            if (-not $cmd) { continue }
            $inRepo = ($cmd -like "*$repoRoot*") -or ($exe -and ($exe -like "$repoRoot*"))
            if (-not $inRepo) { continue }
            Write-Info "Orphan in repo: PID $($p.Id)" Yellow
            Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
        } catch { }
    }
}

# 3. Port-listener fallback -- only kill if listener is anchored in this repo
foreach ($port in $Ports) {
    $conns = Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue
    foreach ($c in $conns) {
        $listenerPid = $c.OwningProcess
        if (-not $listenerPid -or $listenerPid -eq 0) { continue }
        $proc = Get-CimInstance Win32_Process -Filter "ProcessId = $listenerPid" -ErrorAction SilentlyContinue
        if (-not $proc) { continue }
        $cmd = $proc.CommandLine
        $exe = $proc.ExecutablePath
        $inRepo = ($exe -and $exe -like "$PSScriptRoot*") -or ($cmd -and $cmd -like "*$PSScriptRoot*")
        if ($inRepo) {
            Stop-Process -Id $listenerPid -Force -ErrorAction SilentlyContinue
            Write-Info "Stopped PID $listenerPid (port $port, repo-scoped)" Green
        } else {
            Write-Info "WARNING: PID $listenerPid is listening on :$port but is NOT from this repo -- not killing." Red
            Write-Info "  exe: $exe" Yellow
        }
    }
}

# 4. Verify ports
Start-Sleep -Seconds 1
foreach ($port in $Ports) {
    try {
        $r = Invoke-WebRequest "http://127.0.0.1:$port/" -UseBasicParsing -TimeoutSec 2
        Write-Info "WARNING: something still responding on :$port (status $($r.StatusCode))." Red
    } catch {
        Write-Info "Port :$port is down." Green
    }
}

Write-Info ""
Write-Info "Teardown complete." Cyan
