# Register a one-time Windows Scheduled Task to run the job application engine.
# Run in PowerShell (same Windows user that should run Chrome/automation):
#   cd <project-root>
#   .\scripts\register_windows_demo_task.ps1 -MinutesFromNow 3
#
# Prereqs: wbl-backend running, MySQL, one candidate with run_weekly_workflow=1,
#          project .env: BACKEND_URL (with /api), SCHEDULER_INTERNAL_SECRET matching backend.

param(
    [int]$MinutesFromNow = 3,
    [string]$TaskName = "WBL-JobApplicationEngine-Demo"
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (-not (Test-Path (Join-Path $projectRoot "scripts\main.py"))) {
    Write-Error "Could not find scripts\main.py under project root: $projectRoot"
}

$batPath = Join-Path $projectRoot "run_engine_scheduler.bat"
if (-not (Test-Path $batPath)) {
    Write-Error "Missing run_engine_scheduler.bat at $batPath"
}

$start = (Get-Date).AddMinutes($MinutesFromNow)

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

$action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$batPath`""
$trigger = New-ScheduledTaskTrigger -Once -At $start
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null

Write-Host "Created task '$TaskName' to run once at $start (local time)."
Write-Host "Command: cmd.exe /c `"$batPath`""
Write-Host "Logs:    $(Join-Path $projectRoot 'logs')"
Write-Host ""
Write-Host "Verify: Get-ScheduledTask -TaskName '$TaskName' | Select-Object TaskName, State, NextRunTime"
Write-Host "Remove: Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false"
