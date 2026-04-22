# Wealth Planning App — Stop Backend + Frontend
# Usage: .\stop_server.ps1

Set-Location $PSScriptRoot

function Stop-ServiceByPid {
    param([string]$File, [string]$Label, [int]$Port)
    $pidPath = Join-Path $PSScriptRoot $File
    $stopped = $false

    # Try PID file first
    if (Test-Path $pidPath) {
        $savedPid = (Get-Content $pidPath).Trim()
        if ($savedPid -and $savedPid -match '^\d+$') {
            $proc = Get-Process -Id ([int]$savedPid) -ErrorAction SilentlyContinue
            if ($proc) {
                Stop-Process -Id ([int]$savedPid) -Force
                Write-Host "$Label stopped (PID: $savedPid)" -ForegroundColor Green
                $stopped = $true
            }
        }
        Remove-Item $pidPath -Force
    }

    # Fallback: kill anything still listening on the port
    $listening = netstat -ano | Select-String ":${Port}\s.*LISTENING" | ForEach-Object {
        ($_ -split '\s+')[-1]
    } | Sort-Object -Unique
    foreach ($pid in $listening) {
        if ($pid -and $pid -ne '0') {
            Stop-Process -Id ([int]$pid) -Force -ErrorAction SilentlyContinue
            if (-not $stopped) {
                Write-Host "$Label stopped (port $Port, PID: $pid)" -ForegroundColor Green
                $stopped = $true
            }
        }
    }

    if (-not $stopped) {
        Write-Host "${Label} - not running" -ForegroundColor Gray
    }
}

Write-Host "Stopping Wealth Planning App..." -ForegroundColor Yellow
Stop-ServiceByPid "backend.pid"  "Backend"  8089
Stop-ServiceByPid "frontend.pid" "Frontend" 3080
Write-Host "Done." -ForegroundColor Green
