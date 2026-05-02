# Wealth Planning App -- install_autostart.ps1
#
# Registers a Windows Task Scheduler entry that runs start_server.ps1 -AutoStart
# at boot. See ~/.claude/skills/server-control/reference/autostart.md.
#
# Usage (elevated PowerShell):
#   .\install_autostart.ps1                                       # SYSTEM principal
#   .\install_autostart.ps1 -User <DOMAIN\user> -Password <pw>    # service account
#   .\install_autostart.ps1 -Force                                # overwrite existing task

[CmdletBinding()]
param(
    [string]$User,
    [string]$Password,
    [switch]$Force,
    [string]$TaskName    = "WealthPlanning_Server",
    [string]$Description = "Wealth Planning App at boot"
)

# Must be elevated
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator
)
if (-not $isAdmin) {
    Write-Host "ERROR: must run from an elevated PowerShell." -ForegroundColor Red
    exit 1
}
if (($User -and -not $Password) -or ($Password -and -not $User)) {
    Write-Host "ERROR: -User and -Password must be provided together." -ForegroundColor Red
    exit 1
}

$projectDir   = $PSScriptRoot
$startScript  = Join-Path $projectDir "start_server.ps1"
if (-not (Test-Path $startScript)) {
    Write-Host "ERROR: start_server.ps1 not found at $startScript" -ForegroundColor Red
    exit 1
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Autostart installer" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "App        : Wealth Planning App"
Write-Host "Task name  : $TaskName"
Write-Host "Project dir: $projectDir"
Write-Host "Run as     : $(if ($User) { $User } else { 'SYSTEM' })"
Write-Host ""

$psArgs = "-NoProfile -ExecutionPolicy Bypass -File `"$startScript`" -AutoStart"

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument $psArgs `
    -WorkingDirectory $projectDir

$trigger = New-ScheduledTaskTrigger -AtStartup
$trigger.Delay = "PT30S"

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 2) `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0)

if ($User) {
    $principal = New-ScheduledTaskPrincipal -UserId $User -LogonType Password -RunLevel Highest
    $registerArgs = @{
        TaskName = $TaskName; Action = $action; Trigger = $trigger
        Settings = $settings; Principal = $principal; Description = $Description
        User = $User; Password = $Password
    }
} else {
    $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
    $registerArgs = @{
        TaskName = $TaskName; Action = $action; Trigger = $trigger
        Settings = $settings; Principal = $principal; Description = $Description
    }
}

$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    if (-not $Force) {
        Write-Host "Task '$TaskName' already exists. Use -Force to overwrite." -ForegroundColor Yellow
        exit 1
    }
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed existing task '$TaskName'." -ForegroundColor Gray
}

Register-ScheduledTask @registerArgs | Out-Null
Write-Host "Registered task: $TaskName" -ForegroundColor Green
Write-Host ""
Write-Host "Verify with:" -ForegroundColor Gray
Write-Host "  Get-ScheduledTask -TaskName $TaskName | Format-List State, TaskName, LastRunTime" -ForegroundColor Gray
Write-Host ""
Write-Host "Test without rebooting:" -ForegroundColor Gray
Write-Host "  Start-ScheduledTask -TaskName $TaskName" -ForegroundColor Gray
Write-Host ""
Write-Host "Remove with: .\uninstall_autostart.ps1" -ForegroundColor Gray
