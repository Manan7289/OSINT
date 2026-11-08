@echo off
setlocal
title Stop LocalOSINT v2.0

echo ===============================================================================
echo Stopping LocalOSINT v2.0 Processes
echo ===============================================================================
echo.

echo Finding and terminating running LocalOSINT instances on port 8000...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING') do (
    echo Terminating PID: %%a
    taskkill /F /PID %%a >nul 2>&1
)

echo [OK] All LocalOSINT instances terminated.
timeout /t 2 /nobreak >nul
