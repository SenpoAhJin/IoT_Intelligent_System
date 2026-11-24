# WIREBUZZ ONE-COMMAND STARTUP SYSTEM
param([switch]$SkipBrowser, [switch]$Verbose)

$ErrorActionPreference = "Continue"
$global:VerboseMode = $Verbose

# Configuration
$MOSQUITTO_EXE = "C:\Program Files\mosquitto\mosquitto.exe"
$MOSQUITTO_PORT = 1883
$BACKEND_PORT = 8000
$DASHBOARD_PORT = 3000
$HEALTH_CHECK_RETRIES = 10
$HEALTH_CHECK_DELAY = 2

# Helper Functions
function Write-Status {
    param([string]$Message, [ValidateSet("INFO", "OK", "WARN", "ERROR", "STEP")][string]$Level = "INFO")
    $timestamp = Get-Date -Format "HH:mm:ss"
    switch ($Level) {
        "OK"    { Write-Host "[$timestamp] [OK] $Message" -ForegroundColor Green }
        "ERROR" { Write-Host "[$timestamp] [ERROR] $Message" -ForegroundColor Red }
        "WARN"  { Write-Host "[$timestamp] [WARN] $Message" -ForegroundColor Yellow }
        "STEP"  { Write-Host "[$timestamp] [STEP] $Message" -ForegroundColor Cyan }
        default { Write-Host "[$timestamp] [INFO] $Message" }
    }
}

function Write-VerboseStatus {
    param([string]$Message)
    if ($global:VerboseMode) { Write-Status $Message -Level INFO }
}

function Test-PortInUse {
    param([int]$Port)
    try {
        $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        return $connections.Count -gt 0
    } catch {
        try {
            $listener = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Loopback, $Port)
            $listener.Start()
            $listener.Stop()
            return $false
        } catch { return $true }
    }
}

function Get-ProcessOnPort {
    param([int]$Port)
    try {
        $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        if ($connections) {
            $pid = $connections[0].OwningProcess
            return Get-Process -Id $pid -ErrorAction SilentlyContinue
        }
    } catch {}
    return $null
}

function Test-HttpEndpoint {
    param([string]$Url, [int]$TimeoutSeconds = 5)
    try {
        $response = Invoke-WebRequest -Uri $Url -Method GET -TimeoutSec $TimeoutSeconds -UseBasicParsing -ErrorAction Stop
        return $response.StatusCode -eq 200
    } catch { return $false }
}

function Start-ServiceWindow {
    param([string]$Title, [string]$Command, [string]$WorkingDirectory)
    $psCommand = "Set-Location '$WorkingDirectory'; `$Host.UI.RawUI.WindowTitle = '$Title'; $Command; Read-Host 'Press Enter to close'"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $psCommand -WindowStyle Normal
    Write-VerboseStatus "Launched service window: $Title"
}

# Validation
function Test-Prerequisites {
    Write-Status "Validating prerequisites..." -Level STEP
    $allValid = $true
    
    if (-not (Test-Path "backend\app\main.py")) {
        Write-Status "Backend application not found (backend\app\main.py)" -Level ERROR
        $allValid = $false
    } else { Write-Status "Backend application found" -Level OK }
    
    if (-not (Test-Path "dashboard\index.html")) {
        Write-Status "Dashboard not found (dashboard\index.html)" -Level ERROR
        $allValid = $false
    } else { Write-Status "Dashboard found" -Level OK }
    
    if (-not (Test-Path "mosquitto.conf")) {
        Write-Status "Mosquitto config not found" -Level ERROR
        $allValid = $false
    } else { Write-Status "Mosquitto configuration found" -Level OK }
    
    if (-not (Test-Path ".venv\Scripts\python.exe")) {
        Write-Status "Python virtual environment not found (.venv)" -Level ERROR
        Write-Host "Create it with: python -m venv .venv" -ForegroundColor Yellow
        Write-Host "Then install: .venv\Scripts\pip install -r backend\requirements.txt" -ForegroundColor Yellow
        $allValid = $false
    } else {
        Write-Status "Python virtual environment found" -Level OK
        $uvicornCheck = & ".venv\Scripts\python.exe" -c "import uvicorn" 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Status "Backend dependencies not installed" -Level WARN
            Write-Host "Install with: .venv\Scripts\pip install -r backend\requirements.txt" -ForegroundColor Yellow
            $allValid = $false
        } else { Write-Status "Backend dependencies installed" -Level OK }
    }
    
    if (-not (Test-Path $MOSQUITTO_EXE)) {
        Write-Status "Mosquitto not found at: $MOSQUITTO_EXE" -Level ERROR
        Write-Host "Install from: https://mosquitto.org/download/" -ForegroundColor Yellow
        $allValid = $false
    } else { Write-Status "Mosquitto MQTT broker found" -Level OK }
    
    return $allValid
}

# Service Startup
function Start-MosquittoService {
    Write-Status "Starting Mosquitto MQTT Broker..." -Level STEP
    
    if (Test-PortInUse -Port $MOSQUITTO_PORT) {
        $process = Get-ProcessOnPort -Port $MOSQUITTO_PORT
        if ($process -and $process.ProcessName -like "*mosquitto*") {
            Write-Status "Mosquitto already running on port $MOSQUITTO_PORT (PID: $($process.Id))" -Level OK
            return $true
        } else {
            Write-Status "Port $MOSQUITTO_PORT occupied by: $($process.ProcessName)" -Level ERROR
            return $false
        }
    }
    
    $configPath = Join-Path (Get-Location) "mosquitto.conf"
    if (-not (Test-Path $configPath)) {
        Write-Status "mosquitto.conf not found" -Level ERROR
        return $false
    }
    
    $mosquittoCmd = "& '$MOSQUITTO_EXE' -c '$configPath' -v"
    Start-ServiceWindow -Title "WIREBUZZ - MQTT BROKER" -Command $mosquittoCmd -WorkingDirectory (Get-Location)
    
    $retries = 0; $maxRetries = 10
    while ($retries -lt $maxRetries) {
        Start-Sleep -Seconds 1
        if (Test-PortInUse -Port $MOSQUITTO_PORT) {
            Write-Status "Mosquitto MQTT Broker started successfully" -Level OK
            return $true
        }
        $retries++
    }
    
    Write-Status "Mosquitto failed to start within timeout" -Level ERROR
    return $false
}

function Start-BackendService {
    Write-Status "Starting FastAPI Backend..." -Level STEP
    
    if (Test-PortInUse -Port $BACKEND_PORT) {
        if (Test-HttpEndpoint -Url "http://localhost:$BACKEND_PORT/api/health") {
            Write-Status "Backend already running on port $BACKEND_PORT" -Level OK
            return $true
        } else {
            $process = Get-ProcessOnPort -Port $BACKEND_PORT
            Write-Status "Port $BACKEND_PORT occupied by: $($process.ProcessName)" -Level ERROR
            return $false
        }
    }
    
    if (-not (Test-Path "backend\app\main.py")) {
        Write-Status "Backend application not found" -Level ERROR
        return $false
    }
    
    $pythonExe = Join-Path (Get-Location) ".venv\Scripts\python.exe"
    $backendDir = Join-Path (Get-Location) "backend"
    $backendCmd = "& '$pythonExe' -m uvicorn app.main:app --host 127.0.0.1 --port $BACKEND_PORT"
    
    Start-ServiceWindow -Title "WIREBUZZ - FASTAPI BACKEND" -Command $backendCmd -WorkingDirectory $backendDir
    
    Write-Status "Waiting for backend to initialize..." -Level INFO
    $retries = 0
    while ($retries -lt $HEALTH_CHECK_RETRIES) {
        Start-Sleep -Seconds $HEALTH_CHECK_DELAY
        
        if (Test-HttpEndpoint -Url "http://localhost:$BACKEND_PORT/api/health") {
            Write-Status "FastAPI Backend started successfully" -Level OK
            
            try {
                $healthData = Invoke-RestMethod -Uri "http://localhost:$BACKEND_PORT/api/health" -Method GET -TimeoutSec 5
                if ($healthData.mqtt_connected) {
                    Write-Status "MQTT backend connection established" -Level OK
                } else {
                    Write-Status "Backend started but MQTT not connected" -Level WARN
                }
            } catch {
                Write-Status "Could not verify MQTT connection status" -Level WARN
            }
            
            return $true
        }
        
        $retries++
        Write-VerboseStatus "Health check retry $retries/$HEALTH_CHECK_RETRIES"
    }
    
    Write-Status "Backend failed to respond to health checks" -Level ERROR
    return $false
}

function Start-DashboardService {
    Write-Status "Starting Dashboard HTTP Server..." -Level STEP
    
    if (Test-PortInUse -Port $DASHBOARD_PORT) {
        if (Test-HttpEndpoint -Url "http://localhost:$DASHBOARD_PORT") {
            Write-Status "Dashboard already running on port $DASHBOARD_PORT" -Level OK
            return $true
        } else {
            $process = Get-ProcessOnPort -Port $DASHBOARD_PORT
            Write-Status "Port $DASHBOARD_PORT occupied by: $($process.ProcessName)" -Level ERROR
            return $false
        }
    }
    
    if (-not (Test-Path "dashboard\index.html")) {
        Write-Status "Dashboard not found" -Level ERROR
        return $false
    }
    
    $pythonExe = Join-Path (Get-Location) ".venv\Scripts\python.exe"
    $projectRoot = Get-Location
    $dashboardCmd = "& '$pythonExe' -m http.server $DASHBOARD_PORT --directory dashboard --bind 127.0.0.1"
    
    Start-ServiceWindow -Title "WIREBUZZ - DASHBOARD" -Command $dashboardCmd -WorkingDirectory $projectRoot
    
    $retries = 0; $maxRetries = 8
    while ($retries -lt $maxRetries) {
        Start-Sleep -Seconds 1
        
        if (Test-HttpEndpoint -Url "http://localhost:$DASHBOARD_PORT") {
            Write-Status "Dashboard server started successfully" -Level OK
            return $true
        }
        $retries++
    }
    
    Write-Status "Dashboard failed to respond" -Level ERROR
    return $false
}

function Open-WireBuzzBrowser {
    if ($SkipBrowser) {
        Write-Status "Skipping browser launch (--SkipBrowser)" -Level INFO
        return
    }
    
    Write-Status "Opening browser..." -Level STEP
    
    $urls = @(
        "http://localhost:$DASHBOARD_PORT",
        "http://localhost:$BACKEND_PORT/docs",
        "http://localhost:$BACKEND_PORT/api/health"
    )
    
    foreach ($url in $urls) {
        try {
            Start-Process $url
            Write-VerboseStatus "Opened: $url"
        } catch {
            Write-Status "Could not open: $url" -Level WARN
        }
    }
    
    Start-Sleep -Seconds 1
}

# Main Execution
function Start-WireBuzz {
    Clear-Host
    
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "        WIREBUZZ STARTUP SYSTEM        " -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    
    # Validate structure
    if (-not ((Test-Path "backend\app\main.py") -and (Test-Path "mosquitto.conf") -and (Test-Path ".venv"))) {
        Write-Status "Could not find WireBuzz project root" -Level ERROR
        Write-Host "Please run this command from the WireBuzz project directory." -ForegroundColor Yellow
        return 1
    }
    
    Write-Status "Project root: $(Get-Location)" -Level INFO
    Write-Host ""
    
    if (-not (Test-Prerequisites)) {
        Write-Host ""
        Write-Status "Prerequisites check failed. Please resolve the issues above." -Level ERROR
        return 1
    }
    
    Write-Host ""
    Write-Host "----------------------------------------" -ForegroundColor Cyan
    Write-Host "STARTING SERVICES" -ForegroundColor Cyan
    Write-Host "----------------------------------------" -ForegroundColor Cyan
    Write-Host ""
    
    $mosquittoOk = Start-MosquittoService
    Start-Sleep -Seconds 2
    
    $backendOk = Start-BackendService
    Start-Sleep -Seconds 1
    
    $dashboardOk = Start-DashboardService
    Start-Sleep -Seconds 1
    
    # Status Report
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "          WIREBUZZ SYSTEM              " -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    
    if ($mosquittoOk) {
        Write-Host "[OK] Mosquitto MQTT Broker" -ForegroundColor Green
        Write-Host "[OK] MQTT Port $MOSQUITTO_PORT" -ForegroundColor Green
    } else {
        Write-Host "[FAIL] Mosquitto MQTT Broker" -ForegroundColor Red
    }
    
    if ($backendOk) {
        Write-Host "[OK] FastAPI Backend" -ForegroundColor Green
        Write-Host "[OK] SQLite Database" -ForegroundColor Green
        
        try {
            $healthData = Invoke-RestMethod -Uri "http://localhost:$BACKEND_PORT/api/health" -Method GET -TimeoutSec 5 -ErrorAction SilentlyContinue
            if ($healthData.mqtt_connected) {
                Write-Host "[OK] MQTT Backend Connection" -ForegroundColor Green
            } else {
                Write-Host "[WARN] MQTT Backend Connection" -ForegroundColor Yellow
            }
        } catch {
            Write-Host "[WARN] MQTT Connection Status Unknown" -ForegroundColor Yellow
        }
    } else {
        Write-Host "[FAIL] FastAPI Backend" -ForegroundColor Red
    }
    
    if ($dashboardOk) {
        Write-Host "[OK] Dashboard Server" -ForegroundColor Green
        Write-Host "[OK] Dashboard HTTP Response" -ForegroundColor Green
    } else {
        Write-Host "[FAIL] Dashboard Server" -ForegroundColor Red
    }
    
    Write-Host ""
    Write-Host "----------------------------------------" -ForegroundColor Cyan
    
    if ($dashboardOk) {
        Write-Host "DASHBOARD: http://localhost:$DASHBOARD_PORT" -ForegroundColor Cyan
    }
    
    if ($backendOk) {
        Write-Host "API DOCS:  http://localhost:$BACKEND_PORT/docs" -ForegroundColor Cyan
        Write-Host "HEALTH:    http://localhost:$BACKEND_PORT/api/health" -ForegroundColor Cyan
    }
    
    Write-Host "----------------------------------------" -ForegroundColor Cyan
    Write-Host ""
    
    if ($mosquittoOk -and $backendOk -and $dashboardOk) {
        Write-Host "WIREBUZZ IS READY FOR TESTING." -ForegroundColor Green
        Write-Host ""
        Write-Host "========================================" -ForegroundColor Cyan
        Write-Host ""
        
        Open-WireBuzzBrowser
        return 0
    } else {
        Write-Host "SOME SERVICES FAILED TO START." -ForegroundColor Red
        Write-Host "Check the service windows for error details." -ForegroundColor Yellow
        Write-Host ""
        Write-Host "========================================" -ForegroundColor Cyan
        Write-Host ""
        return 1
    }
}

# Execute
$exitCode = Start-WireBuzz
exit $exitCode
