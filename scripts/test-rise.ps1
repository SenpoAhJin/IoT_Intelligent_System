# Simple test script for rise functionality
Write-Host "Testing rise.ps1 syntax and basic functions..." -ForegroundColor Cyan

# Test 1: Check if script exists
Write-Host "`n[TEST 1] Script exists..." -NoNewline
$scriptPath = Join-Path $PSScriptRoot "rise.ps1"
if (Test-Path $scriptPath) {
    Write-Host " PASS" -ForegroundColor Green
} else {
    Write-Host " FAIL" -ForegroundColor Red
    exit 1
}

# Test 2: Check script syntax
Write-Host "[TEST 2] Script syntax..." -NoNewline
try {
    $scriptContent = Get-Content $scriptPath -Raw
    $null = [System.Management.Automation.PSParser]::Tokenize($scriptContent, [ref]$null)
    Write-Host " PASS" -ForegroundColor Green
} catch {
    Write-Host " FAIL" -ForegroundColor Red
    Write-Host "Error: $_" -ForegroundColor Red
    exit 1
}

# Test 3: Test port checking function
Write-Host "[TEST 3] Port availability check..." -NoNewline
function Test-PortAvailable {
    param([int]$Port)
    try {
        $listener = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Loopback, $Port)
        $listener.Start()
        $listener.Stop()
        return $true
    } catch {
        return $false
    }
}

$testResult = Test-PortAvailable -Port 65432  # Use high unused port
if ($testResult) {
    Write-Host " PASS" -ForegroundColor Green
} else {
    Write-Host " FAIL" -ForegroundColor Red
}

# Test 4: Check project structure
Write-Host "[TEST 4] Project structure..." -NoNewline
$projectRoot = Split-Path $PSScriptRoot
$checks = @(
    (Test-Path (Join-Path $projectRoot ".venv")),
    (Test-Path (Join-Path $projectRoot "backend\app\main.py")),
    (Test-Path (Join-Path $projectRoot "dashboard\index.html"))
)

if ($checks -notcontains $false) {
    Write-Host " PASS" -ForegroundColor Green
} else {
    Write-Host " FAIL" -ForegroundColor Red
}

# Test 5: Check Mosquitto
Write-Host "[TEST 5] Mosquitto executable..." -NoNewline
if (Test-Path "C:\Program Files\mosquitto\mosquitto.exe") {
    Write-Host " PASS" -ForegroundColor Green
} else {
    Write-Host " WARN (not found)" -ForegroundColor Yellow
}

Write-Host "`nAll basic tests completed!" -ForegroundColor Cyan
Write-Host "You can now run: .\scripts\rise.ps1" -ForegroundColor Green
