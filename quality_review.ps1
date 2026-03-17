# Quality Review: run QA agent, then have Claude Code review and fix issues
# Scheduled daily at 7 AM via TaskNemoQualityEval

$scriptDir = $PSScriptRoot
$promptFile = Join-Path $scriptDir "quality_review_prompt.md"
$logFile = Join-Path $scriptDir "data\quality_review_$(Get-Date -Format 'yyyyMMdd_HHmmss').txt"

Set-Location $scriptDir

$prompt = Get-Content $promptFile -Raw

# Run Claude Code in headless mode with tools to read/write tasks
claude -p $prompt --allowedTools "Bash,Read,Grep,Glob,Write,Edit" 2>&1 | Tee-Object -FilePath $logFile

Write-Host "`nQuality review log saved to: $logFile"
