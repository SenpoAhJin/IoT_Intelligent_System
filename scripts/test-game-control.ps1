# PHASE 2B-2: Game Control Testing Script
# Tests dashboard game control functionality without physical hardware

Write-Host "======================================" -ForegroundColor Cyan
Write-Host "  AQUABUZZ GAME CONTROL TEST SUITE" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

$API_BASE = "http://localhost:8000/api"
$TEST_DEVICE = "aquabuzz-001"

# Test counters
$tests_passed = 0
$tests_failed = 0
$tests_skipped = 0

function Test-ApiEndpoint {
    param(
        [string]$TestName,
        [string]$Method,
        [string]$Url,
        [hashtable]$Body = $null,
        [int]$ExpectedStatus = 200
    )
    
    Write-Host "TEST: $TestName" -ForegroundColor Yellow
    
    try {
        $params = @{
            Uri = $Url
            Method = $Method
            ContentType = "application/json"
            TimeoutSec = 5
        }
        
        if ($Body) {
            $params.Body = ($Body | ConvertTo-Json)
        }
        
        $response = Invoke-WebRequest @params -UseBasicParsing
        
        if ($response.StatusCode -eq $ExpectedStatus) {
            Write-Host "  PASS: Got expected status $ExpectedStatus" -ForegroundColor Green
            $script:tests_passed++
            return $true
        } else {
            Write-Host "  FAIL: Got status $($response.StatusCode), expected $ExpectedStatus" -ForegroundColor Red
            $script:tests_failed++
            return $false
        }
    } catch {
        if ($_.Exception.Response) {
            $status = $_.Exception.Response.StatusCode.value__
            if ($status -eq $ExpectedStatus) {
                Write-Host "  PASS: Got expected status $ExpectedStatus (error)" -ForegroundColor Green
                $script:tests_passed++
                return $true
            }
        }
        
        Write-Host "  FAIL: $_" -ForegroundColor Red
        $script:tests_failed++
        return $false
    }
}

# Check if backend is running
Write-Host "Checking backend availability..." -ForegroundColor Cyan
try {
    $health = Invoke-RestMethod -Uri "$API_BASE/health" -Method GET -TimeoutSec 2
    Write-Host "Backend is online" -ForegroundColor Green
    Write-Host "  MQTT Connected: $($health.mqtt_connected)" -ForegroundColor Gray
    Write-Host "  Active Runs: $($health.active_runs)" -ForegroundColor Gray
} catch {
    Write-Host "ERROR: Backend not running at $API_BASE" -ForegroundColor Red
    Write-Host "Start backend with: uvicorn app.main:app --reload" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "===========================================" -ForegroundColor Cyan
Write-Host "  API ENDPOINT TESTS (Without Hardware)" -ForegroundColor Cyan
Write-Host "===========================================" -ForegroundColor Cyan
Write-Host ""

# Test 1: Health check
Test-ApiEndpoint -TestName "GET /api/health" `
    -Method GET `
    -Url "$API_BASE/health" `
    -ExpectedStatus 200

# Test 2: Game status check
Test-ApiEndpoint -TestName "GET /api/game/status" `
    -Method GET `
    -Url "$API_BASE/game/status?device_id=$TEST_DEVICE" `
    -ExpectedStatus 200

# Test 3: Start game (may fail if game already running)
Write-Host ""
Write-Host "TEST: POST /api/game/start" -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "$API_BASE/game/start" `
        -Method POST `
        -ContentType "application/json" `
        -Body (@{
            device_id = $TEST_DEVICE
            player_id = "test-user"
        } | ConvertTo-Json)
    
    Write-Host "  PASS: Command sent successfully" -ForegroundColor Green
    Write-Host "    Request ID: $($response.request_id)" -ForegroundColor Gray
    Write-Host "    Status: $($response.status)" -ForegroundColor Gray
    $script:tests_passed++
    
    $start_request_id = $response.request_id
} catch {
    $errorResponse = $_.ErrorDetails.Message | ConvertFrom-Json
    if ($errorResponse.detail -match "already in progress") {
        Write-Host "  INFO: Game already running (expected if previous test left game active)" -ForegroundColor Yellow
        $script:tests_skipped++
    } else {
        Write-Host "  FAIL: $_" -ForegroundColor Red
        Write-Host "  Detail: $($errorResponse.detail)" -ForegroundColor Red
        $script:tests_failed++
    }
}

# Test 4: Duplicate start (should fail)
Write-Host ""
Write-Host "TEST: POST /api/game/start (duplicate - should fail)" -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "$API_BASE/game/start" `
        -Method POST `
        -ContentType "application/json" `
        -Body (@{
            device_id = $TEST_DEVICE
            player_id = "test-user"
        } | ConvertTo-Json)
    
    Write-Host "  FAIL: Should have rejected duplicate start" -ForegroundColor Red
    $script:tests_failed++
} catch {
    $errorResponse = $_.ErrorDetails.Message | ConvertFrom-Json
    if ($errorResponse.detail -match "already in progress|already pending") {
        Write-Host "  PASS: Duplicate start correctly rejected" -ForegroundColor Green
        Write-Host "    Reason: $($errorResponse.detail)" -ForegroundColor Gray
        $script:tests_passed++
    } else {
        Write-Host "  FAIL: Wrong error: $($errorResponse.detail)" -ForegroundColor Red
        $script:tests_failed++
    }
}

# Test 5: Finish game
Write-Host ""
Write-Host "TEST: POST /api/game/finish" -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "$API_BASE/game/finish" `
        -Method POST `
        -ContentType "application/json" `
        -Body (@{
            device_id = $TEST_DEVICE
        } | ConvertTo-Json)
    
    Write-Host "  PASS: Finish command sent successfully" -ForegroundColor Green
    Write-Host "    Request ID: $($response.request_id)" -ForegroundColor Gray
    $script:tests_passed++
} catch {
    $errorResponse = $_.ErrorDetails.Message | ConvertFrom-Json
    if ($errorResponse.detail -match "No active game") {
        Write-Host "  INFO: No active game to finish (expected if no hardware connected)" -ForegroundColor Yellow
        $script:tests_skipped++
    } else {
        Write-Host "  FAIL: $_" -ForegroundColor Red
        Write-Host "  Detail: $($errorResponse.detail)" -ForegroundColor Red
        $script:tests_failed++
    }
}

# Test 6: Finish without game (should fail)
Start-Sleep -Milliseconds 500
Write-Host ""
Write-Host "TEST: POST /api/game/finish (no active game - should fail)" -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "$API_BASE/game/finish" `
        -Method POST `
        -ContentType "application/json" `
        -Body (@{
            device_id = $TEST_DEVICE
        } | ConvertTo-Json)
    
    Write-Host "  FAIL: Should have rejected finish with no game" -ForegroundColor Red
    $script:tests_failed++
} catch {
    $errorResponse = $_.ErrorDetails.Message | ConvertFrom-Json
    if ($errorResponse.detail -match "No active game") {
        Write-Host "  PASS: Finish without game correctly rejected" -ForegroundColor Green
        Write-Host "    Reason: $($errorResponse.detail)" -ForegroundColor Gray
        $script:tests_passed++
    } else {
        Write-Host "  FAIL: Wrong error: $($errorResponse.detail)" -ForegroundColor Red
        $script:tests_failed++
    }
}

# Summary
Write-Host ""
Write-Host "===========================================" -ForegroundColor Cyan
Write-Host "  TEST SUMMARY" -ForegroundColor Cyan
Write-Host "===========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Passed:  $tests_passed" -ForegroundColor Green
Write-Host "Failed:  $tests_failed" -ForegroundColor $(if ($tests_failed -gt 0) { "Red" } else { "Gray" })
Write-Host "Skipped: $tests_skipped" -ForegroundColor Yellow
Write-Host ""

if ($tests_failed -eq 0) {
    Write-Host "SUCCESS: All API tests passed!" -ForegroundColor Green
    Write-Host ""
    Write-Host "NEXT STEPS:" -ForegroundColor Cyan
    Write-Host "1. Connect ESP32 hardware" -ForegroundColor Gray
    Write-Host "2. Upload firmware: firmware/aquabuzz_connected/aquabuzz_connected.ino" -ForegroundColor Gray
    Write-Host "3. Start serial gateway: python backend/serial_gateway.py" -ForegroundColor Gray
    Write-Host "4. Open dashboard: dashboard/index.html" -ForegroundColor Gray
    Write-Host "5. Test START GAME and FINISH GAME buttons" -ForegroundColor Gray
    exit 0
} else {
    Write-Host "FAILURE: Some tests failed" -ForegroundColor Red
    Write-Host "Review errors above and fix issues before hardware testing" -ForegroundColor Yellow
    exit 1
}
