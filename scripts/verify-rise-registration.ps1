# ========================================
#   VERIFY RISE COMMAND REGISTRATION
# ========================================
# This script verifies that rise commands
# are properly registered in PowerShell
# ========================================

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  RISE COMMAND VERIFICATION" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Reload profile to ensure latest version
. $PROFILE

# Test 1: Check if commands exist
Write-Host "TEST 1: Command Registration" -ForegroundColor Yellow
Write-Host "----------------------------------------"

$commands = @("arise", "rest", "rise", "rise-stop")
$results = @{}

foreach ($cmd in $commands) {
    $command = Get-Command $cmd -ErrorAction SilentlyContinue
    if ($command) {
        $results[$cmd] = @{
            Exists = $true
            Type = $command.CommandType
            Path = $command.Definition
        }
        
        $project = "Unknown"
        if ($command.Definition -like "*ForgeMind*") {
            $project = "ForgeMind"
        } elseif ($command.Definition -like "*Intelligent_System*" -or $command.Definition -like "*WireBuzz*") {
            $project = "WireBuzz"
        }
        
        Write-Host "  ✓ " -NoNewline -ForegroundColor Green
        Write-Host "$cmd " -NoNewline -ForegroundColor White
        Write-Host "($project)" -ForegroundColor Cyan
    } else {
        $results[$cmd] = @{ Exists = $false }
        Write-Host "  ✗ " -NoNewline -ForegroundColor Red
        Write-Host "$cmd " -NoNewline -ForegroundColor White
        Write-Host "(NOT FOUND)" -ForegroundColor Red
    }
}

Write-Host ""

# Test 2: Verify script paths exist
Write-Host ""
Write-Host "TEST 2: Script Path Validation" -ForegroundColor Yellow
Write-Host "----------------------------------------"

$wirebuzzScripts = @{
    "rise" = "c:\Users\Alord\OneDrive\Documents\School\COSC 105 - Ma'am Mikae\Intelligent_System_IS\scripts\rise.ps1"
    "rise-stop" = "c:\Users\Alord\OneDrive\Documents\School\COSC 105 - Ma'am Mikae\Intelligent_System_IS\scripts\rise-stop.ps1"
}

foreach ($name in $wirebuzzScripts.Keys) {
    $path = $wirebuzzScripts[$name]
    if (Test-Path $path) {
        Write-Host "  ✓ " -NoNewline -ForegroundColor Green
        Write-Host "$name script exists" -ForegroundColor White
    } else {
        Write-Host "  ✗ " -NoNewline -ForegroundColor Red
        Write-Host "$name script NOT FOUND at:" -ForegroundColor Red
        Write-Host "    $path" -ForegroundColor Gray
    }
}

Write-Host ""

# Test 3: Command isolation
Write-Host ""
Write-Host "TEST 3: Command Isolation Check" -ForegroundColor Yellow
Write-Host "----------------------------------------"

$ariseCmd = Get-Command arise -ErrorAction SilentlyContinue
$riseCmd = Get-Command rise -ErrorAction SilentlyContinue

if ($ariseCmd -and $riseCmd) {
    $arisePath = $ariseCmd.Definition
    $risePath = $riseCmd.Definition
    
    if ($arisePath -like "*ForgeMind*" -and $risePath -like "*Intelligent_System*") {
        Write-Host "  ✓ " -NoNewline -ForegroundColor Green
        Write-Host "Commands are properly isolated" -ForegroundColor White
        Write-Host "    arise -> ForgeMind" -ForegroundColor Gray
        Write-Host "    rise  -> WireBuzz" -ForegroundColor Gray
    } else {
        Write-Host "  ✗ " -NoNewline -ForegroundColor Red
        Write-Host "Commands may be conflicting!" -ForegroundColor Red
    }
} else {
    Write-Host "  ⚠ " -NoNewline -ForegroundColor Yellow
    Write-Host "Cannot verify isolation (commands missing)" -ForegroundColor Yellow
}

Write-Host ""

# Summary
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  SUMMARY" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$allGood = $results["rise"].Exists -and 
           $results["rise-stop"].Exists -and 
           $results["arise"].Exists -and 
           $results["rest"].Exists -and
           (Test-Path $wirebuzzScripts["rise"]) -and
           (Test-Path $wirebuzzScripts["rise-stop"])

if ($allGood) {
    Write-Host "✓ ALL CHECKS PASSED" -ForegroundColor Green
    Write-Host ""
    Write-Host "You can now use:" -ForegroundColor White
    Write-Host "  rise       " -NoNewline -ForegroundColor Yellow
    Write-Host "- Start WireBuzz services" -ForegroundColor Gray
    Write-Host "  rise-stop  " -NoNewline -ForegroundColor Yellow
    Write-Host "- Stop WireBuzz services" -ForegroundColor Gray
    Write-Host ""
    Write-Host "Your existing commands still work:" -ForegroundColor White
    Write-Host "  arise      " -NoNewline -ForegroundColor Yellow
    Write-Host "- Start ForgeMind services" -ForegroundColor Gray
    Write-Host "  rest       " -NoNewline -ForegroundColor Yellow
    Write-Host "- Stop ForgeMind services" -ForegroundColor Gray
} else {
    Write-Host "✗ SOME CHECKS FAILED" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please run the installer:" -ForegroundColor Yellow
    Write-Host "  .\scripts\install-rise-command.ps1" -ForegroundColor Cyan
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
