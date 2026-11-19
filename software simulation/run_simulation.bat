@echo off
title EC261 UAV RF Direction Finding Digital Twin
cls
echo =====================================================================
echo   EC261 -- UAV RF Direction Finding Digital Twin Launcher
echo   IIIT Vadodara - International Campus Diu
echo =====================================================================
echo.

cd /d "%~dp0"

:: Verify Python virtual environment
if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment .venv not found in %~dp0!
    echo Please make sure the Python virtual environment is set up.
    pause
    exit /b 1
)

:: 1. Launch Backend in a separate window
echo [1/2] Starting Python DSP Backend (FastAPI / Uvicorn on http://localhost:8000)...
start "EC261 Backend - FastAPI Server" cmd /k "cd /d "%~dp0" && set PYTHONPATH=. && .venv\Scripts\python.exe -m uvicorn backend.api.main:app --host 0.0.0.0 --port 8000"

:: Wait 2 seconds for backend initialization
timeout /t 2 /nobreak >nul

:: 2. Launch Frontend in a separate window
echo [2/2] Starting Next.js Web Interface on http://localhost:3000...
start "EC261 Frontend - Next.js UI" cmd /k "cd /d "%~dp0frontend" && npm run dev"

:: Wait 3 seconds then open default browser
timeout /t 3 /nobreak >nul
echo.
echo Opening browser at http://localhost:3000 ...
start http://localhost:3000

echo.
echo =====================================================================
echo   Simulation is now active!
echo     - 3D Mission Control: http://localhost:3000
echo     - Backend REST API:   http://localhost:8000
echo     - Interactive Docs:   http://localhost:8000/docs
echo.
echo   Keep both opened terminal windows running while using the twin.
echo =====================================================================
echo.

