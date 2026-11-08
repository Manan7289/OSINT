# scripts/start.ps1 - PowerShell Workstation Launcher for LocalOSINT v2.0
[CmdletBinding()]
param()

$pythonExe = if (Test-Path ".venv\Scripts\python.exe") { ".venv\Scripts\python.exe" } else { "python" }

Write-Host "===============================================================================" -ForegroundColor Cyan
Write-Host "Starting LocalOSINT v2.0 Workstation on http://127.0.0.1:8000" -ForegroundColor Cyan
Write-Host "===============================================================================" -ForegroundColor Cyan

# Open browser after 2 seconds in background
Start-Job -ScriptBlock {
    Start-Sleep -Seconds 2
    Start-Process "http://127.0.0.1:8000"
} | Out-Null

# Run server
& $pythonExe run.py
