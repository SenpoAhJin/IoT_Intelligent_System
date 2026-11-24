# Test dynamic path detection
$script:PROJECT_ROOT = (Get-Item $PSScriptRoot).Parent.FullName

Write-Host "PSScriptRoot: $PSScriptRoot" -ForegroundColor Cyan
Write-Host "PROJECT_ROOT: $script:PROJECT_ROOT" -ForegroundColor Cyan

$backendPath = Join-Path $script:PROJECT_ROOT 'backend'
$dashboardPath = Join-Path $script:PROJECT_ROOT 'dashboard'

Write-Host "`nValidation:" -ForegroundColor Yellow
Write-Host "  Backend exists: $(Test-Path $backendPath)" -ForegroundColor White
Write-Host "  Dashboard exists: $(Test-Path $dashboardPath)" -ForegroundColor White
