# ========================================
#       WIREBUZZ SHUTDOWN SYSTEM
# ========================================
# Gracefully stops WireBuzz services
# Command: rise-stop
# ========================================

$ErrorActionPreference = "Stop"

$PROJECT_ROOT = "c:\Users\Alord\OneDrive\Documents\School\COSC 105 - Ma'am Mikae\Intelligent_System_IS"
$PROCESS_TRACKER = Join-Path $PROJECT_ROOT ".wirebuzz-processes.json"

function Write-Status {
    param([string]$Message, [string]$Status = "INFO")
    
    $timestamp = Get-Date -Format "HH:mm:ss"
    switch ($Status) {
        "OK"      { Write-Host "[$timestamp] " -NoNewline; Write-Host "[OK]      " -ForegroundColor Green -NoNewline; Write-Host $Message }
        "FAILED"  { Write-Host "[$timestamp] " -NoNewline; Write-Host "[FAILED]  " -ForegroundColor Red -NoNewline; Write-Host $Message }
        "WARNING" { Write-Host "[$timestamp] " -NoNewline; Write-Host "[WARNING] " -ForegroundColor Yellow -NoNewline; Write-Host $Message }
        "INFO"    { Write-Host "[$timestamp] " -NoNewline; Write-Host "[INFO]    " -ForegroundColor Cyan -NoNewline; Write-Host $Message }
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

Write-Header "WIREBUZZ SHUTDOWN"

# Check if process tracker exists
if (-not (Test-Path $PROCESS_TRACKER)) {
    Write-Status "No process tracker found. No WireBuzz services to stop." "WARNING"
    Write-Status "Either services were not started with 'rise', or they were already stopped." "INFO"
    exit 0
}

# Load tracked processes
Write-Status "Loading tracked processes..." "INFO"
$processes = Get-Content $PROCESS_TRACKER | ConvertFrom-Json

$stoppedCount = 0
$notFoundCount = 0
$failedCount = 0

# Stop each service
foreach ($serviceName in $processes.PSObject.Properties.Name) {
    $service = $processes.$serviceName
    $pid = $service.pid
    $port = $service.port
    
    Write-Host ""
    Write-Status "Stopping $serviceName (PID: $pid, Port: $port)..." "INFO"
    
    # Check if process still exists
    try {
        $process = Get-Process -Id $pid -ErrorAction SilentlyContinue
        
        if ($process) {
            # Verify the process is actually using the expected port (safety check)
            $portOwner = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | 
                         Where-Object { $_.OwningProcess -eq $pid } | 
                         Select-Object -First 1
            
            if ($portOwner) {
                Write-Status "Confirmed process $pid owns port $port, stopping..." "INFO"
                Stop-Process -Id $pid -Force
                Start-Sleep -Seconds 1
                
                # Verify it stopped
                $stillRunning = Get-Process -Id $pid -ErrorAction SilentlyContinue
                if ($stillRunning) {
                    Write-Status "Process $pid did not stop gracefully" "WARNING"
                    $failedCount++
                } else {
                    Write-Status "$serviceName stopped successfully" "OK"
                    $stoppedCount++
                }
            } else {
                Write-Status "Process $pid exists but doesn't own port $port (may have been replaced)" "WARNING"
                Write-Status "Skipping for safety - not stopping unrelated process" "WARNING"
                $notFoundCount++
            }
        } else {
            Write-Status "Process $pid no longer exists (already stopped)" "INFO"
            $notFoundCount++
        }
    } catch {
        Write-Status "Error checking/stopping process $pid : $_" "FAILED"
        $failedCount++
    }
}

# Remove process tracker
Write-Host ""
Write-Status "Removing process tracker..." "INFO"
Remove-Item $PROCESS_TRACKER -Force
Write-Status "Process tracker removed" "OK"

# Summary
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "          SHUTDOWN SUMMARY" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Services stopped:        " -NoNewline; Write-Host $stoppedCount -ForegroundColor Green
Write-Host "Already stopped/gone:    " -NoNewline; Write-Host $notFoundCount -ForegroundColor Yellow
Write-Host "Failed to stop:          " -NoNewline; Write-Host $failedCount -ForegroundColor Red
Write-Host ""

if ($stoppedCount -gt 0) {
    Write-Host "WireBuzz services have been stopped." -ForegroundColor Green
} elseif ($notFoundCount -gt 0) {
    Write-Host "No running WireBuzz services found." -ForegroundColor Yellow
}

if ($failedCount -gt 0) {
    Write-Host "Some services failed to stop. Check Task Manager manually." -ForegroundColor Red
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
