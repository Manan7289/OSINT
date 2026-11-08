# scripts/stop.ps1 - PowerShell Workstation Process Stopper
[CmdletBinding()]
param()

Write-Host "Searching for active processes on port 8000 ..." -ForegroundColor Yellow
$connections = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue

if ($connections) {
    foreach ($conn in $connections) {
        $procId = $conn.OwningProcess
        Write-Host "Stopping process PID: $procId" -ForegroundColor Yellow
        Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
    }
    Write-Host "[OK] LocalOSINT processes stopped." -ForegroundColor Green
} else {
    Write-Host "[INFO] No process listening on port 8000." -ForegroundColor Gray
}
