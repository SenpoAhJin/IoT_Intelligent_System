# AquaBuzz Shutdown Script - Public MQTT Edition
# PowerShell 5.1 Compatible
# Stops only AquaBuzz services tracked in .aquabuzz-processes.json

$ErrorActionPreference = 'Stop'

# Configuration - Dynamically determine project root
$script:PROJECT_ROOT = (Get-Item $PSScriptRoot).Parent.FullName
$script:PROCESS_TRACKER = Join-Path $PROJECT_ROOT '.aquabuzz-processes.json'

function Test-IsForgeMindProcess {
    param([int]$ProcessId)
    
    try {
        $proc = Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId" -ErrorAction SilentlyContinue
        if ($proc -and $proc.CommandLine) {
            # Check for ForgeMind identifiers
            if ($proc.CommandLine -like '*arise*' -or $proc.CommandLine -like '*rest*' -or $proc.CommandLine -like '*ForgeMind*') {
                return $true
            }
        }
    } catch {
        return $false
    }
    return $false
}

function Test-IsAquaBuzzProcess {
    param([int]$ProcessId, [string]$ServiceName)
    
    try {
        $proc = Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId" -ErrorAction SilentlyContinue
        if (-not $proc) {
            return $false
        }
        
        $processName = $proc.Name
        $commandLine = $proc.CommandLine
        
        # AquaBuzz processes are Python (backend/gateway) or PowerShell (dashboard server)
        if ($processName -match 'python|powershell') {
            # Additional verification for specific services
            if ($ServiceName -eq 'backend' -and $commandLine -like '*uvicorn*app.main:app*') {
                return $true
            }
            if ($ServiceName -eq 'gateway' -and $commandLine -like '*serial_gateway.py*') {
                return $true
            }
            if ($ServiceName -eq 'dashboard' -and $commandLine -like '*http.server*') {
                return $true
            }
            
            # Generic Python/PowerShell process, might be AquaBuzz
            return $true
        }
        
        return $false
    } catch {
        return $false
    }
}

function Stop-AquaBuzzProcesses {
    Write-Host ''
    Write-Host '==================================================' -ForegroundColor Cyan
    Write-Host '    AquaBuzz Shutdown System' -ForegroundColor Cyan
    Write-Host '==================================================' -ForegroundColor Cyan
    Write-Host ''
    
    if (-not (Test-Path $script:PROCESS_TRACKER)) {
        Write-Host 'No AquaBuzz process tracker found.' -ForegroundColor Yellow
        Write-Host 'Nothing to stop.' -ForegroundColor Yellow
        Write-Host ''
        return
    }
    
    Write-Host 'Stopping AquaBuzz services...' -ForegroundColor Cyan
    Write-Host ''
    
    try {
        $content = Get-Content $script:PROCESS_TRACKER -Raw
        $processes = $content | ConvertFrom-Json -AsHashtable
    } catch {
        Write-Host 'Error reading process tracker file' -ForegroundColor Red
        Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
        Write-Host ''
        return
    }
    
    $stoppedCount = 0
    $notFoundCount = 0
    $skippedCount = 0
    
    foreach ($service in $processes.Keys) {
        $info = $processes[$service]
        $processId = $info.pid
        $port = if ($info.port) { $info.port } else { 'N/A' }
        
        Write-Host "Stopping $service (PID: $processId, Port: $port)..." -ForegroundColor Cyan
        
        try {
            # Check if process still exists
            $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
            
            if (-not $process) {
                Write-Host "  Process $processId not found (already stopped)" -ForegroundColor Yellow
                $notFoundCount++
                continue
            }
            
            # Verify it's not a ForgeMind process
            if (Test-IsForgeMindProcess -ProcessId $processId) {
                Write-Host "  SKIPPED: ForgeMind process detected - will not terminate" -ForegroundColor Magenta
                $skippedCount++
                continue
            }
            
            # Verify it's an AquaBuzz process
            if (-not (Test-IsAquaBuzzProcess -ProcessId $processId -ServiceName $service)) {
                Write-Host "  SKIPPED: Not an AquaBuzz process ($($process.ProcessName))" -ForegroundColor Yellow
                $skippedCount++
                continue
            }
            
            # Stop the process
            Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
            Start-Sleep -Milliseconds 500
            
            # Verify it stopped
            $stillRunning = Get-Process -Id $processId -ErrorAction SilentlyContinue
            if (-not $stillRunning) {
                Write-Host "  Stopped $service" -ForegroundColor Green
                $stoppedCount++
            } else {
                Write-Host "  Failed to stop $service" -ForegroundColor Red
            }
        } catch {
            Write-Host "  Could not stop process $processId" -ForegroundColor Red
            Write-Host "  Error: $($_.Exception.Message)" -ForegroundColor Red
        }
    }
    
    # Remove process tracker file
    try {
        Remove-Item -Path $script:PROCESS_TRACKER -Force -ErrorAction SilentlyContinue
        Write-Host ''
        Write-Host 'Process tracker file removed' -ForegroundColor Green
    } catch {
        Write-Host ''
        Write-Host 'Warning: Could not remove process tracker file' -ForegroundColor Yellow
    }
    
    Write-Host ''
    Write-Host '==================================================' -ForegroundColor Green
    Write-Host '    Shutdown complete' -ForegroundColor Green
    Write-Host '==================================================' -ForegroundColor Green
    Write-Host ''
    Write-Host 'Summary:' -ForegroundColor Cyan
    Write-Host "  Stopped: $stoppedCount service(s)" -ForegroundColor White
    Write-Host "  Not found: $notFoundCount service(s)" -ForegroundColor White
    if ($skippedCount -gt 0) {
        Write-Host "  Skipped: $skippedCount service(s) (protected or non-AquaBuzz)" -ForegroundColor Magenta
    }
    Write-Host ''
    Write-Host 'Note: ESP32 device remains connected to MQTT broker' -ForegroundColor Yellow
    Write-Host 'Note: ForgeMind processes (arise/rest) were not affected' -ForegroundColor Yellow
    Write-Host ''
}

Stop-AquaBuzzProcesses
