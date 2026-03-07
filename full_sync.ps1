# Full TaskNemo sync via Claude Code headless mode
# Runs claude -p with the sync prompt, working in the project directory

$scriptDir = $PSScriptRoot
$promptFile = Join-Path $scriptDir "full_sync_prompt.md"
$logFile = Join-Path $scriptDir "data\sync_log_$(Get-Date -Format 'yyyyMMdd_HHmmss').txt"

Set-Location $scriptDir

$prompt = Get-Content $promptFile -Raw

# Run Claude Code in headless print mode
claude -p $prompt --allowedTools "mcp__workiq__ask_work_iq,Bash,Read,Grep,Glob,Write,Edit" 2>&1 | Tee-Object -FilePath $logFile

Write-Host "`nSync log saved to: $logFile"
