# AquaBuzz System Test Script
# Tests backend API, MQTT connectivity, and dashboard functionality

$ErrorActionPreference = 'Stop'

$API_BASE = 'http://localhost:8000/api'
$DASHBOARD_URL = 'http://localhost:3000'
$MQTT_BROKER = 'test.mosquitto.org'
$MQTT_PORT = 1883

Write-Host ''
Write-Host '==================================================' -ForegroundColor Cyan
Write-Host '    AquaBuzz System Test Suite' -ForegroundColor Cyan
Write-Host '==================================================' -ForegroundColor Cyan
Write-Host ''

# Test 1: Backend Health
Write-Host '[TEST 1] Backend Health Check...' -ForegroundColor Cyan
try {
    $health = Invoke-RestMethod -Uri "$API_BASE/health" -Method Get -TimeoutSec 5
    Write-Host "  Status: $($health.status)" -ForegroundColor Green
    Write-Host "  MQTT Connected: $($health.mqtt_connected)" -ForegroundColor $(if ($health.mqtt_connected) { 'Green' } else { 'Yellow' })
    Write-Host "  Total Runs: $($health.total_runs)" -ForegroundColor White
    Write-Host "  Total Players: $($health.total_players)" -ForegroundColor White
    Write-Host "  Active Runs: $($health.active_runs)" -ForegroundColor White
    Write-Host "  Completed Runs: $($health.completed_runs)" -ForegroundColor White
    
    if ($health.devices -and $health.devices.Length -gt 0) {
        Write-Host "  Devices:" -ForegroundColor White
        foreach ($device in $health.devices) {
            Write-Host "    - $($device.id): $(if ($device.online) { 'Online' } else { 'Offline' })" -ForegroundColor $(if ($device.online) { 'Green' } else { 'Gray' })
        }
    } else {
        Write-Host "  Devices: None connected" -ForegroundColor Gray
    }
    Write-Host "  ✓ PASSED" -ForegroundColor Green
} catch {
    Write-Host "  ✗ FAILED: $($_.Exception.Message)" -ForegroundColor Red
}
Write-Host ''

# Test 2: API Endpoints
Write-Host '[TEST 2] API Endpoints...' -ForegroundColor Cyan
$endpoints = @(
    @{ Path = '/runs?limit=5'; Name = 'Get Runs' },
    @{ Path = '/players'; Name = 'Get Players' },
    @{ Path = '/leaderboard?limit=5'; Name = 'Get Leaderboard' }
)

foreach ($endpoint in $endpoints) {
    try {
        $response = Invoke-RestMethod -Uri "$API_BASE$($endpoint.Path)" -Method Get -TimeoutSec 5
        $count = if ($response -is [Array]) { $response.Length } else { 1 }
        Write-Host "  $($endpoint.Name): $count record(s) ✓" -ForegroundColor Green
    } catch {
        Write-Host "  $($endpoint.Name): FAILED" -ForegroundColor Red
    }
}
Write-Host ''

# Test 3: Dashboard Accessibility
Write-Host '[TEST 3] Dashboard Accessibility...' -ForegroundColor Cyan
try {
    $response = Invoke-WebRequest -Uri $DASHBOARD_URL -UseBasicParsing -TimeoutSec 5
    if ($response.StatusCode -eq 200) {
        Write-Host "  Dashboard accessible at $DASHBOARD_URL✓" -ForegroundColor Green
        
        # Check if dashboard contains expected elements
        $content = $response.Content
        $checks = @(
            @{ Text = 'AquaBuzz Dashboard'; Name = 'Title' },
            @{ Text = 'System Health'; Name = 'Health Section' },
            @{ Text = 'Leaderboard'; Name = 'Leaderboard Section' },
            @{ Text = 'Recent Runs'; Name = 'Runs Section' }
        )
        
        foreach ($check in $checks) {
            if ($content -like "*$($check.Text)*") {
                Write-Host "    - $($check.Name) present ✓" -ForegroundColor Green
            } else {
                Write-Host "    - $($check.Name) missing ✗" -ForegroundColor Yellow
            }
        }
    } else {
        Write-Host "  Dashboard returned status code: $($response.StatusCode) ✗" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  Dashboard not accessible: $($_.Exception.Message) ✗" -ForegroundColor Red
}
Write-Host ''

# Test 4: MQTT Broker Connectivity
Write-Host '[TEST 4] MQTT Broker Connectivity...' -ForegroundColor Cyan
try {
    $tcpClient = New-Object System.Net.Sockets.TcpClient
    $connectTask = $tcpClient.ConnectAsync($MQTT_BROKER, $MQTT_PORT)
    $timeout = 5000
    
    if ($connectTask.Wait($timeout)) {
        if ($tcpClient.Connected) {
            Write-Host "  MQTT broker reachable at ${MQTT_BROKER}:${MQTT_PORT} ✓" -ForegroundColor Green
            $tcpClient.Close()
        } else {
            Write-Host "  Cannot connect to MQTT broker ✗" -ForegroundColor Red
        }
    } else {
        $tcpClient.Close()
        Write-Host "  MQTT broker connection timeout ✗" -ForegroundColor Red
    }
} catch {
    Write-Host "  MQTT broker test failed: $($_.Exception.Message) ✗" -ForegroundColor Red
}
Write-Host ''

# Test 5: Database Records
Write-Host '[TEST 5] Database Content...' -ForegroundColor Cyan
try {
    $runs = Invoke-RestMethod -Uri "$API_BASE/runs?limit=10" -Method Get -TimeoutSec 5
    $players = Invoke-RestMethod -Uri "$API_BASE/players" -Method Get -TimeoutSec 5
    
    Write-Host "  Total Runs: $($runs.Length)" -ForegroundColor White
    Write-Host "  Total Players: $($players.Length)" -ForegroundColor White
    
    if ($runs.Length -gt 0) {
        Write-Host "  Latest Run:" -ForegroundColor White
        $latest = $runs[0]
        Write-Host "    Player: $($latest.player_id)" -ForegroundColor Gray
        Write-Host "    Hits: $($latest.hits)" -ForegroundColor Gray
        Write-Host "    Duration: $([math]::Round($latest.duration_ms / 1000, 2))s" -ForegroundColor Gray
        Write-Host "    Status: $($latest.status)" -ForegroundColor Gray
    } else {
        Write-Host "  No runs recorded yet" -ForegroundColor Gray
    }
    
    Write-Host "  ✓ PASSED" -ForegroundColor Green
} catch {
    Write-Host "  ✗ FAILED: $($_.Exception.Message)" -ForegroundColor Red
}
Write-Host ''

# Summary
Write-Host '==================================================' -ForegroundColor Cyan
Write-Host '    Test Summary' -ForegroundColor Cyan
Write-Host '==================================================' -ForegroundColor Cyan
Write-Host ''
Write-Host 'Next Steps:' -ForegroundColor Yellow
Write-Host '  1. Connect ESP32 via USB to test Serial Gateway' -ForegroundColor White
Write-Host '  2. Verify gateway auto-detects COM port' -ForegroundColor White
Write-Host '  3. Test game events are published to MQTT' -ForegroundColor White
Write-Host '  4. Verify dashboard updates in real-time' -ForegroundColor White
Write-Host ''
Write-Host 'Manual Testing:' -ForegroundColor Yellow
Write-Host "  Dashboard: $DASHBOARD_URL" -ForegroundColor White
Write-Host "  API Docs: http://localhost:8000/docs" -ForegroundColor White
Write-Host "  API Health: http://localhost:8000/api/health" -ForegroundColor White
Write-Host ''
