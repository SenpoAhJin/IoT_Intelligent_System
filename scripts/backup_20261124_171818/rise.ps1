# ========================================
#          WIREBUZZ STARTUP SYSTEM
# ========================================
# One-command startup for WireBuzz IoT Project
# Command: rise
# Author: WireBuzz Team
# ========================================

$ErrorActionPreference = "Stop"

# Project configuration
$PROJECT_NAME = "WIREBUZZ"
$PROJECT_ROOT = "c:\Users\Alord\OneDrive\Documents\School\COSC 105 - Ma'am Mikae\Intelligent_System_IS"
$VENV_PYTHON = Join-Path $PROJECT_ROOT ".venv\Scripts\python.exe"
$BACKEND_DIR = Join-Path $PROJECT_ROOT "backend"
$DASHBOARD_DIR = Join-Path $PROJECT_ROOT "dashboard"
$MOSQUITTO_EXE = "C:\Program Files\mosquitto\mosquitto.exe"
$MOSQUITTO_CONF = Join-Path $PROJECT_ROOT "mosquitto.conf"

# Port configuration
$MQTT_PORT = 1883
$API_PORT = 8000
$DASHBOARD_PORTS = @(3000, 3001, 3002, 8080, 8081)

# Process tracking file
$PROCESS_TRACKER = Join-Path $PROJECT_ROOT ".wirebuzz-processes.json"

# Color output helpers
function Write-Status {
    param([string]$Message, [string]$Status = "INFO")
    
    $timestamp = Get-Date -Format "HH:mm:ss"
    switch ($Status) {
        "OK"      { Write-Host "[$timestamp] " -NoNewline; Write-Host "[OK]      " -ForegroundColor Green -NoNewline; Write-Host $Message }
        "FAILED"  { Write-Host "[$timestamp] " -NoNewline; Write-Host "[FAILED]  " -ForegroundColor Red -NoNewline; Write-Host $Message }
        "WARNING" { Write-Host "[$timestamp] " -NoNewline; Write-Host "[WARNING] " -ForegroundColor Yellow -NoNewline; Write-Host $Message }
        "INFO"    { Write-Host "[$timestamp] " -NoNewline; Write-Host "[INFO]    " -ForegroundColor Cyan -NoNewline; Write-Host $Message }
        "STEP"    { Write-Host "[$timestamp] " -NoNewline; Write-Host "[STEP]    " -ForegroundColor Magenta -NoNewline; Write-Host $Message }
    }
}

function Write-Header {
    param([string]$Text)
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  $Text" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
}

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

function Test-URLResponds {
    param([string]$Url, [int]$TimeoutSeconds = 5)
    
    try {
        $response = Invoke-WebRequest -Uri $Url -TimeoutSec $TimeoutSeconds -UseBasicParsing -ErrorAction Stop
        return $response.StatusCode -eq 200
    } catch {
        return $false
    }
}

function Save-ProcessInfo {
    param(
        [string]$Service,
        [int]$ProcessId,
        [int]$Port,
        [string]$Url = ""
    )
    
    $processes = @{}
    if (Test-Path $PROCESS_TRACKER) {
        $processes = Get-Content $PROCESS_TRACKER | ConvertFrom-Json -AsHashtable
    }
    
    $processes[$Service] = @{
        pid = $ProcessId
        port = $Port
        url = $Url
        started_at = (Get-Date).ToString("o")
    }
    
    $processes | ConvertTo-Json | Set-Content $PROCESS_TRACKER
}

function Get-SavedProcessInfo {
    if (Test-Path $PROCESS_TRACKER) {
        return Get-Content $PROCESS_TRACKER | ConvertFrom-Json
    }
    return $null
}

# ========================================
# VALIDATION PHASE
# ========================================

Write-Header "WIREBUZZ STARTUP — VALIDATION"

$validationResults = @{
    project_dir = $false
    venv = $false
    python_exe = $false
    backend = $false
    dashboard = $false
    mosquitto = $false
}

# Check project directory
Write-Status "Checking project directory..." "STEP"
if (Test-Path $PROJECT_ROOT) {
    Write-Status "Project directory found: $PROJECT_ROOT" "OK"
    $validationResults.project_dir = $true
} else {
    Write-Status "Project directory not found: $PROJECT_ROOT" "FAILED"
    exit 1
}

# Check virtual environment
Write-Status "Checking Python virtual environment..." "STEP"
if (Test-Path (Join-Path $PROJECT_ROOT ".venv")) {
    Write-Status "Virtual environment found" "OK"
    $validationResults.venv = $true
} else {
    Write-Status "Virtual environment not found at .venv" "FAILED"
    exit 1
}

# Check Python executable
Write-Status "Checking Python executable..." "STEP"
if (Test-Path $VENV_PYTHON) {
    $pythonVersion = & $VENV_PYTHON --version 2>&1
    Write-Status "Python found: $pythonVersion" "OK"
    $validationResults.python_exe = $true
} else {
    Write-Status "Python executable not found: $VENV_PYTHON" "FAILED"
    exit 1
}

# Check backend
Write-Status "Checking backend files..." "STEP"
$backendMain = Join-Path $BACKEND_DIR "app\main.py"
if (Test-Path $backendMain) {
    Write-Status "Backend main.py found" "OK"
    $validationResults.backend = $true
} else {
    Write-Status "Backend main.py not found" "FAILED"
    exit 1
}

# Check dashboard
Write-Status "Checking dashboard files..." "STEP"
$dashboardIndex = Join-Path $DASHBOARD_DIR "index.html"
if (Test-Path $dashboardIndex) {
    Write-Status "Dashboard index.html found" "OK"
    $validationResults.dashboard = $true
} else {
    Write-Status "Dashboard index.html not found" "FAILED"
    exit 1
}

# Check Mosquitto
Write-Status "Checking Mosquitto..." "STEP"
if (Test-Path $MOSQUITTO_EXE) {
    Write-Status "Mosquitto executable found" "OK"
    $validationResults.mosquitto = $true
} else {
    Write-Status "Mosquitto not found at: $MOSQUITTO_EXE" "FAILED"
    exit 1
}

Write-Host ""
Write-Status "All validations passed!" "OK"
Start-Sleep -Seconds 1

# ========================================
# MOSQUITTO MQTT BROKER
# ========================================

Write-Header "STARTING MOSQUITTO MQTT BROKER"

$mqttHealthy = $false
$mqttPid = $null

# Check if MQTT port is already in use
$existingMqttPid = Get-ProcessOwningPort -Port $MQTT_PORT

if ($existingMqttPid) {
    Write-Status "Port $MQTT_PORT already in use by PID $existingMqttPid" "WARNING"
    
    # Test if it's responding
    Write-Status "Testing existing MQTT broker..." "STEP"
    
    # Simple connection test using mosquitto_pub if available
    $mosquittoPub = "C:\Program Files\mosquitto\mosquitto_pub.exe"
    if (Test-Path $mosquittoPub) {
        try {
            $testResult = & $mosquittoPub -h localhost -p $MQTT_PORT -t "wirebuzz/test" -m "ping" -q 2>&1
            if ($LASTEXITCODE -eq 0) {
                Write-Status "Existing MQTT broker is healthy, reusing it" "OK"
                $mqttHealthy = $true
                $mqttPid = $existingMqttPid
            } else {
                Write-Status "Existing process on port $MQTT_PORT is not a healthy MQTT broker" "WARNING"
            }
        } catch {
            Write-Status "Could not verify existing MQTT broker health" "WARNING"
        }
    } else {
        Write-Status "Assuming existing MQTT broker is healthy" "OK"
        $mqttHealthy = $true
        $mqttPid = $existingMqttPid
    }
}

if (-not $mqttHealthy) {
    Write-Status "Starting new Mosquitto broker..." "STEP"
    
    # Start Mosquitto in a new window
    $mosquittoProcess = Start-Process -FilePath $MOSQUITTO_EXE `
        -ArgumentList "-c", "`"$MOSQUITTO_CONF`"", "-v" `
        -WindowStyle Normal `
        -PassThru
    
    $mqttPid = $mosquittoProcess.Id
    Write-Status "Mosquitto started (PID: $mqttPid)" "OK"
    
    # Wait for MQTT to be ready
    Write-Status "Waiting for MQTT broker to be ready..." "STEP"
    $mqttReady = $false
    for ($i = 1; $i -le 10; $i++) {
        Start-Sleep -Seconds 1
        $currentPid = Get-ProcessOwningPort -Port $MQTT_PORT
        if ($currentPid -eq $mqttPid) {
            $mqttReady = $true
            break
        }
    }
    
    if ($mqttReady) {
        Write-Status "MQTT broker is ready on port $MQTT_PORT" "OK"
        $mqttHealthy = $true
    } else {
        Write-Status "MQTT broker failed to start properly" "FAILED"
        exit 1
    }
}

Save-ProcessInfo -Service "mqtt" -ProcessId $mqttPid -Port $MQTT_PORT -Url "mqtt://localhost:$MQTT_PORT"

# ========================================
# FASTAPI BACKEND
# ========================================

Write-Header "STARTING FASTAPI BACKEND"

$backendHealthy = $false
$backendPid = $null
$apiHealthUrl = "http://127.0.0.1:$API_PORT/api/health"

# Check if API port is already in use
$existingApiPid = Get-ProcessOwningPort -Port $API_PORT

if ($existingApiPid) {
    Write-Status "Port $API_PORT already in use by PID $existingApiPid" "WARNING"
    
    # Test if it's the WireBuzz backend
    Write-Status "Testing existing backend..." "STEP"
    if (Test-URLResponds -Url $apiHealthUrl) {
        Write-Status "Existing WireBuzz backend is healthy, reusing it" "OK"
        $backendHealthy = $true
        $backendPid = $existingApiPid
    } else {
        Write-Status "Existing process on port $API_PORT is not a healthy WireBuzz backend" "WARNING"
        Write-Status "Please stop the process using port $API_PORT and try again" "FAILED"
        exit 1
    }
}

if (-not $backendHealthy) {
    Write-Status "Starting FastAPI backend..." "STEP"
    
    # Start backend in a new window
    $backendProcess = Start-Process powershell -ArgumentList `
        "-NoExit", `
        "-Command", `
        "Write-Host 'WIREBUZZ - FASTAPI BACKEND' -ForegroundColor Cyan; Write-Host ''; cd '$BACKEND_DIR'; & '$VENV_PYTHON' -m uvicorn app.main:app --host 127.0.0.1 --port $API_PORT" `
        -WindowStyle Normal `
        -PassThru
    
    $backendPid = $backendProcess.Id
    Write-Status "FastAPI started (PID: $backendPid)" "OK"
    
    # Wait for backend to be ready
    Write-Status "Waiting for FastAPI to be ready..." "STEP"
    $backendReady = $false
    for ($i = 1; $i -le 20; $i++) {
        Start-Sleep -Seconds 1
        if (Test-URLResponds -Url $apiHealthUrl) {
            $backendReady = $true
            break
        }
        Write-Host "." -NoNewline
    }
    Write-Host ""
    
    if ($backendReady) {
        Write-Status "FastAPI backend is ready" "OK"
        
        # Verify MQTT connection
        try {
            $healthData = Invoke-RestMethod -Uri $apiHealthUrl -TimeoutSec 5
            if ($healthData.mqtt_connected) {
                Write-Status "Backend MQTT connection verified" "OK"
            } else {
                Write-Status "Backend started but MQTT not connected yet" "WARNING"
            }
        } catch {
            Write-Status "Could not verify backend health details" "WARNING"
        }
        
        $backendHealthy = $true
    } else {
        Write-Status "FastAPI backend failed to start properly" "FAILED"
        exit 1
    }
}

Save-ProcessInfo -Service "backend" -ProcessId $backendPid -Port $API_PORT -Url "http://127.0.0.1:$API_PORT"

# ========================================
# DASHBOARD SERVER
# ========================================

Write-Header "STARTING DASHBOARD SERVER"

$dashboardHealthy = $false
$dashboardPid = $null
$selectedPort = $null
$dashboardUrl = ""

# Find available port
Write-Status "Finding available port for dashboard..." "STEP"

foreach ($port in $DASHBOARD_PORTS) {
    $existingPid = Get-ProcessOwningPort -Port $port
    
    if ($existingPid) {
        Write-Status "Port $port in use by PID $existingPid, trying next..." "INFO"
        continue
    }
    
    # Test if we can actually bind to it
    if (Test-PortAvailable -Port $port) {
        Write-Status "Port $port is available and bindable" "OK"
        $selectedPort = $port
        break
    } else {
        Write-Status "Port $port appears available but cannot bind, trying next..." "WARNING"
    }
}

if (-not $selectedPort) {
    Write-Status "No available ports found in candidate list: $($DASHBOARD_PORTS -join ', ')" "FAILED"
    Write-Status "Please free up one of these ports and try again" "FAILED"
    exit 1
}

$dashboardUrl = "http://127.0.0.1:$selectedPort"

Write-Status "Starting dashboard server on port $selectedPort..." "STEP"

# Start dashboard in a new window
$dashboardProcess = Start-Process powershell -ArgumentList `
    "-NoExit", `
    "-Command", `
    "Write-Host 'WIREBUZZ - DASHBOARD SERVER' -ForegroundColor Cyan; Write-Host 'Serving at: http://127.0.0.1:$selectedPort' -ForegroundColor Green; Write-Host ''; cd '$DASHBOARD_DIR'; & '$VENV_PYTHON' -m http.server $selectedPort --bind 127.0.0.1" `
    -WindowStyle Normal `
    -PassThru

$dashboardPid = $dashboardProcess.Id
Write-Status "Dashboard server started (PID: $dashboardPid)" "OK"

# Wait for dashboard to be ready
Write-Status "Waiting for dashboard to be ready..." "STEP"
$dashboardReady = $false
for ($i = 1; $i -le 10; $i++) {
    Start-Sleep -Seconds 1
    if (Test-URLResponds -Url $dashboardUrl) {
        $dashboardReady = $true
        break
    }
    Write-Host "." -NoNewline
}
Write-Host ""

if ($dashboardReady) {
    Write-Status "Dashboard server is ready at $dashboardUrl" "OK"
    $dashboardHealthy = $true
} else {
    Write-Status "Dashboard server failed to respond properly" "FAILED"
    exit 1
}

Save-ProcessInfo -Service "dashboard" -ProcessId $dashboardPid -Port $selectedPort -Url $dashboardUrl

# ========================================
# OPEN BROWSER
# ========================================

Write-Header "OPENING BROWSER"

Write-Status "Opening dashboard..." "STEP"
Start-Process $dashboardUrl

Start-Sleep -Seconds 1

Write-Status "Opening API documentation..." "STEP"
Start-Process "http://127.0.0.1:$API_PORT/docs"

Start-Sleep -Seconds 1

Write-Status "Opening health endpoint..." "STEP"
Start-Process $apiHealthUrl

# Final Status
Write-Host ""
Write-Host "WIREBUZZ STARTED" -ForegroundColor Green
Write-Host "Dashboard: $dashboardUrl" -ForegroundColor Cyan
Write-Host "API Docs: http://127.0.0.1:$API_PORT/docs" -ForegroundColor Cyan
Write-Host "Health: http://127.0.0.1:$API_PORT/api/health" -ForegroundColor Cyan
Write-Host "To stop: rise-stop" -ForegroundColor Yellow
Write-Host ""
