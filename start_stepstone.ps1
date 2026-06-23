# Start local Stepstone MCP server
# Usage: .\start_stepstone.ps1
# Required: C:\tools\mcp-stepstone\ must exist

$StepstoneDir = "C:\tools\mcp-stepstone"
$Port = 8765

if (-not (Test-Path $StepstoneDir)) {
    Write-Error "Stepstone directory not found: $StepstoneDir"
    exit 1
}

# Check if already running
$running = netstat -ano | Select-String ":$Port\s.*LISTENING"
if ($running) {
    Write-Host "Stepstone already running on port $Port"
    exit 0
}

Write-Host "Starting Stepstone server on port $Port..."
Set-Location $StepstoneDir
Start-Process python -ArgumentList "-m stepstone_http_server" -WorkingDirectory $StepstoneDir -WindowStyle Minimized
Start-Sleep 2

$check = netstat -ano | Select-String ":$Port\s.*LISTENING"
if ($check) {
    Write-Host "Stepstone started OK (port $Port)"
} else {
    Write-Warning "Stepstone may not have started — check $StepstoneDir for errors"
}
