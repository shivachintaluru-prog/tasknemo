# Setup ALL TaskNemo scheduled tasks
# Run this once (elevated): powershell -ExecutionPolicy Bypass -File setup_all_schedulers.ps1

$scriptDir = $PSScriptRoot
$pythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $pythonExe) {
    Write-Error "Python not found in PATH."
    exit 1
}

Write-Host "Setting up TaskNemo schedulers..." -ForegroundColor Cyan
Write-Host "  Python: $pythonExe"
Write-Host "  Script dir: $scriptDir"
Write-Host ""

# ---- 1. TaskNemoRefresh: every 30 min, 8 AM - 6 PM weekdays ----

$taskName = "TaskNemoRefresh"
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

$action = New-ScheduledTaskAction `
    -Execute $pythonExe `
    -Argument "task_dashboard.py refresh" `
    -WorkingDirectory $scriptDir

$trigger = New-ScheduledTaskTrigger `
    -Weekly `
    -At "08:00" `
    -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday

$trigger.Repetition = (New-ScheduledTaskTrigger -Once -At "08:00" `
    -RepetitionInterval (New-TimeSpan -Minutes 30) `
    -RepetitionDuration (New-TimeSpan -Hours 10)).Repetition

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 5)

Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "Refresh TaskNemo every 30 min (readback, transitions, rescore, re-render)"

Write-Host "[OK] $taskName - every 30 min, 8 AM - 6 PM weekdays" -ForegroundColor Green

# ---- 2. TaskNemoFullSync: every 2 hours, 9 AM - 7 PM weekdays ----

$taskName = "TaskNemoFullSync"
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-ExecutionPolicy Bypass -File `"$scriptDir\full_sync.ps1`"" `
    -WorkingDirectory $scriptDir

$trigger = New-ScheduledTaskTrigger `
    -Weekly `
    -At "09:00" `
    -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday

$trigger.Repetition = (New-ScheduledTaskTrigger -Once -At "09:00" `
    -RepetitionInterval (New-TimeSpan -Hours 2) `
    -RepetitionDuration (New-TimeSpan -Hours 10)).Repetition

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 15) `
    -MultipleInstances IgnoreNew

Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "Full TaskNemo sync via Claude Code (WorkIQ queries + pipeline) every 2h"

Write-Host "[OK] $taskName - every 2 hours, 9 AM - 7 PM weekdays" -ForegroundColor Green

# ---- 3. TaskNemoQualityEval: daily at 7 AM weekdays ----

$taskName = "TaskNemoQualityEval"
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

$action = New-ScheduledTaskAction `
    -Execute $pythonExe `
    -Argument "task_dashboard.py agent run quality_eval" `
    -WorkingDirectory $scriptDir

$trigger = New-ScheduledTaskTrigger `
    -Weekly `
    -At "07:00" `
    -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 5)

Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "TaskNemo Quality Evaluation agent - daily diagnostics at 7 AM"

Write-Host "[OK] $taskName - daily at 7 AM weekdays" -ForegroundColor Green

# ---- Summary ----

Write-Host ""
Write-Host "All 3 scheduled tasks created:" -ForegroundColor Cyan
Write-Host "  TaskNemoRefresh    - every 30 min (8 AM - 6 PM) - readback + rescore + re-render"
Write-Host "  TaskNemoFullSync   - every 2 hours (9 AM - 7 PM) - WorkIQ queries via Claude Code"
Write-Host "  TaskNemoQualityEval - daily at 7 AM - duplicate/stale/health checks -> Quality Report.md"
Write-Host ""
Write-Host "To verify: Get-ScheduledTask | Where-Object { `$_.TaskName -like 'TaskNemo*' }" -ForegroundColor Yellow
