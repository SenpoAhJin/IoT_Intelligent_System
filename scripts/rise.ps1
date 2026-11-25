# AquaBuzz RISE - Complete Automated Startup System (CORRECTED)
# PowerShell 5.1+ Compatible
# Properly tracks actual service processes, not wrappers

$ErrorActionPreference = 'Stop'

# ============================================
# CONFIGURATION
# ============================================

$script:PROJECT_ROOT = (Get-Item $PSScriptRoot).Parent.FullName
$script:VENV_PYTHON = Join-Path $PROJECT_ROOT '.venv\Scripts\python.exe'
$script:BACKEND_DIR = Join-Path $PROJECT_ROOT 'backend'
$script:DASHBOARD_DIR = Join-Path $PROJECT_ROOT 'dashboard'
$script:PROCESS_TRACKER = Join-Path $PROJECT_ROOT '.aquabuzz-processes.json'
$script:ENV_FILE = Join-Path $BACKEND_DIR '.env'

# Service configuration
$script:API_PORT = 8000
$script:DASHBOARD_PORTS = @(3000, 3001, 3002, 8080, 8081)

# State tracking
$script:BackendProcessId = $null
$script:GatewayProcessId = $null
$script:DashboardProcessId = $null
$script:DashboardPort = $null

# ============================================
# UTILITY FUNCTIONS
# ============================================

function Write-Section {
    param([string]$Message, [string]$Color = 'Cyan')
    Write-Host ''
    Write-Host ('=' * 60) -ForegroundColor $Color
    Write-Host "  $Message" -ForegroundColor $Color
    Write-Host ('=' * 60) -ForegroundColor $Color
    Write-Host ''
}

function Write-Step {
    param([string]$Message, [string]$Status = 'INFO', [string]$Detail = '')
    
    $color = switch ($Status) {
        'OK' { 'Green' }
        'WARN' { 'Yellow' }
        'FAIL' { 'Red' }
        'INFO' { 'Cyan' }
        default { 'White' }
    }
    
    Write-Host "[$Status] $Message" -ForegroundColor $color
    if ($Detail) {
        Write-Host "  $Detail" -ForegroundColor Gray
    }
}

function Get-ProcessOwningPort {
    param([int]$Port)
    
    try {
        $connection = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($connection) {
            return $connection.OwningProcess
        }
    } catch {
        return $null
    }
    return $null
}

function Get-ProcessCommandLine {
    param([int]$ProcessId)
    
    try {
        $proc = Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId" -ErrorAction SilentlyContinue
        if ($proc) {
            return $proc.CommandLine
        }
    } catch {
        return $null
    }
    return $null
}

function Test-IsAquaBuzzProcess {
    param([int]$ProcessId, [string]$ServiceType)
    
    $cmdLine = Get-ProcessCommandLine -ProcessId $ProcessId
    if (-not $cmdLine) {
        return $false
    }
    
    # Check for ForgeMind - never touch these
    if ($cmdLine -like '*arise*' -or $cmdLine -like '*rest*' -or $cmdLine -like '*ForgeMind*') {
        return $false
    }
    
    # Check for AquaBuzz identifiers
    switch ($ServiceType) {
        'backend' {
            return $cmdLine -like '*uvicorn*app.main:app*'
        }
        'gateway' {
            return $cmdLine -like '*serial_gateway.py*'
        }
        'dashboard' {
            return $cmdLine -like '*http.server*'
        }
        default {
            return $false
        }
    }
}

function Save-ProcessTracker {
    $data = @{}
    
    if ($script:BackendProcessId) {
        $data['backend'] = @{
            pid = $script:BackendProcessId
            port = $script:API_PORT
            url = "http://localhost:$script:API_PORT"
            started_at = (Get-Date).ToString('o')
        }
    }
    
    if ($script:GatewayProcessId) {
        $data['gateway'] = @{
            pid = $script:GatewayProcessId
            port = 0
            url = 'USB Serial'
            started_at = (Get-Date).ToString('o')
        }
    }
    
    if ($script:DashboardProcessId -and $script:DashboardPort) {
        $data['dashboard'] = @{
            pid = $script:DashboardProcessId
            port = $script:DashboardPort
            url = "http://localhost:$script:DashboardPort"
            started_at = (Get-Date).ToString('o')
        }
    }
    
    if ($data.Count -gt 0) {
        try {
            $json = $data | ConvertTo-Json -Depth 5
            Set-Content -Path $script:PROCESS_TRACKER -Value $json -Encoding UTF8
            Write-Step 'Process tracker saved' 'OK'
        } catch {
            Write-Step 'Failed to save process tracker' 'WARN' $_.Exception.Message
        }
    }
}

# ============================================
# VALIDATION FUNCTIONS
# ============================================

function Test-ProjectRequirements {
    Write-Step 'Validating project requirements' 'INFO'
    
    $checks = @{
        'Project Root' = (Test-Path $script:PROJECT_ROOT)
        'Python Virtual Environment' = (Test-Path $script:VENV_PYTHON)
        'Backend Directory' = (Test-Path $script:BACKEND_DIR)
        'Dashboard Directory' = (Test-Path $script:DASHBOARD_DIR)
        'Backend Configuration (.env)' = (Test-Path $script:ENV_FILE)
        'Serial Gateway Script' = (Test-Path (Join-Path $script:BACKEND_DIR 'serial_gateway.py'))
        'Dashboard HTML' = (Test-Path (Join-Path $script:DASHBOARD_DIR 'index.html'))
    }
    
    $allPassed = $true
    foreach ($check in $checks.GetEnumerator()) {
        if ($check.Value) {
            Write-Step $check.Key 'OK'
        } else {
            Write-Step $check.Key 'FAIL'
            $allPassed = $false
        }
    }
    
    if (-not $allPassed) {
        throw 'Project requirements validation failed'
    }
    
    Write-Host ''
}

# ============================================
# SERVICE MANAGEMENT FUNCTIONS
# ============================================

function Start-BackendService {
    Write-Step 'Starting FastAPI Backend' 'INFO'
    
    # Check if already running
    $existingPid = Get-ProcessOwningPort -Port $script:API_PORT
    
    if ($existingPid) {
        if (Test-IsAquaBuzzProcess -ProcessId $existingPid -ServiceType 'backend') {
            Write-Step 'Checking existing backend health' 'INFO'
            
            try {
                $response = Invoke-WebRequest -Uri "http://localhost:$script:API_PORT/api/health" -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
                $health = $response.Content | ConvertFrom-Json
                
                if ($health.status -eq 'healthy') {
                    Write-Step 'Existing backend is healthy - reusing' 'OK'
                    $script:BackendProcessId = $existingPid
                    
                    # Report MQTT status
                    if ($health.mqtt_connected) {
                        Write-Step 'MQTT is connected' 'OK'
                    } else {
                        Write-Step 'MQTT is NOT connected' 'WARN' 'Backend will retry connection'
                    }
                    
                    Write-Host ''
                    return
                }
            } catch {
                Write-Step 'Existing backend not responding, will restart' 'WARN'
                Stop-Process -Id $existingPid -Force -ErrorAction SilentlyContinue
                Start-Sleep -Seconds 2
            }
        } else {
            $cmdLine = Get-ProcessCommandLine -ProcessId $existingPid
            Write-Step "Port $script:API_PORT occupied by another process" 'FAIL' "PID: $existingPid"
            throw "Port $script:API_PORT is in use by: $cmdLine"
        }
    }
    
    # Start new backend
    Write-Step 'Launching uvicorn backend' 'INFO'
    
    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = $script:VENV_PYTHON
    $startInfo.Arguments = "-m uvicorn app.main:app --host 0.0.0.0 --port $script:API_PORT --env-file .env"
    $startInfo.WorkingDirectory = $script:BACKEND_DIR
    $startInfo.UseShellExecute = $true
    $startInfo.WindowStyle = 'Normal'
    
    $process = [System.Diagnostics.Process]::Start($startInfo)
    Write-Step "Backend wrapper started (PID: $($process.Id))" 'OK'
    
    # Wait for actual backend process to bind to port
    Write-Step 'Waiting for backend to bind to port' 'INFO'
    
    $maxAttempts = 20
    $actualPid = $null
    
    for ($i = 1; $i -le $maxAttempts; $i++) {
        Start-Sleep -Milliseconds 500
        
        $actualPid = Get-ProcessOwningPort -Port $script:API_PORT
        if ($actualPid) {
            Write-Step "Backend process found (PID: $actualPid)" 'OK'
            $script:BackendProcessId = $actualPid
            break
        }
    }
    
    if (-not $actualPid) {
        Write-Step 'Backend did not bind to port' 'FAIL'
        throw 'Backend startup failed - process did not bind to port'
    }
    
    # Wait for backend API to be ready
    Write-Step 'Waiting for backend API to be ready' 'INFO'
    
    $ready = $false
    $mqttConnected = $false
    
    for ($i = 1; $i -le 15; $i++) {
        Start-Sleep -Seconds 1
        
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:$script:API_PORT/api/health" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
            if ($response.StatusCode -eq 200) {
                $health = $response.Content | ConvertFrom-Json
                
                if ($health.status -eq 'healthy') {
                    $ready = $true
                    $mqttConnected = $health.mqtt_connected
                    break
                }
            }
        } catch {
            # Still starting
        }
    }
    
    if ($ready) {
        Write-Step 'Backend API is ready' 'OK' "http://localhost:$script:API_PORT"
        Write-Step 'API Documentation' 'OK' "http://localhost:$script:API_PORT/docs"
        
        if ($mqttConnected) {
            Write-Step 'MQTT is connected' 'OK'
        } else {
            Write-Step 'MQTT is NOT connected' 'WARN' 'This may prevent gateway from working. Check backend logs.'
        }
    } else {
        Write-Step 'Backend API not responding' 'WARN' 'Backend process is running but API not ready'
    }
    
    Write-Host ''
}

function Start-SerialGateway {
    Write-Step 'Starting Serial-to-MQTT Gateway' 'INFO'
    
    # Check for already running gateway
    $pythonProcs = Get-Process -Name python -ErrorAction SilentlyContinue
    $existingGateway = $null
    
    foreach ($proc in $pythonProcs) {
        if (Test-IsAquaBuzzProcess -ProcessId $proc.Id -ServiceType 'gateway') {
            $existingGateway = $proc
            break
        }
    }
    
    if ($existingGateway) {
        Write-Step 'Serial Gateway already running - reusing' 'OK' "PID: $($existingGateway.Id)"
        $script:GatewayProcessId = $existingGateway.Id
        Write-Host ''
        return
    }
    
    # Verify script exists
    $gatewayScript = Join-Path $script:BACKEND_DIR 'serial_gateway.py'
    if (-not (Test-Path $gatewayScript)) {
        Write-Step 'Serial gateway script not found' 'FAIL' $gatewayScript
        Write-Step 'Skipping gateway startup' 'WARN'
        Write-Host ''
        return
    }
    
    # Start gateway
    Write-Step 'Launching serial gateway' 'INFO'
    
    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = $script:VENV_PYTHON
    $startInfo.Arguments = "`"$gatewayScript`""
    $startInfo.WorkingDirectory = $script:BACKEND_DIR
    $startInfo.UseShellExecute = $true
    $startInfo.WindowStyle = 'Normal'
    
    $process = [System.Diagnostics.Process]::Start($startInfo)
    
    # Wait briefly for process to stabilize
    Start-Sleep -Milliseconds 1000
    
    # Find the actual Python process
    $actualGateway = $null
    $pythonProcs = Get-Process -Name python -ErrorAction SilentlyContinue
    
    foreach ($proc in $pythonProcs) {
        if (Test-IsAquaBuzzProcess -ProcessId $proc.Id -ServiceType 'gateway') {
            # Check if this process started recently
            if ($proc.StartTime -gt (Get-Date).AddSeconds(-5)) {
                $actualGateway = $proc
                break
            }
        }
    }
    
    if ($actualGateway) {
        $script:GatewayProcessId = $actualGateway.Id
        Write-Step "Gateway started (PID: $($actualGateway.Id))" 'OK'
    } else {
        $script:GatewayProcessId = $process.Id
        Write-Step "Gateway wrapper started (PID: $($process.Id))" 'WARN' 'Could not verify actual Python process'
    }
    
    Write-Step 'ESP32 auto-detection enabled' 'INFO' 'Connect ESP32 via USB'
    Write-Step 'Gateway will publish heartbeats to MQTT' 'INFO'
    
    Write-Host ''
}

function Start-DashboardService {
    Write-Step 'Starting Dashboard HTTP Server' 'INFO'
    
    # Check if dashboard already running on any port
    foreach ($port in $script:DASHBOARD_PORTS) {
        $existingPid = Get-ProcessOwningPort -Port $port
        if ($existingPid) {
            if (Test-IsAquaBuzzProcess -ProcessId $existingPid -ServiceType 'dashboard') {
                # Verify it's serving our dashboard
                try {
                    $response = Invoke-WebRequest -Uri "http://localhost:$port" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
                    if ($response.StatusCode -eq 200 -and $response.Content -like '*AquaBuzz*') {
                        Write-Step 'Dashboard already running - reusing' 'OK' "Port: $port"
                        $script:DashboardProcessId = $existingPid
                        $script:DashboardPort = $port
                        Write-Host ''
                        return
                    }
                } catch {
                    # Not our dashboard
                }
            }
        }
    }
    
    # Find available port
    $selectedPort = $null
    foreach ($port in $script:DASHBOARD_PORTS) {
        $existingPid = Get-ProcessOwningPort -Port $port
        if (-not $existingPid) {
            $selectedPort = $port
            break
        }
    }
    
    if (-not $selectedPort) {
        Write-Step 'No available ports for dashboard' 'FAIL' "Tried: $($script:DASHBOARD_PORTS -join ', ')"
        throw 'Dashboard port allocation failed'
    }
    
    # Verify dashboard files exist
    $indexPath = Join-Path $script:DASHBOARD_DIR 'index.html'
    if (-not (Test-Path $indexPath)) {
        Write-Step 'Dashboard files not found' 'FAIL' $indexPath
        throw 'Dashboard HTML not found'
    }
    
    # Start dashboard server
    Write-Step "Launching dashboard on port $selectedPort" 'INFO'
    
    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = $script:VENV_PYTHON
    $startInfo.Arguments = "-m http.server $selectedPort"
    $startInfo.WorkingDirectory = $script:DASHBOARD_DIR
    $startInfo.UseShellExecute = $true
    $startInfo.WindowStyle = 'Normal'
    
    $process = [System.Diagnostics.Process]::Start($startInfo)
    
    # Wait for dashboard to bind to port
    Write-Step 'Waiting for dashboard to bind to port' 'INFO'
    
    $actualPid = $null
    for ($i = 1; $i -le 10; $i++) {
        Start-Sleep -Milliseconds 500
        
        $actualPid = Get-ProcessOwningPort -Port $selectedPort
        if ($actualPid) {
            Write-Step "Dashboard process found (PID: $actualPid)" 'OK'
            $script:DashboardProcessId = $actualPid
            $script:DashboardPort = $selectedPort
            break
        }
    }
    
    if (-not $actualPid) {
        Write-Step 'Dashboard did not bind to port' 'WARN'
        $script:DashboardProcessId = $process.Id
        $script:DashboardPort = $selectedPort
    }
    
    # Verify dashboard is accessible
    $ready = $false
    for ($i = 1; $i -le 5; $i++) {
        Start-Sleep -Seconds 1
        
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:$selectedPort" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
            if ($response.StatusCode -eq 200) {
                $ready = $true
                break
            }
        } catch {
            # Still starting
        }
    }
    
    if ($ready) {
        Write-Step 'Dashboard is ready' 'OK' "http://localhost:$selectedPort"
    } else {
        Write-Step 'Dashboard may still be starting' 'WARN' "Check http://localhost:$selectedPort manually"
    }
    
    Write-Host ''
}

function Open-DashboardBrowser {
    if ($script:DashboardPort) {
        Write-Step 'Opening dashboard in browser' 'INFO'
        
        $url = "http://localhost:$script:DashboardPort"
        try {
            Start-Process $url
            Write-Step 'Browser opened' 'OK' $url
        } catch {
            Write-Step 'Could not auto-open browser' 'WARN' "Please open manually: $url"
        }
    }
    
    Write-Host ''
}

# ============================================
# MAIN EXECUTION
# ============================================

function Start-AquaBuzz {
    Write-Section 'AQUABUZZ INTELLIGENT SYSTEM - RISE' 'Cyan'
    Write-Host '  Automated Startup System' -ForegroundColor Gray
    Write-Host '  USB Serial + Public MQTT' -ForegroundColor Gray
    
    try {
        # Pre-flight checks
        Test-ProjectRequirements
        
        # Start services
        Start-BackendService
        Start-SerialGateway
        Start-DashboardService
        
        # Save process tracking
        Save-ProcessTracker
        
        # Open browser
        Open-DashboardBrowser
        
        # Success summary
        Write-Section 'AQUABUZZ STARTUP COMPLETE' 'Green'
        
        Write-Host 'Services Running:' -ForegroundColor Cyan
        Write-Host ''
        
        if ($script:BackendProcessId) {
            Write-Host "  [OK] Backend API" -ForegroundColor Green
            Write-Host "       http://localhost:$script:API_PORT" -ForegroundColor Gray
            Write-Host "       PID: $script:BackendProcessId" -ForegroundColor Gray
        } else {
            Write-Host "  [FAIL] Backend API: NOT STARTED" -ForegroundColor Red
        }
        Write-Host ''
        
        if ($script:GatewayProcessId) {
            Write-Host "  [OK] Serial Gateway" -ForegroundColor Green
            Write-Host "       USB Serial to MQTT" -ForegroundColor Gray
            Write-Host "       PID: $script:GatewayProcessId" -ForegroundColor Gray
        } else {
            Write-Host "  [WARN] Serial Gateway: NOT STARTED" -ForegroundColor Yellow
        }
        Write-Host ''
        
        if ($script:DashboardProcessId -and $script:DashboardPort) {
            Write-Host "  [OK] Dashboard" -ForegroundColor Green
            Write-Host "       http://localhost:$script:DashboardPort" -ForegroundColor Gray
            Write-Host "       PID: $script:DashboardProcessId" -ForegroundColor Gray
        } else {
            Write-Host "  [FAIL] Dashboard: NOT STARTED" -ForegroundColor Red
        }
        Write-Host ''
        
        Write-Host 'Important Notes:' -ForegroundColor Yellow
        Write-Host '  - If MQTT shows as NOT connected, check backend terminal for errors' -ForegroundColor White
        Write-Host '  - Gateway requires MQTT to publish events' -ForegroundColor White
        Write-Host '  - Connect ESP32 via USB for gateway to detect it' -ForegroundColor White
        Write-Host ''
        
        Write-Host 'To stop all services:' -ForegroundColor Yellow
        Write-Host '  rise-stop' -ForegroundColor White
        Write-Host ''
        
    } catch {
        Write-Section 'STARTUP FAILED' 'Red'
        $errorMsg = $_.Exception.Message
        Write-Host "Error: $errorMsg" -ForegroundColor Red
        Write-Host ''
        Write-Host 'Troubleshooting:' -ForegroundColor Yellow
        Write-Host '  1. Run: rise-stop' -ForegroundColor White
        Write-Host '  2. Check for port conflicts (8000, 3000)' -ForegroundColor White
        Write-Host '  3. Verify Python virtual environment' -ForegroundColor White
        Write-Host '  4. Try: rise again' -ForegroundColor White
        Write-Host ''
        exit 1
    }
}

# Run the startup
Start-AquaBuzz
