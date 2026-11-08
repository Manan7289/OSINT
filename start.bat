@echo off
setlocal
title LocalOSINT v2.0 - Workstation Server

echo ===============================================================================
echo Starting LocalOSINT v2.0 Intelligence Workstation Server
echo Target: http://127.0.0.1:8000
echo ===============================================================================
echo.

if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

:: Launch browser after short delay in background
start "" cmd /c "timeout /t 3 /nobreak >nul & start http://127.0.0.1:8000"

:: Start Uvicorn Server
python run.py

pause
