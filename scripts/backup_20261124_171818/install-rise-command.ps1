# ========================================
#   WIREBUZZ COMMAND REGISTRATION
# ========================================
# Registers 'rise' and 'rise-stop' commands
# in PowerShell profile
# ========================================

$ErrorActionPreference = "Stop"

$PROJECT_ROOT = "c:\Users\Alord\OneDrive\Documents\School\COSC 105 - Ma'am Mikae\Intelligent_System_IS"
$RISE_SCRIPT = Join-Path $PROJECT_ROOT "scripts\rise.ps1"
$STOP_SCRIPT = Join-Path $PROJECT_ROOT "scripts\rise-stop.ps1"

function Write-Status {
    param([string]$Message, [string]$Status = "INFO")
    
    switch ($Status) {
        "OK"      { Write-Host "[OK]      " -ForegroundColor Green -NoNewline; Write-Host $Message }
        "FAILED"  { Write-Host "[FAILED]  " -ForegroundColor Red -NoNewline; Write-Host $Message }
        "WARNING" { Write-Host "[WARNING] " -ForegroundColor Yellow -NoNewline; Write-Host $Message }
        "INFO"    { Write-Host "[INFO]    " -ForegroundColor Cyan -NoNewline; Write-Host $Message }
        "STEP"    { Write-Host "[STEP]    " -ForegroundColor Magenta -NoNewline; Write-Host $Message }
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  WIREBUZZ COMMAND REGISTRATION" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Verify scripts exist
Write-Status "Checking for rise.ps1..." "STEP"
if (-not (Test-Path $RISE_SCRIPT)) {
    Write-Status "rise.ps1 not found at: $RISE_SCRIPT" "FAILED"
    exit 1
}
Write-Status "rise.ps1 found" "OK"

Write-Status "Checking for rise-stop.ps1..." "STEP"
if (-not (Test-Path $STOP_SCRIPT)) {
    Write-Status "rise-stop.ps1 not found at: $STOP_SCRIPT" "FAILED"
    exit 1
}
Write-Status "rise-stop.ps1 found" "OK"

# Check PowerShell profile
$profilePath = $PROFILE
Write-Status "PowerShell profile: $profilePath" "INFO"

$profileExists = Test-Path $profilePath
if (-not $profileExists) {
    Write-Status "PowerShell profile does not exist, will create it" "INFO"
} else {
    Write-Status "PowerShell profile exists, will check for conflicts" "INFO"
}

# Read existing profile content
$profileContent = ""
if ($profileExists) {
    $profileContent = Get-Content $profilePath -Raw
}

# Check for existing 'rise' function
if ($profileContent -match "function\s+rise\s*{") {
    Write-Host ""
    Write-Status "CONFLICT DETECTED: 'rise' function already exists in profile!" "WARNING"
    Write-Host ""
    Write-Host "Current profile content:" -ForegroundColor Yellow
    Write-Host "----------------------------------------"
    Write-Host $profileContent
    Write-Host "----------------------------------------"
    Write-Host ""
    Write-Host "The 'rise' command is already defined. Options:" -ForegroundColor Yellow
    Write-Host "  1. Choose a different command name for WireBuzz" -ForegroundColor Cyan
    Write-Host "  2. Manually remove the existing 'rise' function" -ForegroundColor Cyan
    Write-Host "  3. Edit the scripts to use a different name (e.g., 'wirebuzz')" -ForegroundColor Cyan
    Write-Host ""
    Write-Status "Installation aborted to prevent conflicts" "FAILED"
    exit 1
}

# Check for existing 'rise-stop' function
if ($profileContent -match "function\s+rise-stop\s*{") {
    Write-Status "CONFLICT: 'rise-stop' function already exists in profile" "WARNING"
    Write-Status "Installation aborted to prevent conflicts" "FAILED"
    exit 1
}

# Check if WireBuzz functions already registered
if ($profileContent -match "# WireBuzz Commands") {
    Write-Status "'rise' commands appear to already be registered" "WARNING"
    Write-Host ""
    Write-Host "Do you want to re-register (update) the commands? [Y/N]: " -NoNewline
    $response = Read-Host
    
    if ($response -ne "Y" -and $response -ne "y") {
        Write-Status "Installation cancelled by user" "INFO"
        exit 0
    }
    
    # Remove existing WireBuzz section
    Write-Status "Removing old WireBuzz commands..." "STEP"
    $lines = $profileContent -split "`r?`n"
    $newLines = @()
    $skipMode = $false
    
    foreach ($line in $lines) {
        if ($line -match "# WireBuzz Commands") {
            $skipMode = $true
            continue
        }
        if ($skipMode -and $line -match "^function\s+(rise|rise-stop)") {
            # Skip WireBuzz function definitions
            continue
        }
        if ($skipMode -and $line.Trim() -eq "") {
            # End of WireBuzz section
            $skipMode = $false
            continue
        }
        if (-not $skipMode) {
            $newLines += $line
        }
    }
    
    $profileContent = $newLines -join "`r`n"
}

# Prepare new functions to add
$newFunctions = @"

# WireBuzz Commands
function rise { & 'c:\Users\Alord\OneDrive\Documents\School\COSC 105 - Ma'am Mikae\Intelligent_System_IS\scripts\rise.ps1' }
function rise-stop { & 'c:\Users\Alord\OneDrive\Documents\School\COSC 105 - Ma'am Mikae\Intelligent_System_IS\scripts\rise-stop.ps1' }
"@

# Add to profile
Write-Status "Adding WireBuzz commands to PowerShell profile..." "STEP"

$updatedContent = $profileContent.TrimEnd() + $newFunctions + "`r`n"

# Create profile directory if it doesn't exist
$profileDir = Split-Path $profilePath
if (-not (Test-Path $profileDir)) {
    Write-Status "Creating profile directory..." "STEP"
    New-Item -ItemType Directory -Path $profileDir -Force | Out-Null
}

# Write updated profile
Set-Content -Path $profilePath -Value $updatedContent -Encoding UTF8

Write-Status "Commands registered successfully!" "OK"

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  INSTALLATION COMPLETE" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "New commands available:" -ForegroundColor Cyan
Write-Host "  rise       " -ForegroundColor Yellow -NoNewline; Write-Host "- Start all WireBuzz services"
Write-Host "  rise-stop  " -ForegroundColor Yellow -NoNewline; Write-Host "- Stop all WireBuzz services"
Write-Host ""
Write-Host "To use the commands:" -ForegroundColor Cyan
Write-Host "  1. Close this PowerShell window" -ForegroundColor White
Write-Host "  2. Open a NEW PowerShell window" -ForegroundColor White
Write-Host "  3. Navigate to your project directory" -ForegroundColor White
Write-Host "  4. Type: " -NoNewline -ForegroundColor White
Write-Host "rise" -ForegroundColor Yellow
Write-Host ""
Write-Host "Or reload your profile now with:" -ForegroundColor Cyan
Write-Host "  . `$PROFILE" -ForegroundColor Yellow
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
