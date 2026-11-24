# AquaBuzz Integration Test Script
# Tests serial gateway, MQTT, backend, and dashboard integration

$ErrorActionPreference = 'Stop'

$API_BASE = 'http://localhost:8000/api'
$MQTT_BROKER = 'test.mosquitto.org'
$MQTT_PORT = 1883

Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "    AquaBuzz Integration Test Suite" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host ""

# Test 1: Backend Health
Write-Host "[Test 1] Backend Health Check" -ForegroundColor Yellow
try {
    $health = Invoke-RestMethod -Uri "$API_BASE/health" -TimeoutSec 5
    Write-Host "  Status: $($health.status)" -ForegroundColor Green
    Write-Host "  MQTT: $($health.mqtt_connected)" -ForegroundColor $(if ($health.mqtt_connected) {'Green'} else {'Red'})
    Write-Host "  Devices: $($health.devices.Count)" -ForegroundColor White
    
    if ($health.devices -and $health.devices.Count -gt 0) {
        foreach ($device in $health.devices) {
            $statusColor = if ($device.online) {'Green'} else {'Gray'}
            Write-Host "    - $($device.id): $(if ($device.online) {'Online'} else {'Offline'})" -ForegroundColor $statusColor
            if ($device.last_heartbeat) {
                Write-Host "      Last heartbeat: $($device.last_heartbeat)" -ForegroundColor Gray
            }
        }
    }
    Write-Host "  [PASS]" -ForegroundColor Green
} catch {
    Write-Host "  [FAIL] $_" -ForegroundColor Red
}
Write-Host ""

# Test 2: MQTT Connectivity
Write-Host "[Test 2] MQTT Broker Connectivity" -ForegroundColor Yellow
try {
    $tcp = New-Object System.Net.Sockets.TcpClient
    $task = $tcp.ConnectAsync($MQTT_BROKER, $MQTT_PORT)
    if ($task.Wait(5000) -and $tcp.Connected) {
        Write-Host "  ${MQTT_BROKER}:${MQTT_PORT}: Reachable" -ForegroundColor Green
        $tcp.Close()
        Write-Host "  [PASS]" -ForegroundColor Green
    } else {
        Write-Host "  ${MQTT_BROKER}:${MQTT_PORT}: Timeout" -ForegroundColor Red
        $tcp.Close()
        Write-Host "  [FAIL]" -ForegroundColor Red
    }
} catch {
    Write-Host "  [FAIL] $_" -ForegroundColor Red
}
Write-Host ""

# Test 3: Serial Gateway Process
Write-Host "[Test 3] Serial Gateway Status" -ForegroundColor Yellow
$gatewayProcess = Get-Process -Name python -ErrorAction SilentlyContinue | Where-Object {
    $cmdLine = (Get-CimInstance Win32_Process -Filter "ProcessId = $($_.Id)" -ErrorAction SilentlyContinue).CommandLine
    $cmdLine -like '*serial_gateway.py*'
}

if ($gatewayProcess) {
    Write-Host "  Gateway running: PID $($gatewayProcess.Id)" -ForegroundColor Green
    Write-Host "  [PASS]" -ForegroundColor Green
} else {
    Write-Host "  Gateway NOT running" -ForegroundColor Yellow
    Write-Host "  [WARN] Start gateway with: rise" -ForegroundColor Yellow
}
Write-Host ""

# Test 4: ESP32 COM Port Detection
Write-Host "[Test 4] ESP32 COM Port Detection" -ForegroundColor Yellow
$comPorts = Get-CimInstance Win32_PnPEntity | Where-Object {
    $_.Caption -like '*CH340*' -or $_.Caption -like '*CP210*' -or $_.Caption -like '*USB*Serial*'
}

if ($comPorts) {
    foreach ($port in $comPorts) {
        Write-Host "  Found: $($port.Caption)" -ForegroundColor Green
        Write-Host "    Status: $($port.Status)" -ForegroundColor Gray
    }
    Write-Host "  [PASS]" -ForegroundColor Green
} else {
    Write-Host "  No ESP32 COM port detected" -ForegroundColor Yellow
    Write-Host "  [WARN] Connect ESP32 via USB" -ForegroundColor Yellow
}
Write-Host ""

# Test 5: Database Records
Write-Host "[Test 5] Database Content" -ForegroundColor Yellow
try {
    $runs = Invoke-RestMethod -Uri "$API_BASE/runs?limit=5" -TimeoutSec 5
    $players = Invoke-RestMethod -Uri "$API_BASE/players" -TimeoutSec 5
    
    Write-Host "  Total Runs: $($runs.Count)" -ForegroundColor White
    Write-Host "  Total Players: $($players.Count)" -ForegroundColor White
    
    if ($runs.Count -gt 0) {
        Write-Host "  Recent runs:" -ForegroundColor Cyan
        foreach ($run in $runs | Select-Object -First 3) {
            $duration = [math]::Round($run.duration_ms / 1000, 2)
            Write-Host "    - $($run.player_id): $($run.hits) hits, ${duration}s" -ForegroundColor Gray
        }
    }
    Write-Host "  [PASS]" -ForegroundColor Green
} catch {
    Write-Host "  [FAIL] $_" -ForegroundColor Red
}
Write-Host ""

# Test 6: Dashboard Accessibility
Write-Host "[Test 6] Dashboard HTTP Server" -ForegroundColor Yellow
$dashboardPorts = @(3000, 3001, 3002, 8080, 8081)
$dashboardFound = $false

foreach ($port in $dashboardPorts) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:$port" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
        if ($response.StatusCode -eq 200 -and $response.Content -like '*AquaBuzz*') {
            Write-Host "  Dashboard accessible: http://localhost:$port" -ForegroundColor Green
            $dashboardFound = $true
            break
        }
    } catch {
        # Try next port
    }
}

if ($dashboardFound) {
    Write-Host "  [PASS]" -ForegroundColor Green
} else {
    Write-Host "  Dashboard NOT accessible" -ForegroundColor Yellow
    Write-Host "  [WARN] Start dashboard with: rise" -ForegroundColor Yellow
}
Write-Host ""

# Summary
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "    Test Summary" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "  1. If services not running: run 'rise'" -ForegroundColor White
Write-Host "  2. Connect ESP32 via USB" -ForegroundColor White
Write-Host "  3. Watch gateway terminal for connection messages" -ForegroundColor White
Write-Host "  4. Play maze game to generate events" -ForegroundColor White
Write-Host "  5. Verify dashboard updates automatically" -ForegroundColor White
Write-Host ""
