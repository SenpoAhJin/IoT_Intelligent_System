# AquaBuzz Startup Script - USB Serial Gateway Edition
# PowerShell 5.1 Compatible
# Starts FastAPI backend, Serial Gateway, and dashboard

$ErrorActionPreference = 'Stop'

# Configuration - Dynamically determine project root
$script:PROJECT_ROOT = (Get-Item $PSScriptRoot).Parent.FullName
$script:VENV_PYTHON = Join-Path $PROJECT_ROOT '.venv\Scripts\python.exe'
$script:BACKEND_DIR = Join-Path $PROJECT_ROOT 'backend'
$script:DASHBOARD_DIR = Join-Path $PROJECT_ROOT 'dashboard'
$script:PROCESS_TRACKER = Join-Path $PROJECT_ROOT '.aquabuzz-processes.json'
$script:ENV_FILE = Join-Path $BACKEND_DIR '.env'

# Public MQTT broker
$script:MQTT_BROKER = 'test.mosquitto.org'
$script:MQTT_PORT = 1883
$script:API_PORT = 8000
$script:DASHBOARD_PORTS = @(3000, 3001, 3002, 8080, 8081)

# Global state
$script:BackendProcessId = $null
$script:GatewayProcessId = $null
$script:DashboardProcessId = $null
$script:DashboardPort = $null

# Functions
function Test-ProjectRequirements {
    Write-Host 'Validating project requirements...' -ForegroundColor Cyan
    
    $checks = @{
        'Project Root' = (Test-Path $script:PROJECT_ROOT)
        'Python Virtual Env' = (Test-Path $script:VENV_PYTHON)
        'Backend Directory' = (Test-Path $script:BACKEND_DIR)
        'Dashboard Directory' = (Test-Path $script:DASHBOARD_DIR)
        'Backend .env File' = (Test-Path $script:ENV_FILE)
        'Serial Gateway Script' = (Test-Path (Join-Path $script:BACKEND_DIR 'serial_gateway.py'))
    }
    
    $allPassed = $true
    foreach ($check in $checks.GetEnumerator()) {
        if ($check.Value) {
            Write-Host "  [OK]  $($check.Key)" -ForegroundColor Green
        } else {
            Write-Host "  [FAIL] $($check.Key)" -ForegroundColor Red
            $allPassed = $false
        }
    }
    
    if (-not $allPassed) {
        throw 'Project requirements validation failed'
    }
    
    Write-Host 'All requirements validated' -ForegroundColor Green
    Write-Host ''
}

function Test-InternetConnectivity {
    Write-Host 'Checking internet connectivity...' -ForegroundColor Cyan
    
    try {
        $response = Test-Connection -ComputerName '8.8.8.8' -Count 1 -Quiet -ErrorAction Stop
        if ($response) {
            Write-Host '  Internet connectivity: OK' -ForegroundColor Green
        } else {
            Write-Host '  Internet connectivity: FAILED' -ForegroundColor Yellow
            Write-Host '  Serial Gateway will reconnect when internet returns' -ForegroundColor Yellow
        }
    } catch {
        Write-Host '  Internet connectivity: FAILED' -ForegroundColor Yellow
        Write-Host '  Serial Gateway will reconnect when internet returns' -ForegroundColor Yellow
    }
    
    Write-Host ''
}

function Test-PortAvailability {
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

function Get-ProcessDetails {
    param([int]$ProcessId)
    
    try {
        $proc = Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId" -ErrorAction SilentlyContinue
        if ($proc) {
            return @{
                Name = $proc.Name
                CommandLine = $proc.CommandLine
                ProcessId = $ProcessId
            }
        }
    } catch {
        return $null
    }
    return $null
}

function Test-IsAquaBuzzBackend {
    param([int]$ProcessId)
    
    $details = Get-ProcessDetails -ProcessId $ProcessId
    if (-not $details) {
        return $false
    }
    
    # Check if it's a Python process running uvicorn with our app
    if ($details.Name -eq 'python.exe' -and $details.CommandLine -like '*uvicorn*app.main:app*') {
        return $true
    }
    
    return $false
}

function Test-IsForgeMindProcess {
    param([int]$ProcessId)
    
    $details = Get-ProcessDetails -ProcessId $ProcessId
    if (-not $details) {
        return $false
    }
    
    # Check for ForgeMind identifiers
    if ($details.CommandLine -like '*arise*' -or $details.CommandLine -like '*rest*' -or $details.CommandLine -like '*ForgeMind*') {
        return $true
    }
    
    return $false
}

function Start-BackendService {
    Write-Host 'Starting FastAPI Backend...' -ForegroundColor Cyan
    
    $existingProcessId = Get-ProcessOwningPort -Port $script:API_PORT
    
    if ($existingProcessId) {
        Write-Host "  Port $script:API_PORT already in use by PID $existingProcessId" -ForegroundColor Yellow
        
        # Check if it's a ForgeMind process - never touch it
        if (Test-IsForgeMindProcess -ProcessId $existingProcessId) {
            Write-Host '  WARNING: Port occupied by ForgeMind process' -ForegroundColor Red
            Write-Host '  Will NOT terminate ForgeMind process' -ForegroundColor Red
            throw "Port $script:API_PORT is occupied by ForgeMind. Please use a different port."
        }
        
        # Check if it's an AquaBuzz backend
        if (Test-IsAquaBuzzBackend -ProcessId $existingProcessId) {
            Write-Host '  Existing process appears to be AquaBuzz backend' -ForegroundColor Yellow
            
            # Check if it's healthy
            try {
                $response = Invoke-WebRequest -Uri "http://localhost:$script:API_PORT/api/health" -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
                $health = $response.Content | ConvertFrom-Json
                
                if ($health.status -eq 'healthy') {
                    Write-Host '  Existing AquaBuzz backend is healthy - reusing it' -ForegroundColor Green
                    $script:BackendProcessId = $existingProcessId
                    Write-Host ''
                    return
                }
            } catch {
                Write-Host '  Existing backend not responding to health check' -ForegroundColor Yellow
            }
        }
        
        # Port occupied by unknown process
        $details = Get-ProcessDetails -ProcessId $existingProcessId
        if ($details) {
            Write-Host "  Port occupied by: $($details.Name)" -ForegroundColor Yellow
            Write-Host "  Command: $($details.CommandLine)" -ForegroundColor Gray
        }
        throw "Port $script:API_PORT is occupied. Please stop the conflicting process first."
    }
    
    Write-Host '  Launching FastAPI with uvicorn...' -ForegroundColor Cyan
    
    $uvicornCmd = "& '$script:VENV_PYTHON' -m uvicorn app.main:app --host 0.0.0.0 --port $script:API_PORT"
    $process = Start-Process powershell -ArgumentList "-NoProfile", "-Command", $uvicornCmd -WindowStyle Normal -WorkingDirectory $script:BACKEND_DIR -PassThru
    
    $script:BackendProcessId = $process.Id
    Write-Host "  Backend wrapper started (PID: $script:BackendProcessId)" -ForegroundColor Green
    
    # Wait briefly and find actual Python process
    Write-Host '  Locating actual Python process...' -ForegroundColor Cyan
    Start-Sleep -Milliseconds 1500
    
    $actualPid = Get-ProcessOwningPort -Port $script:API_PORT
    if ($actualPid) {
        $script:BackendProcessId = $actualPid
        Write-Host "  Tracked actual Python process (PID: $actualPid)" -ForegroundColor Green
    } else {
        Write-Host "  Warning: Could not find Python process, using wrapper PID" -ForegroundColor Yellow
    }
    
    Write-Host '  Waiting for backend to be ready...' -ForegroundColor Cyan
    $ready = $false
    $mqttConnected = $false
    
    for ($i = 1; $i -le 30; $i++) {
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
            # Still starting up
        }
    }
    
    if ($ready) {
        Write-Host "  Backend ready on port $script:API_PORT" -ForegroundColor Green
        Write-Host "  API: http://localhost:$script:API_PORT" -ForegroundColor Cyan
        Write-Host "  Docs: http://localhost:$script:API_PORT/docs" -ForegroundColor Cyan
        
        if ($mqttConnected) {
            Write-Host "  MQTT Status: CONNECTED to $script:MQTT_BROKER" -ForegroundColor Green
        } else {
            Write-Host "  MQTT Status: CONNECTING... (may take a moment)" -ForegroundColor Yellow
        }
    } else {
        Write-Host '  WARNING: Backend may still be starting' -ForegroundColor Yellow
        Write-Host '  Check http://localhost:8000/api/health for status' -ForegroundColor Yellow
    }
    
    Write-Host ''
}

function Start-SerialGateway {
    Write-Host 'Starting Serial-to-MQTT Gateway...' -ForegroundColor Cyan
    
    # Check if gateway is already running
    $existingGateway = Get-Process -Name python -ErrorAction SilentlyContinue | Where-Object {
        $cmdLine = (Get-CimInstance Win32_Process -Filter "ProcessId = $($_.Id)" -ErrorAction SilentlyContinue).CommandLine
        $cmdLine -like '*serial_gateway.py*'
    }
    
    if ($existingGateway) {
        Write-Host "  Serial Gateway already running (PID: $($existingGateway.Id))" -ForegroundColor Yellow
        $script:GatewayProcessId = $existingGateway.Id
        Write-Host ''
        return
    }
    
    Write-Host '  Launching serial gateway...' -ForegroundColor Cyan
    
    $gatewayScript = Join-Path $script:BACKEND_DIR 'serial_gateway.py'
    
    # Check if script exists
    if (-not (Test-Path $gatewayScript)) {
        Write-Host '  WARNING: Serial gateway script not found' -ForegroundColor Yellow
        Write-Host "  Expected: $gatewayScript" -ForegroundColor Gray
        Write-Host '  Skipping gateway startup' -ForegroundColor Yellow
        Write-Host ''
        return
    }
    
    $gatewayCmd = "& '$script:VENV_PYTHON' '$gatewayScript'"
    $process = Start-Process powershell -ArgumentList "-NoProfile", "-Command", $gatewayCmd -WindowStyle Normal -WorkingDirectory $script:BACKEND_DIR -PassThru
    
    $script:GatewayProcessId = $process.Id
    Write-Host "  Gateway wrapper started (PID: $script:GatewayProcessId)" -ForegroundColor Green
    
    # Wait briefly and find actual Python process
    Write-Host '  Locating actual Python process...' -ForegroundColor Cyan
    Start-Sleep -Milliseconds 1500
    
    $pythonProcs = Get-Process -Name python -ErrorAction SilentlyContinue
    $actualPid = $null
    foreach ($proc in $pythonProcs) {
        $cmdLine = (Get-CimInstance Win32_Process -Filter "ProcessId = $($proc.Id)" -ErrorAction SilentlyContinue).CommandLine
        if ($cmdLine -like '*serial_gateway.py*') {
            $actualPid = $proc.Id
            break
        }
    }
    
    if ($actualPid) {
        $script:GatewayProcessId = $actualPid
        Write-Host "  Tracked actual Python process (PID: $actualPid)" -ForegroundColor Green
    } else {
        Write-Host "  Warning: Could not find Python process, using wrapper PID" -ForegroundColor Yellow
    }
    Write-Host '  Gateway will auto-detect ESP32 COM port' -ForegroundColor Cyan
    Write-Host '  Connect ESP32 via USB to begin publishing events' -ForegroundColor Yellow
    Write-Host '  Note: Gateway will wait for ESP32 connection' -ForegroundColor Gray
    
    Write-Host ''
}

function Start-DashboardService {
    Write-Host 'Starting Dashboard HTTP Server...' -ForegroundColor Cyan
    
    $selectedPort = $null
    $existingProcessId = $null
    
    # Check if any dashboard port is already in use
    foreach ($port in $script:DASHBOARD_PORTS) {
        $processId = Get-ProcessOwningPort -Port $port
        if ($processId) {
            Write-Host "  Port $port already in use by PID $processId" -ForegroundColor Yellow
            
            # Check if it's serving our dashboard
            try {
                $response = Invoke-WebRequest -Uri "http://localhost:$port" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
                if ($response.StatusCode -eq 200 -and $response.Content -like '*AquaBuzz*') {
                    Write-Host '  Existing dashboard server detected - reusing it' -ForegroundColor Green
                    $script:DashboardProcessId = $processId
                    $script:DashboardPort = $port
                    Write-Host ''
                    return
                }
            } catch {
                # Port occupied but not responding or not our dashboard
            }
            
            $selectedPort = $port
            $existingProcessId = $processId
            break
        }
    }
    
    # If port occupied by non-dashboard process, skip to next available
    if ($existingProcessId -and -not $script:DashboardProcessId) {
        Write-Host "  Port $selectedPort occupied by other service, trying next port..." -ForegroundColor Yellow
        $selectedPort = $null
    }
    
    # Find first available port
    if (-not $selectedPort) {
        foreach ($port in $script:DASHBOARD_PORTS) {
            if (Test-PortAvailability -Port $port) {
                $selectedPort = $port
                break
            }
        }
    }
    
    if (-not $selectedPort) {
        Write-Host '  ERROR: No available ports for dashboard' -ForegroundColor Red
        Write-Host '  Tried ports: 3000, 3001, 3002, 8080, 8081' -ForegroundColor Gray
        throw 'Dashboard port allocation failed'
    }
    
    Write-Host "  Launching dashboard on port $selectedPort..." -ForegroundColor Cyan
    
    # Verify dashboard directory and index.html exist
    $indexPath = Join-Path $script:DASHBOARD_DIR 'index.html'
    if (-not (Test-Path $indexPath)) {
        Write-Host '  ERROR: Dashboard index.html not found' -ForegroundColor Red
        Write-Host "  Expected: $indexPath" -ForegroundColor Gray
        throw 'Dashboard files not found'
    }
    
    $serverCmd = "& '$script:VENV_PYTHON' -m http.server $selectedPort"
    $process = Start-Process powershell -ArgumentList "-NoProfile", "-Command", $serverCmd -WindowStyle Normal -WorkingDirectory $script:DASHBOARD_DIR -PassThru
    
    $script:DashboardProcessId = $process.Id
    $script:DashboardPort = $selectedPort
    
    Write-Host "  Dashboard started (PID: $script:DashboardProcessId)" -ForegroundColor Green
    
    Write-Host '  Waiting for dashboard to be ready...' -ForegroundColor Cyan
    $ready = $false
    for ($i = 1; $i -le 10; $i++) {
        Start-Sleep -Seconds 1
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:$selectedPort" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
            if ($response.StatusCode -eq 200) {
                $ready = $true
                break
            }
        } catch {
            # Still starting up
        }
    }
    
    if ($ready) {
        Write-Host "  Dashboard ready on port $selectedPort" -ForegroundColor Green
        Write-Host "  URL: http://localhost:$selectedPort" -ForegroundColor Cyan
    } else {
        Write-Host '  WARNING: Dashboard may still be starting' -ForegroundColor Yellow
        Write-Host "  Check http://localhost:$selectedPort manually" -ForegroundColor Gray
    }
    
    Write-Host ''
}

function Open-BrowserWindows {
    Write-Host 'Opening browser windows...' -ForegroundColor Cyan
    
    if ($script:DashboardPort) {
        $url = "http://localhost:$script:DashboardPort"
        try {
            Start-Process $url
            Write-Host "  Browser opened: $url" -ForegroundColor Green
        } catch {
            Write-Host "  Could not auto-open browser" -ForegroundColor Yellow
            Write-Host "  Please open manually: $url" -ForegroundColor Gray
        }
    } else {
        Write-Host '  Dashboard not started, skipping browser launch' -ForegroundColor Yellow
    }
    
    Write-Host ''
}

function Save-ProcessInfo {
    param(
        [string]$Service,
        [int]$ProcessId,
        [int]$Port,
        [string]$Url = ''
    )
    
    $processes = @{}
    if (Test-Path $script:PROCESS_TRACKER) {
        try {
            $content = Get-Content $script:PROCESS_TRACKER -Raw
            $processes = $content | ConvertFrom-Json -AsHashtable
        } catch {
            $processes = @{}
        }
    }
    
    $processes[$Service] = @{
        pid = $ProcessId
        port = $Port
        url = $Url
        started_at = (Get-Date).ToString('o')
    }
    
    try {
        $json = $processes | ConvertTo-Json
        Set-Content -Path $script:PROCESS_TRACKER -Value $json -Encoding UTF8
    } catch {
        Write-Host "  Warning: Could not save process tracker" -ForegroundColor Yellow
    }
}

# Main execution
Write-Host ''
Write-Host '==================================================' -ForegroundColor Cyan
Write-Host '    AquaBuzz Intelligent System - RISE' -ForegroundColor Cyan
Write-Host '    USB Serial Gateway + Public MQTT' -ForegroundColor Cyan
Write-Host '==================================================' -ForegroundColor Cyan
Write-Host ''

try {
    Test-ProjectRequirements
    Test-InternetConnectivity
    Start-BackendService
    Start-SerialGateway
    Start-DashboardService

    # Save process tracking information
    if ($script:BackendProcessId) {
        Save-ProcessInfo -Service 'backend' -ProcessId $script:BackendProcessId -Port $script:API_PORT -Url "http://localhost:$script:API_PORT"
    }
    if ($script:GatewayProcessId) {
        Save-ProcessInfo -Service 'gateway' -ProcessId $script:GatewayProcessId -Port 0 -Url 'USB Serial'
    }
    if ($script:DashboardProcessId -and $script:DashboardPort) {
        Save-ProcessInfo -Service 'dashboard' -ProcessId $script:DashboardProcessId -Port $script:DashboardPort -Url "http://localhost:$script:DashboardPort"
    }

    Open-BrowserWindows

    Write-Host ''
    Write-Host '==================================================' -ForegroundColor Green
    Write-Host '    AquaBuzz Startup Complete' -ForegroundColor Green
    Write-Host '==================================================' -ForegroundColor Green
    Write-Host ''
    Write-Host 'Services Running:' -ForegroundColor Cyan
    
    if ($script:BackendProcessId) {
        Write-Host "  Backend API: http://localhost:$script:API_PORT (PID: $script:BackendProcessId)" -ForegroundColor White
    } else {
        Write-Host "  Backend API: NOT STARTED" -ForegroundColor Red
    }
    
    if ($script:GatewayProcessId) {
        Write-Host "  Serial Gateway: USB Serial to MQTT (PID: $script:GatewayProcessId)" -ForegroundColor White
    } else {
        Write-Host "  Serial Gateway: NOT STARTED" -ForegroundColor Yellow
    }
    
    if ($script:DashboardProcessId -and $script:DashboardPort) {
        Write-Host "  Dashboard: http://localhost:$script:DashboardPort (PID: $script:DashboardProcessId)" -ForegroundColor White
    } else {
        Write-Host "  Dashboard: NOT STARTED" -ForegroundColor Red
    }
    
    Write-Host "  MQTT Broker: $script:MQTT_BROKER:$script:MQTT_PORT (public)" -ForegroundColor White
    Write-Host ''
    Write-Host 'Architecture:' -ForegroundColor Yellow
    Write-Host '  ESP32 -> USB Serial -> Gateway -> MQTT -> Backend -> Dashboard' -ForegroundColor White
    Write-Host ''
    Write-Host 'Network Independence:' -ForegroundColor Yellow
    Write-Host '  [OK] No WiFi credentials needed on ESP32' -ForegroundColor White
    Write-Host '  [OK] Works with any laptop WiFi connection' -ForegroundColor White
    Write-Host '  [OK] Gateway reconnects automatically' -ForegroundColor White
    Write-Host ''
    Write-Host 'ESP32 Setup:' -ForegroundColor Yellow
    Write-Host '  1. Upload aquabuzz_core.ino firmware' -ForegroundColor White
    Write-Host '  2. Connect ESP32 via USB' -ForegroundColor White
    Write-Host '  3. Gateway will auto-detect COM port' -ForegroundColor White
    Write-Host ''
    Write-Host 'To stop all services, run: rise-stop' -ForegroundColor Yellow
    Write-Host ''
} catch {
    Write-Host ''
    Write-Host 'ERROR: Startup failed' -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host ''
    Write-Host 'Troubleshooting:' -ForegroundColor Yellow
    Write-Host '  - Check if ports 8000 or 3000 are already in use' -ForegroundColor Gray
    Write-Host '  - Verify Python virtual environment exists' -ForegroundColor Gray
    Write-Host '  - Run rise-stop to clean up any stuck processes' -ForegroundColor Gray
    Write-Host ''
    exit 1
}
