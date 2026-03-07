# TaskNemo Updater
# Pulls latest code, installs deps, merges new config keys, migrates task schema

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$scriptDir = $PSScriptRoot

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  TaskNemo Update" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ---------------------------------------------------------------
# Step 1: Pull latest code
# ---------------------------------------------------------------
Write-Host "[1/4] Pulling latest code..." -ForegroundColor Yellow

Set-Location $scriptDir
$gitStatus = & git status --porcelain 2>&1
if ($gitStatus) {
    Write-Host "  WARNING  You have local changes:" -ForegroundColor DarkYellow
    Write-Host $gitStatus -ForegroundColor Gray
    $proceed = Read-Host "  Continue with git pull? Local changes may conflict (y/N)"
    if ($proceed -ne "y" -and $proceed -ne "Y") {
        Write-Host "  Aborted." -ForegroundColor Red
        exit 0
    }
}

& git pull --ff-only 2>&1 | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
if ($LASTEXITCODE -ne 0) {
    Write-Host "  FAIL  git pull failed — resolve manually" -ForegroundColor Red
    exit 1
}
Write-Host "  OK  Code updated" -ForegroundColor Green
Write-Host ""

# ---------------------------------------------------------------
# Step 2: Install/update dependencies
# ---------------------------------------------------------------
Write-Host "[2/4] Updating dependencies..." -ForegroundColor Yellow

$reqFile = Join-Path $scriptDir "requirements.txt"
if (Test-Path $reqFile) {
    & python -m pip install -r $reqFile --quiet 2>&1 | Out-Null
    Write-Host "  OK  Dependencies updated" -ForegroundColor Green
} else {
    Write-Host "  SKIP  No requirements.txt" -ForegroundColor DarkYellow
}
Write-Host ""

# ---------------------------------------------------------------
# Step 3: Upgrade config + migrate tasks
# ---------------------------------------------------------------
Write-Host "[3/4] Upgrading config and task schema..." -ForegroundColor Yellow

& python (Join-Path $scriptDir "task_dashboard.py") upgrade 2>&1 | ForEach-Object { Write-Host "  $_" -ForegroundColor Gray }
Write-Host ""

# ---------------------------------------------------------------
# Step 4: Verify
# ---------------------------------------------------------------
Write-Host "[4/4] Verifying..." -ForegroundColor Yellow

& python (Join-Path $scriptDir "task_dashboard.py") check
Write-Host ""

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Update Complete" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
