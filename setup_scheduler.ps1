# Create a Windows Task Scheduler job for task dashboard refresh
# Runs every 30 minutes from 8 AM to 6 PM on weekdays

$taskName = "TaskNemoRefresh"
$pythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $pythonExe) {
    Write-Error "Python not found in PATH. Install Python 3.10+ and ensure it's on your PATH."
    exit 1
}
$scriptDir = $PSScriptRoot
$scriptArgs = "task_dashboard.py refresh"

# Remove existing task if present
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

# Action: run python task_dashboard.py refresh
$action = New-ScheduledTaskAction `
    -Execute $pythonExe `
    -Argument $scriptArgs `
    -WorkingDirectory $scriptDir

# Trigger: every 30 minutes, 8 AM to 6 PM, weekdays only
$trigger = New-ScheduledTaskTrigger `
    -Weekly `
    -At "08:00" `
    -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday

# Repetition: every 30 min for 10 hours (8 AM to 6 PM)
$trigger.Repetition = (New-ScheduledTaskTrigger -Once -At "08:00" -RepetitionInterval (New-TimeSpan -Minutes 30) -RepetitionDuration (New-TimeSpan -Hours 10)).Repetition

# Settings: don't wake computer, stop if on battery after 5 min
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 5)

# Register
Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "Refresh TaskNemo every 30 min (readback, transitions, rescore, re-render)"

Write-Host "Scheduled task '$taskName' created successfully."
Write-Host "  Runs every 30 min from 8:00 AM to 6:00 PM, weekdays only."
Write-Host "  Command: python task_dashboard.py refresh"
