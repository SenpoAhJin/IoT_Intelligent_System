# WORKING_2 RESTORATION SCRIPT
# Safely restores the working_2-dashboard-control-baseline from GitHub
# 
# Usage: .\scripts\restore-working-2.ps1

param(
    [switch]$Force,
    [switch]$NoVerify
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "  AQUABUZZ WORKING_2 RESTORATION SCRIPT" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host ""

# Color functions
function Write-Success($message) {
    Write-Host "✓ $message" -ForegroundColor Green
}

function Write-Error-Custom($message) {
    Write-Host "✗ $message" -ForegroundColor Red
}

function Write-Warning-Custom($message) {
    Write-Host "⚠ $message" -ForegroundColor Yellow
}

function Write-Info($message) {
    Write-Host "ℹ $message" -ForegroundColor Cyan
}

# Step 1: Check Git is installed
Write-Info "Checking Git installation..."
try {
    $gitVersion = git --version
    Write-Success "Git is installed: $gitVersion"
} catch {
    Write-Error-Custom "Git is not installed or not in PATH"
    Write-Host ""
    Write-Host "Please install Git: https://git-scm.com/downloads"
    exit 1
}

Write-Host ""

# Step 2: Check we're in the correct repository
Write-Info "Verifying repository..."
try {
    $remoteUrl = git remote get-url origin
    if ($remoteUrl -notmatch "SenpoAhJin/IoT_Intelligent_System") {
        Write-Error-Custom "Wrong repository!"
        Write-Host "Current remote: $remoteUrl"
        Write-Host "Expected: https://github.com/SenpoAhJin/IoT_Intelligent_System.git"
        exit 1
    }
    Write-Success "Correct repository: $remoteUrl"
} catch {
    Write-Error-Custom "Not in a Git repository"
    Write-Host "Please run this script from the AquaBuzz project root"
    exit 1
}

Write-Host ""

# Step 3: Check for uncommitted changes
Write-Info "Checking for uncommitted changes..."
$gitStatus = git status --porcelain
if ($gitStatus -and -not $Force) {
    Write-Error-Custom "You have uncommitted changes!"
    Write-Host ""
    Write-Host "Uncommitted files:" -ForegroundColor Yellow
    git status --short
    Write-Host ""
    Write-Host "Options:" -ForegroundColor Cyan
    Write-Host "  1. Commit your changes: git add -A && git commit -m 'Your message'"
    Write-Host "  2. Stash your changes: git stash"
    Write-Host "  3. Force restore (WILL LOSE CHANGES): .\scripts\restore-working-2.ps1 -Force"
    Write-Host ""
    exit 1
} elseif ($gitStatus) {
    Write-Warning-Custom "Uncommitted changes detected, but -Force flag provided"
    Write-Warning-Custom "These changes will be LOST!"
} else {
    Write-Success "Working directory is clean"
}

Write-Host ""

# Step 4: Fetch from GitHub
Write-Info "Fetching latest from GitHub..."
try {
    git fetch origin --tags | Out-Null
    Write-Success "Fetched latest branches and tags"
} catch {
    Write-Error-Custom "Failed to fetch from GitHub"
    Write-Host "Error: $_"
    Write-Host ""
    Write-Host "Check your internet connection and GitHub access"
    exit 1
}

Write-Host ""

# Step 5: Verify working_2 branch exists
Write-Info "Verifying working_2 branch exists..."
$branches = git branch -r | Select-String "origin/working_2"
if (-not $branches) {
    Write-Error-Custom "working_2 branch not found on GitHub!"
    Write-Host ""
    Write-Host "Available branches:"
    git branch -r
    exit 1
}
Write-Success "working_2 branch found on GitHub"

Write-Host ""

# Step 6: Verify working_2-dashboard-control-baseline tag exists
Write-Info "Verifying tag exists..."
$tags = git tag | Select-String "^working_2-dashboard-control-baseline$"
if (-not $tags) {
    Write-Error-Custom "working_2-dashboard-control-baseline tag not found!"
    Write-Host ""
    Write-Host "Available tags:"
    git tag | Select-String "working"
    exit 1
}
Write-Success "Tag found: working_2-dashboard-control-baseline"

Write-Host ""

# Step 7: Get current branch
$currentBranch = git branch --show-current
Write-Info "Current branch: $currentBranch"

Write-Host ""

# Step 8: Confirm before checkout (if not already on working_2)
if ($currentBranch -ne "working_2" -and -not $Force) {
    Write-Host "=============================================" -ForegroundColor Yellow
    Write-Host "  CONFIRMATION REQUIRED" -ForegroundColor Yellow
    Write-Host "=============================================" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "You are about to:" -ForegroundColor Cyan
    Write-Host "  1. Switch from '$currentBranch' to 'working_2'"
    Write-Host "  2. Reset to tag: working_2-dashboard-control-baseline"
    Write-Host "  3. Restore commit: a474fc738e129853b98fae267bd2f8afc97b2294"
    Write-Host ""
    
    if ($gitStatus) {
        Write-Warning-Custom "UNCOMMITTED CHANGES WILL BE LOST!"
        Write-Host ""
    }
    
    $response = Read-Host "Continue? (yes/no)"
    if ($response -ne "yes") {
        Write-Info "Restoration cancelled"
        exit 0
    }
}

Write-Host ""

# Step 9: Checkout working_2 branch
Write-Info "Checking out working_2 branch..."
try {
    if ($Force) {
        git checkout -f working_2 | Out-Null
    } else {
        git checkout working_2 | Out-Null
    }
    Write-Success "Checked out working_2 branch"
} catch {
    Write-Error-Custom "Failed to checkout working_2"
    Write-Host "Error: $_"
    exit 1
}

Write-Host ""

# Step 10: Reset to baseline tag
Write-Info "Resetting to working_2-dashboard-control-baseline..."
try {
    git reset --hard working_2-dashboard-control-baseline | Out-Null
    Write-Success "Reset to baseline tag"
} catch {
    Write-Error-Custom "Failed to reset to tag"
    Write-Host "Error: $_"
    exit 1
}

Write-Host ""

# Step 11: Verify commit hash
Write-Info "Verifying commit hash..."
$currentCommit = git rev-parse HEAD
$expectedCommit = "a474fc738e129853b98fae267bd2f8afc97b2294"

if ($currentCommit -eq $expectedCommit) {
    Write-Success "Commit hash verified: $currentCommit"
} else {
    Write-Error-Custom "Commit hash mismatch!"
    Write-Host "Expected: $expectedCommit"
    Write-Host "Got:      $currentCommit"
    exit 1
}

Write-Host ""

# Step 12: Display restoration summary
Write-Host "=============================================" -ForegroundColor Green
Write-Host "  RESTORATION COMPLETE" -ForegroundColor Green
Write-Host "=============================================" -ForegroundColor Green
Write-Host ""
Write-Host "Branch:     working_2" -ForegroundColor Cyan
Write-Host "Tag:        working_2-dashboard-control-baseline" -ForegroundColor Cyan
Write-Host "Commit:     a474fc738e129853b98fae267bd2f8afc97b2294" -ForegroundColor Cyan
Write-Host ""

# Step 13: Show commit message
Write-Info "Commit details:"
Write-Host ""
git log -1 --format="%s%n%n%b" | Select-Object -First 10
Write-Host ""

# Step 14: Verify files exist (unless -NoVerify)
if (-not $NoVerify) {
    Write-Host ""
    Write-Info "Verifying key files..."
    
    $keyFiles = @(
        "firmware/aquabuzz_connected/aquabuzz_connected.ino",
        "backend/serial_gateway.py",
        "backend/app/main.py",
        "dashboard/index.html",
        "PHASE_2B2_IMPLEMENTATION_REPORT.md"
    )
    
    $allExist = $true
    foreach ($file in $keyFiles) {
        if (Test-Path $file) {
            Write-Success $file
        } else {
            Write-Error-Custom "Missing: $file"
            $allExist = $false
        }
    }
    
    if (-not $allExist) {
        Write-Host ""
        Write-Warning-Custom "Some files are missing! Restoration may be incomplete."
    }
    
    Write-Host ""
}

# Step 15: Next steps
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host "  NEXT STEPS" -ForegroundColor Cyan
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. Configure environment files:" -ForegroundColor Yellow
Write-Host "   - Create backend/.env with MQTT credentials"
Write-Host "   - Create firmware/aquabuzz_connected/secrets.h"
Write-Host ""
Write-Host "2. Install dependencies:" -ForegroundColor Yellow
Write-Host "   cd backend"
Write-Host "   .\.venv\Scripts\Activate.ps1"
Write-Host "   pip install -r requirements.txt"
Write-Host ""
Write-Host "3. Upload firmware to ESP32 using Arduino IDE" -ForegroundColor Yellow
Write-Host ""
Write-Host "4. Run tests:" -ForegroundColor Yellow
Write-Host "   python -m pytest backend/tests -v"
Write-Host ""
Write-Host "5. Start system:" -ForegroundColor Yellow
Write-Host "   .\scripts\rise.ps1"
Write-Host ""
Write-Host "6. Test dashboard:" -ForegroundColor Yellow
Write-Host "   Open http://localhost:8000"
Write-Host "   Click START GAME, test controls, click FINISH GAME"
Write-Host ""
Write-Host "=============================================" -ForegroundColor Green
Write-Host "For detailed documentation, see:" -ForegroundColor Cyan
Write-Host "  - WORKING_2_PRESERVATION_REPORT.md"
Write-Host "  - WORKING_2_QUICK_REFERENCE.md"
Write-Host "  - PHASE_2B2_IMPLEMENTATION_REPORT.md"
Write-Host "=============================================" -ForegroundColor Green
Write-Host ""
Write-Success "WORKING_2 RESTORATION COMPLETE"
Write-Host ""
