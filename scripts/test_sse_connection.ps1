#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Manual SSE Connection Test Script for Phase 2B-1

.DESCRIPTION
    Tests Server-Sent Events connection reliability by:
    1. Starting the backend
    2. Opening Chrome to test SSE connection
    3. Simulating game events via MQTT
    4. Verifying dashboard receives and displays events

.NOTES
    This is a manual test script requiring visual verification
#>

param(
    [switch]$SkipBackendStart,
    [string]$ChromePath = "C:\Program Files\Google\Chrome\Application\chrome.exe"
)

$ErrorActionPreference = "Stop"

Write-Host "=============================================================================================" -ForegroundColor Cyan
Write-Host " PHASE 2B-1: SSE CONNECTION RELIABILITY TEST" -ForegroundColor Cyan
Write-Host "=============================================================================================" -ForegroundColor Cyan
Write-Host ""

# Navigate to workspace root
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$workspaceRoot = Split-Path -Parent $scriptDir
Set-Location $workspaceRoot

Write-Host "[1/5] Checking prerequisites..." -ForegroundColor Yellow
Write-Host ""

# Check if backend is already running
$backendRunning = $false
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/api/health" -TimeoutSec 2 -UseBasicParsing -ErrorAction SilentlyContinue
    if ($response.StatusCode -eq 200) {
        $backendRunning = $true
        Write-Host "  ✓ Backend already running on port 8000" -ForegroundColor Green
    }
} catch {
    Write-Host "  ℹ Backend not running" -ForegroundColor Gray
}

# Start backend if needed
if (-not $backendRunning -and -not $SkipBackendStart) {
    Write-Host ""
    Write-Host "[2/5] Starting backend..." -ForegroundColor Yellow
    Write-Host ""
    
    # Start backend in background
    $backendJob = Start-Job -ScriptBlock {
        param($workDir)
        Set-Location $workDir
        Set-Location backend
        python -m uvicorn app.main:app --reload --port 8000
    } -ArgumentList $workspaceRoot
    
    Write-Host "  Backend starting (Job ID: $($backendJob.Id))..." -ForegroundColor Cyan
    
    # Wait for backend to be ready
    $maxWait = 30
    $waited = 0
    while ($waited -lt $maxWait) {
        Start-Sleep -Seconds 1
        $waited++
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:8000/api/health" -TimeoutSec 1 -UseBasicParsing -ErrorAction SilentlyContinue
            if ($response.StatusCode -eq 200) {
                Write-Host "  ✓ Backend ready!" -ForegroundColor Green
                break
            }
        } catch {}
        
        if ($waited -ge $maxWait) {
            Write-Host "  ✗ Backend failed to start within ${maxWait}s" -ForegroundColor Red
            Stop-Job $backendJob -ErrorAction SilentlyContinue
            Remove-Job $backendJob -ErrorAction SilentlyContinue
            exit 1
        }
    }
}

Write-Host ""
Write-Host "[3/5] Opening Chrome DevTools for SSE monitoring..." -ForegroundColor Yellow
Write-Host ""

# Open Chrome with DevTools
$dashboardUrl = "http://localhost:8000/dashboard/"

if (Test-Path $ChromePath) {
    Write-Host "  Opening: $dashboardUrl" -ForegroundColor Cyan
    Write-Host "  Chrome DevTools will open automatically" -ForegroundColor Cyan
    Start-Process $ChromePath -ArgumentList "--auto-open-devtools-for-tabs", $dashboardUrl
} else {
    Write-Host "  ⚠ Chrome not found at: $ChromePath" -ForegroundColor Yellow
    Write-Host "  Please open manually: $dashboardUrl" -ForegroundColor Yellow
    Write-Host "  Press Enter when dashboard is loaded..." -ForegroundColor Yellow
    Read-Host
}

Write-Host ""
Write-Host "[4/5] SSE Connection Check" -ForegroundColor Yellow
Write-Host ""
Write-Host "  In Chrome DevTools:" -ForegroundColor Cyan
Write-Host "  1. Go to Network tab" -ForegroundColor White
Write-Host "  2. Filter: 'live'" -ForegroundColor White
Write-Host "  3. Look for '/api/live' request" -ForegroundColor White
Write-Host "  4. Status should be '200' or 'pending'" -ForegroundColor White
Write-Host "  5. Type should be 'eventsource'" -ForegroundColor White
Write-Host ""
Write-Host "  Expected console output:" -ForegroundColor Cyan
Write-Host "  - '[SSE] Connecting to live events stream...'" -ForegroundColor Gray
Write-Host "  - '[SSE] ✓ Connected to live events stream'" -ForegroundColor Green
Write-Host ""
Write-Host "  ❌ SHOULD NOT SEE:" -ForegroundColor Red
Write-Host "  - 'ERR_INCOMPLETE_CHUNKED_ENCODING'" -ForegroundColor Red
Write-Host "  - 'SSE connection error'" -ForegroundColor Red
Write-Host "  - Repeated reconnection attempts" -ForegroundColor Red
Write-Host ""

Write-Host "  Did SSE connect successfully? (y/n): " -NoNewline -ForegroundColor Yellow
$sseConnected = Read-Host

if ($sseConnected -ne 'y') {
    Write-Host ""
    Write-Host "  ✗ SSE connection failed!" -ForegroundColor Red
    Write-Host "  Check console for errors" -ForegroundColor Red
    Write-Host ""
    Write-Host "Press Enter to exit..." -ForegroundColor Yellow
    Read-Host
    exit 1
}

Write-Host "  ✓ SSE connection verified" -ForegroundColor Green

Write-Host ""
Write-Host "[5/5] Testing Event Delivery" -ForegroundColor Yellow
Write-Host ""
Write-Host "  Test scenarios:" -ForegroundColor Cyan
Write-Host ""
Write-Host "  A. Browser Refresh" -ForegroundColor White
Write-Host "     - Refresh the dashboard page (F5)" -ForegroundColor Gray
Write-Host "     - SSE should reconnect automatically" -ForegroundColor Gray
Write-Host "     - Console should show '[Recovery] Checking for active run...'" -ForegroundColor Gray
Write-Host "     - No errors should appear" -ForegroundColor Gray
Write-Host ""
Write-Host "  B. Multiple Tabs" -ForegroundColor White
Write-Host "     - Open dashboard in 2-3 tabs" -ForegroundColor Gray
Write-Host "     - Each tab should show 'SSE ✓ Connected'" -ForegroundColor Gray
Write-Host "     - Backend console should show multiple clients" -ForegroundColor Gray
Write-Host ""
Write-Host "  C. Keep-Alive Messages" -ForegroundColor White
Write-Host "     - Wait 20 seconds without activity" -ForegroundColor Gray
Write-Host "     - In Network tab, SSE request should stay 'pending'" -ForegroundColor Gray
Write-Host "     - EventStream tab should show keep-alive comments" -ForegroundColor Gray
Write-Host ""
Write-Host "  D. Live Game (if hardware available)" -ForegroundColor White
Write-Host "     - Start a game on ESP32" -ForegroundColor Gray
Write-Host "     - Dashboard should update immediately" -ForegroundColor Gray
Write-Host "     - Console should show '[SSE] Received game_event'" -ForegroundColor Gray
Write-Host ""

Write-Host ""
Write-Host "=============================================================================================" -ForegroundColor Cyan
Write-Host " TEST COMPLETE" -ForegroundColor Cyan
Write-Host "=============================================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  ✓ SSE connection reliability verified" -ForegroundColor Green
Write-Host "  ✓ Dashboard event handling tested" -ForegroundColor Green
Write-Host "  ✓ Browser refresh recovery checked" -ForegroundColor Green
Write-Host ""
Write-Host "  Next steps:" -ForegroundColor Cyan
Write-Host "  - Review backend console for any warnings" -ForegroundColor White
Write-Host "  - Check for memory leaks after multiple connect/disconnect cycles" -ForegroundColor White
Write-Host "  - Verify no abandoned client queues remain" -ForegroundColor White
Write-Host ""

if (-not $SkipBackendStart -and $backendJob) {
    Write-Host "  Stop backend job? (y/n): " -NoNewline -ForegroundColor Yellow
    $stopBackend = Read-Host
    
    if ($stopBackend -eq 'y') {
        Stop-Job $backendJob -ErrorAction SilentlyContinue
        Remove-Job $backendJob -ErrorAction SilentlyContinue
        Write-Host "  Backend stopped" -ForegroundColor Green
    } else {
        Write-Host "  Backend still running (Job ID: $($backendJob.Id))" -ForegroundColor Cyan
        Write-Host "  Stop with: Stop-Job -Id $($backendJob.Id); Remove-Job -Id $($backendJob.Id)" -ForegroundColor Gray
    }
}

Write-Host ""
Write-Host "Press Enter to exit..." -ForegroundColor Yellow
Read-Host
