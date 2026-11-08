@echo off
setlocal enabledelayedexpansion
title LocalOSINT v3.0 - Automated Windows 11 Installer

echo ===============================================================================
echo LocalOSINT v3.0 -- Global Intelligence Command Centre Installer
echo Target OS: Windows 11 (64-bit) ^| CPU-Only Architecture
echo ===============================================================================
echo.

:: 1. Check for Python 3.10+
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not found in system PATH.
    echo Please install Python 3.10, 3.11, or 3.12 from python.org or Microsoft Store.
    pause
    exit /b 1
)

for /f "tokens=2 delims= " %%v in ('python --version') do set PY_VER=%%v
echo [OK] Detected Python version: %PY_VER%

:: 2. Create Virtual Environment if not exists
if not exist ".venv" (
    echo [INFO] Creating isolated virtual environment in .venv ...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created successfully.
) else (
    echo [OK] Existing virtual environment found in .venv.
)

:: 3. Activate and upgrade pip
call .venv\Scripts\activate.bat
echo [INFO] Upgrading pip, setuptools, and wheel ...
python -m pip install --upgrade pip setuptools wheel --quiet

:: 4. Install dependencies from requirements.txt
echo [INFO] Installing required dependencies from requirements.txt ...
python -m pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [WARNING] Failed to install all dependencies quietly, retrying with verbose output ...
    python -m pip install -r requirements.txt
)

:: 5. Create default environment configuration if not exists
if not exist ".env" (
    echo [INFO] Generating default .env configuration file ...
    if exist ".env.example" (
        copy .env.example .env >nul
    ) else (
        echo # LocalOSINT v3.0 Runtime Environment Configuration > .env
        echo HOST=127.0.0.1 >> .env
        echo PORT=8000 >> .env
        echo OPSEC_MODE=STANDARD >> .env
        echo OFFLINE_MODE=false >> .env
        echo AI_PROVIDER=local_graphrag >> .env
        echo LOG_LEVEL=INFO >> .env
    )
    echo [OK] .env configuration file initialized.
)

:: 6. Initialize SQLite Database & Seeding
echo [INFO] Initializing SQLite WAL schema, sanctions index and demonstration case ...
python -c "from backend.core.database import db; db.init_db(); from backend.collectors.sanctions_loader import sanctions_loader; sanctions_loader.load_sanctions(); from backend.main import seed_demo_workspace_if_empty; seed_demo_workspace_if_empty(); print('[OK] Database schema initialized and demonstration case verified.')"

echo.
echo ===============================================================================
echo [SUCCESS] LocalOSINT v3.0 installation completed successfully!
echo To start the platform workstation: double-click start.bat
echo Web UI will be accessible at: http://127.0.0.1:8000
echo ===============================================================================
echo.
pause
