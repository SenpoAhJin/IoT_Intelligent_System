# AquaBuzz Startup Verification Script
# Tests that rise.ps1 successfully starts all services
# Run this AFTER running rise.ps1

$ErrorActionPreference = 'Continue'

Write-Host ''
Write-Host '==================================================' -ForegroundColor Cyan
Write-Host '    AquaBuzz Startup Verification' -ForegroundColor Cyan
Write-Host '==================================================' -ForegroundColor Cyan
Write-Host ''

$allPassed = $true

# Test 1: Backend API Health
Write-Host '[Test 1] Checking Backend API health...' -ForegroundColor Cyan
try {
    $response = Invoke-WebRequest -Uri 'http://localhost:8000/api/health' -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
    $health = $response.Content | ConvertFrom-Json
    
    if ($health.status -eq 'healthy') {
        Write-Host '  [PASS] Backend is healthy' -ForegroundColor Green
        Write-Host "    - Status: $($health.status)" -ForegroundColor Gray
        Write-Host "    - Database: $($health.database)" -ForegroundColor Gray
        Write-Host "    - MQTT: $($health.mqtt_connected)" -ForegroundColor Gray
        
        if ($health.mqtt_connected) {
            Write-Host '  [PASS] MQTT is connected' -ForegroundColor Green
        } else {
            Write-Host '  [WARN] MQTT not connected yet (may still be connecting)' -ForegroundColor Yellow
        }
    } else {
        Write-Host '  [FAIL] Backend not healthy' -ForegroundColor Red
        $allPassed = $false
    }
} catch {
    Write-Host '  [FAIL] Cannot reach Backend API' -ForegroundColor Red
    Write-Host "    Error: $($_.Exception.Message)" -ForegroundColor Red
    $allPassed = $false
}
Write-Host ''

# Test 2: Backend API Endpoints
Write-Host '[Test 2] Checking Backend API endpoints...' -ForegroundColor Cyan
try {
    $response = Invoke-WebRequest -Uri 'http://localhost:8000/api/runs' -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
    if ($response.StatusCode -eq 200) {
        Write-Host '  [PASS] Runs endpoint responding' -ForegroundColor Green
        $runs = $response.Content | ConvertFrom-Json
        Write-Host "    - Total runs in database: $($runs.Count)" -ForegroundColor Gray
    }
} catch {
    Write-Host '  [FAIL] Runs endpoint not responding' -ForegroundColor Red
    $allPassed = $false
}
Write-Host ''

# Test 3: Dashboard HTTP Server
Write-Host '[Test 3] Checking Dashboard server...' -ForegroundColor Cyan
$dashboardFound = $false
$dashboardPort = $null

foreach ($port in @(3000, 3001, 3002, 8080, 8081)) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:$port" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200 -and $response.Content -like '*AquaBuzz*') {
            Write-Host "  [PASS] Dashboard running on port $port" -ForegroundColor Green
            $dashboardFound = $true
            $dashboardPort = $port
            break
        }
    } catch {
        # Port not responding, try next
    }
}

if (-not $dashboardFound) {
    Write-Host '  [FAIL] Dashboard not found on any expected port' -ForegroundColor Red
    $allPassed = $false
}
Write-Host ''

# Test 4: Process Tracker File
Write-Host '[Test 4] Checking process tracking...' -ForegroundColor Cyan
$trackerPath = 'C:\Users\Alord\OneDrive\Documents\School\COSC 105 - Ma''am Mikae\Intelligent_System_IS\.aquabuzz-processes.json'
if (Test-Path $trackerPath) {
    try {
        $content = Get-Content $trackerPath -Raw
        $processes = $content | ConvertFrom-Json
        
        Write-Host '  [PASS] Process tracker exists' -ForegroundColor Green
        
        $serviceNames = @('backend', 'gateway', 'dashboard')
        foreach ($service in $serviceNames) {
            if ($processes.$service) {
                $pid = $processes.$service.pid
                $port = $processes.$service.port
                $url = $processes.$service.url
                
                # Check if process still exists
                $process = Get-Process -Id $pid -ErrorAction SilentlyContinue
                if ($process) {
                    Write-Host "    - $service (PID: $pid, Port: $port): RUNNING" -ForegroundColor Green
                } else {
                    Write-Host "    - $service (PID: $pid): NOT RUNNING" -ForegroundColor Red
                    $allPassed = $false
                }
            } else {
                Write-Host "    - $service: NOT TRACKED" -ForegroundColor Yellow
            }
        }
    } catch {
        Write-Host '  [WARN] Process tracker exists but cannot parse' -ForegroundColor Yellow
    }
} else {
    Write-Host '  [FAIL] Process tracker file not found' -ForegroundColor Red
    $allPassed = $false
}
Write-Host ''

# Test 5: Critical Fix Verification
Write-Host '[Test 5] Verifying critical hit aggregation fix...' -ForegroundColor Cyan
try {
    $mainPyPath = 'C:\Users\Alord\OneDrive\Documents\School\COSC 105 - Ma''am Mikae\Intelligent_System_IS\backend\app\main.py'
    if (Test-Path $mainPyPath) {
        $content = Get-Content $mainPyPath -Raw
        
        # Check for the critical fix comment
        if ($content -match 'CRITICAL FIX: Calculate aggregate stats from actual Hit records') {
            Write-Host '  [PASS] Critical fix code is present' -ForegroundColor Green
            
            # Check for key implementation details
            if ($content -match 'hit_records = db\.query\(Hit\)\.filter\(Hit\.run_uid == run_uid\)\.all\(\)') {
                Write-Host '    - Hit records query: PRESENT' -ForegroundColor Gray
            }
            
            if ($content -match 'completed_hits = \[h for h in hit_records if h\.duration_ms > 0\]') {
                Write-Host '    - Completed hits filter: PRESENT' -ForegroundColor Gray
            }
            
            if ($content -match 'run\.hits = len\(completed_hits\)') {
                Write-Host '    - Hit count calculation: PRESENT' -ForegroundColor Gray
            }
            
            if ($content -match 'run\.total_contact_ms = sum\(h\.duration_ms for h in completed_hits\)') {
                Write-Host '    - Total contact calculation: PRESENT' -ForegroundColor Gray
            }
            
            Write-Host '  [PASS] All fix components verified' -ForegroundColor Green
        } else {
            Write-Host '  [FAIL] Critical fix code NOT FOUND' -ForegroundColor Red
            Write-Host '    Backend may be running old code!' -ForegroundColor Red
            $allPassed = $false
        }
    } else {
        Write-Host '  [FAIL] Cannot find backend main.py' -ForegroundColor Red
        $allPassed = $false
    }
} catch {
    Write-Host '  [FAIL] Error checking fix code' -ForegroundColor Red
    Write-Host "    Error: $($_.Exception.Message)" -ForegroundColor Red
    $allPassed = $false
}
Write-Host ''

# Test 6: Database Connection
Write-Host '[Test 6] Checking database connectivity...' -ForegroundColor Cyan
try {
    $dbPath = 'C:\Users\Alord\OneDrive\Documents\School\COSC 105 - Ma''am Mikae\Intelligent_System_IS\backend\aquabuzz.db'
    if (Test-Path $dbPath) {
        Write-Host '  [PASS] Database file exists' -ForegroundColor Green
        $dbSize = (Get-Item $dbPath).Length / 1KB
        Write-Host "    - Size: $([math]::Round($dbSize, 2)) KB" -ForegroundColor Gray
    } else {
        Write-Host '  [FAIL] Database file not found' -ForegroundColor Red
        $allPassed = $false
    }
} catch {
    Write-Host '  [FAIL] Error checking database' -ForegroundColor Red
    $allPassed = $false
}
Write-Host ''

# Summary
Write-Host '==================================================' -ForegroundColor Cyan
if ($allPassed) {
    Write-Host '    All Checks Passed!' -ForegroundColor Green
    Write-Host '==================================================' -ForegroundColor Green
    Write-Host ''
    Write-Host 'System Status: READY FOR TESTING' -ForegroundColor Green
    Write-Host ''
    Write-Host 'Next Steps:' -ForegroundColor Cyan
    Write-Host '  1. Connect ESP32 via USB' -ForegroundColor White
    Write-Host '  2. Watch Serial Gateway window for connection' -ForegroundColor White
    Write-Host '  3. Play the maze game' -ForegroundColor White
    Write-Host '  4. Verify results on dashboard' -ForegroundColor White
    Write-Host ''
    if ($dashboardPort) {
        Write-Host "Dashboard URL: http://localhost:$dashboardPort" -ForegroundColor Cyan
    }
    Write-Host "API Docs: http://localhost:8000/docs" -ForegroundColor Cyan
    Write-Host ''
} else {
    Write-Host '    Some Checks Failed' -ForegroundColor Red
    Write-Host '==================================================' -ForegroundColor Red
    Write-Host ''
    Write-Host 'System Status: NOT READY' -ForegroundColor Red
    Write-Host ''
    Write-Host 'Troubleshooting:' -ForegroundColor Yellow
    Write-Host '  - Try running: .\scripts\rise-stop.ps1' -ForegroundColor White
    Write-Host '  - Then run: .\scripts\rise.ps1 again' -ForegroundColor White
    Write-Host '  - Check for port conflicts (8000, 3000)' -ForegroundColor White
    Write-Host ''
}

