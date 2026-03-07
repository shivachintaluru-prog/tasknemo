# Schedule full task dashboard sync via Claude Code
# Runs every 2 hours from 8 AM to 6 PM on weekdays

$taskName = "TaskNemoFullSync"
$scriptDir = $PSScriptRoot

# Remove existing task if present
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

# Action: run the full sync PowerShell script
$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-ExecutionPolicy Bypass -File `"$scriptDir\full_sync.ps1`"" `
    -WorkingDirectory $scriptDir

# Trigger: weekdays at 9 AM (offset from 8 AM refresh)
$trigger = New-ScheduledTaskTrigger `
    -Weekly `
    -At "09:00" `
    -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday

# Repetition: every 2 hours for 10 hours (9 AM to 7 PM)
$trigger.Repetition = (New-ScheduledTaskTrigger -Once -At "09:00" -RepetitionInterval (New-TimeSpan -Hours 2) -RepetitionDuration (New-TimeSpan -Hours 10)).Repetition

# Settings: allow up to 15 min, don't overlap
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

Write-Host "Scheduled task '$taskName' created successfully."
Write-Host "  Runs every 2 hours from 9:00 AM to 7:00 PM, weekdays only."
Write-Host "  Command: claude -p (full sync pipeline)"
