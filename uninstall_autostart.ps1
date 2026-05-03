# Wealth Planning App -- uninstall_autostart.ps1
#
# Removes the Windows Task Scheduler entry registered by install_autostart.ps1.
#
# Usage (elevated PowerShell):
#   .\uninstall_autostart.ps1
#   .\uninstall_autostart.ps1 -TaskName "<name>"

[CmdletBinding()]
param(
    [string]$TaskName = "WealthPlanning_Server"
)

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator
)
if (-not $isAdmin) {
    Write-Host "ERROR: must run from an elevated PowerShell." -ForegroundColor Red
    exit 1
}

$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if (-not $task) {
    Write-Host "Task '$TaskName' not registered. Nothing to do." -ForegroundColor Gray
    exit 0
}

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
Write-Host "Removed task: $TaskName" -ForegroundColor Green
