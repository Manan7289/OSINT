# scripts/install.ps1 - PowerShell Automated Installer for LocalOSINT v2.0
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

Write-Host "===============================================================================" -ForegroundColor Cyan
Write-Host "LocalOSINT v2.0 -- PowerShell Automated Installer for Windows 11" -ForegroundColor Cyan
Write-Host "===============================================================================" -ForegroundColor Cyan

# 1. Verify Python
try {
    $pythonVersion = (python --version 2>&1).ToString()
    Write-Host "[OK] Detected: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Error "[ERROR] Python 3.10+ is required but not found in system PATH."
}

# 2. Virtual Environment
if (-not (Test-Path ".venv")) {
    Write-Host "[INFO] Creating virtual environment in .venv ..." -ForegroundColor Yellow
    python -m venv .venv
    Write-Host "[OK] Virtual environment created." -ForegroundColor Green
} else {
    Write-Host "[OK] Existing virtual environment found." -ForegroundColor Green
}

# 3. Pip Upgrade & Dependencies
$pythonExe = if (Test-Path ".venv\Scripts\python.exe") { ".venv\Scripts\python.exe" } else { "python" }

Write-Host "[INFO] Upgrading pip and build tools ..." -ForegroundColor Yellow
& $pythonExe -m pip install --upgrade pip setuptools wheel --quiet

Write-Host "[INFO] Installing requirements from requirements.txt ..." -ForegroundColor Yellow
& $pythonExe -m pip install -r requirements.txt --quiet

# 4. Default Environment File
if (-not (Test-Path ".env")) {
    Write-Host "[INFO] Creating default .env configuration file ..." -ForegroundColor Yellow
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
    } else {
        @"
HOST=127.0.0.1
PORT=8000
OPSEC_MODE=STANDARD
OFFLINE_MODE=false
AI_PROVIDER=local_graphrag
LOG_LEVEL=INFO
"@ | Out-File -FilePath ".env" -Encoding utf8
    }
    Write-Host "[OK] .env configuration file created." -ForegroundColor Green
}

# 5. Initialize Database
Write-Host "[INFO] Initializing SQLite database schema and demonstration case ..." -ForegroundColor Yellow
& $pythonExe -c "from backend.core.database import db; db.init_db(); from backend.main import seed_demo_workspace_if_empty; seed_demo_workspace_if_empty(); print('[OK] Database and demo case initialized.')"

Write-Host ""
Write-Host "===============================================================================" -ForegroundColor Cyan
Write-Host "[SUCCESS] Installation Complete! Run .\scripts\start.ps1 to launch workstation." -ForegroundColor Green
Write-Host "===============================================================================" -ForegroundColor Cyan
