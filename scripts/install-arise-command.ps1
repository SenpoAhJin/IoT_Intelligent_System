# WIREBUZZ ARISE COMMAND INSTALLER

$ErrorActionPreference = "Stop"

$WIREBUZZ_PROJECT_DIR = "C:\Users\Alord\OneDrive\Documents\School\COSC 105 - Ma'am Mikae\Intelligent_System_IS"
$ARISE_SCRIPT = Join-Path $WIREBUZZ_PROJECT_DIR "scripts\arise.ps1"

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  WIREBUZZ ARISE COMMAND INSTALLER" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path $ARISE_SCRIPT)) {
    Write-Host "[ERROR] arise.ps1 not found" -ForegroundColor Red
    exit 1
}

Write-Host "[OK] Found arise.ps1" -ForegroundColor Green
Write-Host ""

$profilePath = $PROFILE.CurrentUserAllHosts
if (-not $profilePath) { $profilePath = $PROFILE }

Write-Host "PowerShell Profile: $profilePath" -ForegroundColor Cyan
Write-Host ""

$profileDir = Split-Path -Parent $profilePath
if (-not (Test-Path $profileDir)) {
    New-Item -ItemType Directory -Path $profileDir -Force | Out-Null
}

if (-not (Test-Path $profilePath)) {
    New-Item -ItemType File -Path $profilePath -Force | Out-Null
    Write-Host "[OK] Profile created" -ForegroundColor Green
} else {
    Write-Host "[i] Profile exists" -ForegroundColor Gray
}

$escapedPath = $ARISE_SCRIPT -replace '\\', '\\\\'

$functionText = "`n# WIREBUZZ ARISE COMMAND`nfunction arise {`n    param([switch]`$SkipBrowser, [switch]`$Verbose)`n    `$script = `"$escapedPath`"`n    if (Test-Path `$script) { & `$script @PSBoundParameters } else { Write-Host `"arise.ps1 not found`" -ForegroundColor Red }`n}`n"

Add-Content -Path $profilePath -Value $functionText

Write-Host "[OK] arise function added" -ForegroundColor Green
Write-Host ""
Write-Host "To use in THIS terminal: . `$PROFILE" -ForegroundColor Yellow
Write-Host "To use in NEW terminals: Just open a new PowerShell" -ForegroundColor Yellow
Write-Host ""
