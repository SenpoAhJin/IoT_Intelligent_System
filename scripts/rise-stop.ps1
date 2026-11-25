# AquaBuzz RISE-STOP - Clean Shutdown System
# PowerShell 5.1+ Compatible
# Safely stops only AquaBuzz services

$ErrorActionPreference = 'Stop'

# ============================================
# CONFIGURATION
# ============================================

$script:PROJECT_ROOT = (Get-Item $PSScriptRoot).Parent.FullName
$script:PROCESS_TRACKER = Join-Path $PROJECT_ROOT '.aquabuzz-processes.json'

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
        'SKIP' { 'Magenta' }
        default { 'White' }
    }
    
    Write-Host "[$Status] $Message" -ForegroundColor $color
    if ($Detail) {
        Write-Host "  $Detail" -ForegroundColor Gray
    }
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

function Test-IsProtectedProcess {
    param([int]$ProcessId)
    
    $cmdLine = Get-ProcessCommandLine -ProcessId $ProcessId
    if (-not $cmdLine) {
        return $false
    }
    
    # Check for ForgeMind and other protected processes
    if ($cmdLine -like '*arise*' -or $cmdLine -like '*rest*' -or $cmdLine -like '*ForgeMind*') {
        return $true
    }
    
    return $false
}

function Test-IsAquaBuzzProcess {
    param([int]$ProcessId, [string]$ServiceName)
    
    $cmdLine = Get-ProcessCommandLine -ProcessId $ProcessId
    if (-not $cmdLine) {
        return $false
    }
    
    # Reject protected processes
    if (Test-IsProtectedProcess -ProcessId $ProcessId) {
        return $false
    }
    
    # Check for AquaBuzz identifiers
    switch ($ServiceName) {
        'backend' {
            return $cmdLine -like '*uvicorn*app.main:app*'
        }
        'gateway' {
            return $cmdLine -like '*serial_gateway.py*'
        }
        'dashboard' {
            # Check for http.server running in dashboard directory or on expected ports
            if ($cmdLine -like '*http.server*') {
                # Additional check: port or working directory
                return $true
            }
            return $false
        }
        default {
            # Generic check for Python processes
            return $cmdLine -like '*python*' -and (
                $cmdLine -like '*aquabuzz*' -or
                $cmdLine -like '*serial_gateway*' -or
                $cmdLine -like '*uvicorn*'
            )
        }
    }
}

function Stop-ServiceProcess {
    param(
        [string]$ServiceName,
        [int]$ProcessId,
        [int]$Port = 0
    )
    
    Write-Step "Stopping $ServiceName" 'INFO' "PID: $ProcessId, Port: $Port"
    
    # Check if process exists
    try {
        $process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    } catch {
        $process = $null
    }
    
    if (-not $process) {
        Write-Step "$ServiceName already stopped" 'OK'
        return $true
    }
    
    # Verify it's not a protected process
    if (Test-IsProtectedProcess -ProcessId $ProcessId) {
        Write-Step "$ServiceName is a protected process" 'SKIP' 'Will not terminate ForgeMind or other protected processes'
        return $false
    }
    
    # Verify it's an AquaBuzz process
    if (-not (Test-IsAquaBuzzProcess -ProcessId $ProcessId -ServiceName $ServiceName)) {
        Write-Step "$ServiceName does not appear to be an AquaBuzz process" 'SKIP' "Process: $($process.ProcessName)"
        return $false
    }
    
    # Stop the process
    try {
        Stop-Process -Id $ProcessId -Force -ErrorAction Stop
        Start-Sleep -Milliseconds 500
        
        # Verify it stopped
        $stillRunning = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
        if (-not $stillRunning) {
            Write-Step "$ServiceName stopped successfully" 'OK'
            return $true
        } else {
            Write-Step "$ServiceName failed to stop" 'WARN' 'Process still running'
            return $false
        }
    } catch {
        Write-Step "Error stopping $ServiceName" 'FAIL' $_.Exception.Message
        return $false
    }
}

function Get-PortStatus {
    param([int]$Port)
    
    if ($Port -eq 0) {
        return 'N/A'
    }
    
    try {
        $listener = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Loopback, $Port)
        $listener.Start()
        $listener.Stop()
        return 'Free'
    } catch {
        return 'In Use'
    }
}

# ============================================
# MAIN EXECUTION
# ============================================

function Stop-AquaBuzz {
    Write-Section 'AQUABUZZ SHUTDOWN SYSTEM' 'Cyan'
    
    # Check if tracker file exists
    if (-not (Test-Path $script:PROCESS_TRACKER)) {
        Write-Step 'No process tracker found' 'INFO'
        Write-Step 'No services to stop' 'OK'
        Write-Host ''
        return
    }
    
    # Load process tracker
    Write-Step 'Loading process tracker' 'INFO'
    
    try {
        $content = Get-Content $script:PROCESS_TRACKER -Raw
        $processes = $content | ConvertFrom-Json
        
        # Convert to hashtable for PowerShell 5.1 compatibility
        $processesHash = @{}
        foreach ($prop in $processes.PSObject.Properties) {
            $processesHash[$prop.Name] = @{
                pid = $prop.Value.pid
                port = $prop.Value.port
                url = $prop.Value.url
                started_at = $prop.Value.started_at
            }
        }
    } catch {
        Write-Step 'Error reading process tracker' 'FAIL' $_.Exception.Message
        Write-Host ''
        return
    }
    
    Write-Host ''
    
    # Stop services in reverse order (dashboard, gateway, backend)
    $serviceOrder = @('dashboard', 'gateway', 'backend')
    
    $stoppedCount = 0
    $notFoundCount = 0
    $skippedCount = 0
    $failedCount = 0
    
    foreach ($serviceName in $serviceOrder) {
        if ($processesHash.ContainsKey($serviceName)) {
            $info = $processesHash[$serviceName]
            $processId = $info.pid
            $port = if ($info.port) { [int]$info.port } else { 0 }
            
            $result = Stop-ServiceProcess -ServiceName $serviceName -ProcessId $processId -Port $port
            
            if ($result) {
                $stoppedCount++
            } else {
                $processExists = Get-Process -Id $processId -ErrorAction SilentlyContinue
                if (-not $processExists) {
                    $notFoundCount++
                } else {
                    $isProtected = Test-IsProtectedProcess -ProcessId $processId
                    if ($isProtected) {
                        $skippedCount++
                    } else {
                        $failedCount++
                    }
                }
            }
            
            Write-Host ''
        }
    }
    
    # Verify ports are released
    Write-Step 'Verifying port status' 'INFO'
    
    $portsToCheck = @(
        @{ Name = 'Backend API'; Port = 8000 }
        @{ Name = 'Dashboard'; Port = 3000 }
    )
    
    foreach ($portInfo in $portsToCheck) {
        $status = Get-PortStatus -Port $portInfo.Port
        if ($status -eq 'Free') {
            Write-Step "$($portInfo.Name) (Port $($portInfo.Port))" 'OK' 'Free'
        } else {
            Write-Step "$($portInfo.Name) (Port $($portInfo.Port))" 'WARN' 'Still in use'
        }
    }
    
    Write-Host ''
    
    # Remove process tracker
    Write-Step 'Removing process tracker' 'INFO'
    try {
        Remove-Item -Path $script:PROCESS_TRACKER -Force -ErrorAction Stop
        Write-Step 'Process tracker removed' 'OK'
    } catch {
        Write-Step 'Failed to remove process tracker' 'WARN' $_.Exception.Message
    }
    
    Write-Host ''
    
    # Summary
    Write-Section 'SHUTDOWN COMPLETE' 'Green'
    
    Write-Host 'Summary:' -ForegroundColor Cyan
    Write-Host ''
    Write-Host "  Services stopped:  $stoppedCount" -ForegroundColor Green
    
    if ($notFoundCount -gt 0) {
        Write-Host "  Already stopped:   $notFoundCount" -ForegroundColor Yellow
    }
    
    if ($skippedCount -gt 0) {
        Write-Host "  Skipped (protected): $skippedCount" -ForegroundColor Magenta
    }
    
    if ($failedCount -gt 0) {
        Write-Host "  Failed to stop:    $failedCount" -ForegroundColor Red
    }
    
    Write-Host ''
    
    Write-Host 'Notes:' -ForegroundColor Cyan
    Write-Host '  - ESP32 device (if connected) remains active' -ForegroundColor Gray
    Write-Host '  - ForgeMind processes (arise/rest) were not affected' -ForegroundColor Gray
    Write-Host '  - To restart: run "rise"' -ForegroundColor Gray
    Write-Host ''
    
    if ($failedCount -gt 0) {
        Write-Host 'Some services failed to stop. You may need to manually terminate them.' -ForegroundColor Yellow
        Write-Host ''
    }
}

# Run the shutdown
Stop-AquaBuzz
