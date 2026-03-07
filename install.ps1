# TaskNemo Installer
# Checks prerequisites, installs dependencies, initializes config, sets up schedulers

param(
    [string]$VaultPath,
    [switch]$SkipSchedulers
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$scriptDir = $PSScriptRoot

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  TaskNemo Installer" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ---------------------------------------------------------------
# Step 1: Check prerequisites
# ---------------------------------------------------------------
Write-Host "[1/6] Checking prerequisites..." -ForegroundColor Yellow

$allGood = $true

# Python
$pythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source
if ($pythonExe) {
    $pyVer = & python --version 2>&1
    Write-Host "  OK  Python: $pyVer ($pythonExe)" -ForegroundColor Green
} else {
    Write-Host "  MISSING  Python not found in PATH" -ForegroundColor Red
    Write-Host "           Install Python 3.10+ from https://python.org and add to PATH" -ForegroundColor Red
    $allGood = $false
}

# npm
$npmExe = (Get-Command npm -ErrorAction SilentlyContinue).Source
if ($npmExe) {
    $npmVer = & npm --version 2>&1
    Write-Host "  OK  npm: v$npmVer" -ForegroundColor Green
} else {
    Write-Host "  MISSING  npm not found in PATH" -ForegroundColor Red
    Write-Host "           Install Node.js 18+ from https://nodejs.org" -ForegroundColor Red
    $allGood = $false
}

# Claude Code
$claudeExe = (Get-Command claude -ErrorAction SilentlyContinue).Source
if ($claudeExe) {
    Write-Host "  OK  Claude Code: $claudeExe" -ForegroundColor Green
} else {
    Write-Host "  OPTIONAL  Claude Code not found (needed for full sync)" -ForegroundColor DarkYellow
    Write-Host "            Install: npm install -g @anthropic-ai/claude-code" -ForegroundColor DarkYellow
}

# WorkIQ
$workiqExe = (Get-Command workiq -ErrorAction SilentlyContinue).Source
if ($workiqExe) {
    Write-Host "  OK  WorkIQ: $workiqExe" -ForegroundColor Green
} else {
    Write-Host "  OPTIONAL  WorkIQ not found (needed for full sync)" -ForegroundColor DarkYellow
    Write-Host "            Install: npm install -g workiq" -ForegroundColor DarkYellow
}

if (-not $allGood) {
    Write-Host ""
    Write-Host "Fix the missing prerequisites above, then re-run this script." -ForegroundColor Red
    exit 1
}

Write-Host ""

# ---------------------------------------------------------------
# Step 2: Install pip dependencies
# ---------------------------------------------------------------
Write-Host "[2/6] Installing Python dependencies..." -ForegroundColor Yellow

$reqFile = Join-Path $scriptDir "requirements.txt"
if (Test-Path $reqFile) {
    & python -m pip install -r $reqFile --quiet 2>&1 | Out-Null
    Write-Host "  OK  pip dependencies installed" -ForegroundColor Green
} else {
    Write-Host "  SKIP  No requirements.txt found" -ForegroundColor DarkYellow
}

Write-Host ""

# ---------------------------------------------------------------
# Step 3: Initialize data files
# ---------------------------------------------------------------
Write-Host "[3/6] Initializing data files..." -ForegroundColor Yellow

$configPath = Join-Path $scriptDir "data\config.json"
if (Test-Path $configPath) {
    Write-Host "  SKIP  data/config.json already exists (use 'python task_dashboard.py init --force' to reset)" -ForegroundColor DarkYellow
} else {
    if (-not $VaultPath) {
        $defaultVault = Join-Path $env:USERPROFILE "Documents\TaskVault"
        $VaultPath = Read-Host "  Obsidian vault path [$defaultVault]"
        if ([string]::IsNullOrWhiteSpace($VaultPath)) {
            $VaultPath = $defaultVault
        }
    }

    & python (Join-Path $scriptDir "task_dashboard.py") init --vault-path $VaultPath
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  FAIL  Initialization failed" -ForegroundColor Red
        exit 1
    }

    # Create vault directory if it doesn't exist
    if (-not (Test-Path $VaultPath)) {
        New-Item -ItemType Directory -Path $VaultPath -Force | Out-Null
        Write-Host "  OK  Created vault directory: $VaultPath" -ForegroundColor Green
    }
}

Write-Host ""

# ---------------------------------------------------------------
# Step 4: Configure WorkIQ MCP
# ---------------------------------------------------------------
Write-Host "[4/6] Configuring WorkIQ MCP..." -ForegroundColor Yellow

$mcpPath = Join-Path $scriptDir ".mcp.json"
if (Test-Path $mcpPath) {
    Write-Host "  SKIP  .mcp.json already exists" -ForegroundColor DarkYellow
} elseif ($workiqExe) {
    $mcpConfig = @{
        mcpServers = @{
            workiq = @{
                command = $workiqExe
                args = @("mcp")
            }
        }
    } | ConvertTo-Json -Depth 3

    Set-Content -Path $mcpPath -Value $mcpConfig -Encoding UTF8
    Write-Host "  OK  Created .mcp.json (WorkIQ at $workiqExe)" -ForegroundColor Green
} else {
    Write-Host "  SKIP  WorkIQ not installed, skipping .mcp.json" -ForegroundColor DarkYellow
}

Write-Host ""

# ---------------------------------------------------------------
# Step 5: Set up schedulers (optional)
# ---------------------------------------------------------------
Write-Host "[5/6] Task schedulers..." -ForegroundColor Yellow

if ($SkipSchedulers) {
    Write-Host "  SKIP  Skipped (--SkipSchedulers)" -ForegroundColor DarkYellow
} else {
    $setupSchedulers = Read-Host "  Set up automatic refresh & sync schedulers? (y/N)"
    if ($setupSchedulers -eq "y" -or $setupSchedulers -eq "Y") {
        Write-Host ""
        Write-Host "  Setting up lightweight refresh (every 30 min, weekdays)..." -ForegroundColor Gray
        & powershell -ExecutionPolicy Bypass -File (Join-Path $scriptDir "setup_scheduler.ps1")
        Write-Host ""

        if ($claudeExe) {
            Write-Host "  Setting up full sync (every 2 hours, weekdays)..." -ForegroundColor Gray
            & powershell -ExecutionPolicy Bypass -File (Join-Path $scriptDir "setup_full_sync_scheduler.ps1")
        } else {
            Write-Host "  SKIP  Full sync scheduler requires Claude Code" -ForegroundColor DarkYellow
        }
    } else {
        Write-Host "  SKIP  Schedulers not configured (run setup_scheduler.ps1 later)" -ForegroundColor DarkYellow
    }
}

Write-Host ""

# ---------------------------------------------------------------
# Step 6: Verify
# ---------------------------------------------------------------
Write-Host "[6/6] Verifying installation..." -ForegroundColor Yellow

& python (Join-Path $scriptDir "task_dashboard.py") check
if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "  OK  Installation complete!" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "  WARNING  'check' returned errors -- review output above" -ForegroundColor DarkYellow
}

# ---------------------------------------------------------------
# Summary
# ---------------------------------------------------------------
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Setup Complete" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor White
Write-Host "  1. Edit data/config.json to add your stakeholders"
Write-Host "  2. Add a task:  python task_dashboard.py add `"Review proposal`" --sender `"Jane`""
Write-Host "  3. Check it:    python task_dashboard.py list"
Write-Host ""
if ($claudeExe -and $workiqExe) {
    Write-Host "For full automated sync:" -ForegroundColor White
    Write-Host "  Interactive:  cd $scriptDir && claude"
    Write-Host "                Then say: 'Run a full task dashboard sync'"
    Write-Host "  Headless:     .\full_sync.ps1"
}
Write-Host ""
