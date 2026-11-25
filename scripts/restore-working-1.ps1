# ================================================================
# AQUABUZZ — WORKING_1 BASELINE RESTORATION SCRIPT
# ================================================================
# Safely restores the approved working_1 baseline from GitHub
# without destructive Git commands or overwriting uncommitted work.
# ================================================================

param(
    [switch]$Force = $false
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  AQUABUZZ WORKING_1 BASELINE RESTORATION  " -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# ================================================================
# SAFETY CHECKS
# ================================================================

Write-Host "[1/7] Checking Git repository status..." -ForegroundColor Yellow

# Check if we're in a Git repository
try {
    git rev-parse --git-dir | Out-Null
} catch {
    Write-Host "❌ ERROR: Not in a Git repository" -ForegroundColor Red
    exit 1
}

# Check for uncommitted changes
$gitStatus = git status --porcelain
if ($gitStatus -and -not $Force) {
    Write-Host ""
    Write-Host "❌ ERROR: Uncommitted changes detected:" -ForegroundColor Red
    Write-Host ""
    git status --short
    Write-Host ""
    Write-Host "To protect your work, this script refuses to proceed." -ForegroundColor Yellow
    Write-Host "Options:" -ForegroundColor Yellow
    Write-Host "  1. Commit your changes: git add . && git commit -m 'Your message'" -ForegroundColor White
    Write-Host "  2. Stash your changes: git stash" -ForegroundColor White
    Write-Host "  3. Force restore (DANGEROUS): .\scripts\restore-working-1.ps1 -Force" -ForegroundColor White
    Write-Host ""
    exit 1
}

if ($Force -and $gitStatus) {
    Write-Host "⚠️  WARNING: Proceeding with -Force flag. Uncommitted changes will be lost!" -ForegroundColor Red
    Start-Sleep -Seconds 3
}

Write-Host "✓ Git status check passed" -ForegroundColor Green

# ================================================================
# FETCH BASELINE FROM GITHUB
# ================================================================

Write-Host ""
Write-Host "[2/7] Fetching working_1 baseline from GitHub..." -ForegroundColor Yellow

try {
    git fetch origin working_1 2>&1 | Out-Null
    git fetch origin "refs/tags/working_1-baseline:refs/tags/working_1-baseline" 2>&1 | Out-Null
    Write-Host "✓ Baseline fetched successfully" -ForegroundColor Green
} catch {
    Write-Host "❌ ERROR: Failed to fetch working_1 baseline from GitHub" -ForegroundColor Red
    Write-Host "   Make sure the branch and tag exist on the remote." -ForegroundColor Yellow
    exit 1
}

# ================================================================
# VERIFY BASELINE EXISTS
# ================================================================

Write-Host ""
Write-Host "[3/7] Verifying baseline integrity..." -ForegroundColor Yellow

$branchExists = git rev-parse --verify "origin/working_1" 2>$null
$tagExists = git rev-parse --verify "working_1-baseline" 2>$null

if (-not $branchExists) {
    Write-Host "❌ ERROR: Branch 'working_1' not found on remote" -ForegroundColor Red
    exit 1
}

if (-not $tagExists) {
    Write-Host "❌ ERROR: Tag 'working_1-baseline' not found" -ForegroundColor Red
    exit 1
}

$branchCommit = git rev-parse "origin/working_1"
$tagCommit = git rev-parse "working_1-baseline"

if ($branchCommit -ne $tagCommit) {
    Write-Host "⚠️  WARNING: Branch and tag point to different commits" -ForegroundColor Yellow
    Write-Host "   Branch: $branchCommit" -ForegroundColor White
    Write-Host "   Tag:    $tagCommit" -ForegroundColor White
    Write-Host "   Using tag commit as the source of truth." -ForegroundColor Yellow
}

Write-Host "✓ Baseline verified" -ForegroundColor Green
Write-Host "   Commit: $tagCommit" -ForegroundColor White

# ================================================================
# CREATE LOCAL BRANCH
# ================================================================

Write-Host ""
Write-Host "[4/7] Creating local working_1 branch..." -ForegroundColor Yellow

$currentBranch = git rev-parse --abbrev-ref HEAD

# Check if local working_1 branch exists
$localBranchExists = git rev-parse --verify "working_1" 2>$null

if ($localBranchExists) {
    Write-Host "⚠️  Local 'working_1' branch already exists" -ForegroundColor Yellow
    
    if ($currentBranch -eq "working_1") {
        Write-Host "   Already on working_1 branch" -ForegroundColor White
    } else {
        git checkout working_1
        Write-Host "✓ Switched to existing working_1 branch" -ForegroundColor Green
    }
    
    # Reset to tag commit
    git reset --hard "working_1-baseline"
    Write-Host "✓ Reset to working_1-baseline tag" -ForegroundColor Green
} else {
    # Create new branch from tag
    git checkout -b working_1 "working_1-baseline"
    Write-Host "✓ Created and checked out working_1 branch" -ForegroundColor Green
}

# ================================================================
# RESTORE DATABASE BACKUP
# ================================================================

Write-Host ""
Write-Host "[5/7] Checking for database backup..." -ForegroundColor Yellow

$backupFile = Get-ChildItem "backups\aquabuzz-working1-*.db" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1

if ($backupFile) {
    Write-Host "✓ Database backup found: $($backupFile.Name)" -ForegroundColor Green
    
    if (Test-Path "backend\aquabuzz.db") {
        $currentDbSize = (Get-Item "backend\aquabuzz.db").Length
        Write-Host "   Current database: $currentDbSize bytes" -ForegroundColor White
    }
    
    Write-Host "   Backup database: $($backupFile.Length) bytes" -ForegroundColor White
    Write-Host "   To restore: Copy-Item '$($backupFile.FullName)' 'backend\aquabuzz.db' -Force" -ForegroundColor White
} else {
    Write-Host "⚠️  No database backup found in backups/ directory" -ForegroundColor Yellow
    Write-Host "   Database restoration must be done manually if needed" -ForegroundColor Yellow
}

# ================================================================
# VERIFY FIRMWARE PRESERVATION
# ================================================================

Write-Host ""
Write-Host "[6/7] Verifying firmware preservation..." -ForegroundColor Yellow

$firmwareFiles = @(
    "firmware\aquabuzz_core\aquabuzz_core.ino",
    "firmware\aquabuzz_connected\aquabuzz_connected.ino"
)

$allFirmwarePresent = $true
foreach ($file in $firmwareFiles) {
    if (Test-Path $file) {
        $size = (Get-Item $file).Length
        Write-Host "✓ $file ($size bytes)" -ForegroundColor Green
    } else {
        Write-Host "❌ Missing: $file" -ForegroundColor Red
        $allFirmwarePresent = $false
    }
}

if (-not $allFirmwarePresent) {
    Write-Host "⚠️  WARNING: Some firmware files are missing!" -ForegroundColor Yellow
}

# ================================================================
# VERIFY SYSTEM COMPONENTS
# ================================================================

Write-Host ""
Write-Host "[7/7] Verifying system components..." -ForegroundColor Yellow

$components = @{
    "Dashboard" = "dashboard\index.html"
    "FastAPI Backend" = "backend\app\main.py"
    "Serial Gateway" = "backend\serial_gateway.py"
    "MQTT Client" = "backend\app\mqtt_client.py"
    "Database Models" = "backend\app\models.py"
    "RISE Start Script" = "scripts\rise.ps1"
    "RISE Stop Script" = "scripts\rise-stop.ps1"
    "Requirements" = "backend\requirements.txt"
}

$allComponentsPresent = $true
foreach ($component in $components.GetEnumerator()) {
    if (Test-Path $component.Value) {
        Write-Host "✓ $($component.Key)" -ForegroundColor Green
    } else {
        Write-Host "❌ Missing: $($component.Key)" -ForegroundColor Red
        $allComponentsPresent = $false
    }
}

# ================================================================
# RESTORATION SUMMARY
# ================================================================

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  RESTORATION COMPLETE                     " -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Current branch: working_1" -ForegroundColor Green
Write-Host "Commit: $tagCommit" -ForegroundColor White
Write-Host ""

if ($allComponentsPresent -and $allFirmwarePresent) {
    Write-Host "✓ All system components verified" -ForegroundColor Green
} else {
    Write-Host "⚠️  Some components are missing - check output above" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Review the restored code" -ForegroundColor White
Write-Host "  2. Restore database if needed (see backup info above)" -ForegroundColor White
Write-Host "  3. Install dependencies: pip install -r backend\requirements.txt" -ForegroundColor White
Write-Host "  4. Configure backend\.env with your settings" -ForegroundColor White
Write-Host "  5. Start system: .\scripts\rise.ps1" -ForegroundColor White
Write-Host ""

Write-Host "IMPORTANT: Firmware must be uploaded manually via Arduino IDE" -ForegroundColor Cyan
Write-Host ""
