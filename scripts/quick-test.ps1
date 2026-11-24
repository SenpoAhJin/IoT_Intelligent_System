# AquaBuzz Quick Test
# Simple test of running services

$API_BASE = 'http://localhost:8000/api'
$DASHBOARD_URL = 'http://localhost:3000'

Write-Host ''
Write-Host '==================================================' -ForegroundColor Cyan
Write-Host '    AquaBuzz Quick Test' -ForegroundColor Cyan
Write-Host '==================================================' -ForegroundColor Cyan
Write-Host ''

# Test Backend
Write-Host 'Testing Backend...' -ForegroundColor Cyan
try {
    $health = Invoke-RestMethod -Uri "$API_BASE/health" -TimeoutSec 5
    Write-Host "  Status: $($health.status)" -ForegroundColor Green
    Write-Host "  MQTT: $($health.mqtt_connected)" -ForegroundColor $(if ($health.mqtt_connected) { 'Green' } else { 'Yellow' })
    Write-Host "  Runs: $($health.total_runs)" -ForegroundColor White
    Write-Host "  Players: $($health.total_players)" -ForegroundColor White
    Write-Host ''
} catch {
    Write-Host "  FAILED: $_" -ForegroundColor Red
    Write-Host ''
}

# Test API Endpoints
Write-Host 'Testing API Endpoints...' -ForegroundColor Cyan
try {
    $runs = Invoke-RestMethod -Uri "$API_BASE/runs?limit=5" -TimeoutSec 5
    Write-Host "  Runs: $($runs.Length) records" -ForegroundColor Green
} catch {
    Write-Host "  Runs: FAILED" -ForegroundColor Red
}

try {
    $players = Invoke-RestMethod -Uri "$API_BASE/players" -TimeoutSec 5
    Write-Host "  Players: $($players.Length) records" -ForegroundColor Green
} catch {
    Write-Host "  Players: FAILED" -ForegroundColor Red
}

try {
    $leaderboard = Invoke-RestMethod -Uri "$API_BASE/leaderboard?limit=5" -TimeoutSec 5
    Write-Host "  Leaderboard: $($leaderboard.Length) records" -ForegroundColor Green
} catch {
    Write-Host "  Leaderboard: FAILED" -ForegroundColor Red
}
Write-Host ''

# Test Dashboard
Write-Host 'Testing Dashboard...' -ForegroundColor Cyan
try {
    $response = Invoke-WebRequest -Uri $DASHBOARD_URL -UseBasicParsing -TimeoutSec 5
    if ($response.StatusCode -eq 200) {
        Write-Host "  Accessible: YES" -ForegroundColor Green
        Write-Host "  URL: $DASHBOARD_URL" -ForegroundColor White
    }
} catch {
    Write-Host "  Accessible: NO" -ForegroundColor Red
}
Write-Host ''

Write-Host 'Test Complete!' -ForegroundColor Green
Write-Host ''
