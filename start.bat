@echo off
title EDGE Drishti Launcher
echo ======================================================================
echo                EDGE DRISHTI SECURITY PLATFORM LAUNCHER
echo ======================================================================
echo.

taskkill /f /im node.exe 2>nul
taskkill /f /fi "windowtitle eq uvicorn" 2>nul

if exist "venv\Scripts\activate.bat" goto activate_venv

echo [INFO] Virtual environment not found. Creating virtual environment...
python -m venv venv
if errorlevel 1 (
    echo [ERROR] Failed to create virtual environment. Please check if Python is installed and in your PATH.
    pause
    exit /b 1
)
echo [OK] Virtual environment created successfully.

echo [INFO] Activating virtual environment...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo [ERROR] Failed to activate virtual environment.
    pause
    exit /b 1
)

echo [INFO] Installing dependencies...
if exist "backend\requirements.txt" (
    pip install -r backend\requirements.txt
) else if exist "requirements.txt" (
    pip install -r requirements.txt
) else (
    echo [ERROR] requirements.txt file not found!
    pause
    exit /b 1
)

if errorlevel 1 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)
goto venv_done

:activate_venv
echo [OK] Activating virtual environment...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo [ERROR] Failed to activate existing virtual environment.
    pause
    exit /b 1
)

:venv_done
echo.

echo [INFO] Clearing previous build artifacts (/out and /.next)...
if exist "out" rd /s /q "out"
if exist ".next" rd /s /q ".next"

echo [OK] Building Next.js frontend assets...
call npm run build
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Next.js frontend build failed!
    echo Please ensure Node.js is installed and run "npm install" manually.
    pause
    exit /b %ERRORLEVEL%
)
echo [OK] Frontend built successfully.
echo.

echo [OK] Starting EDGE Drishti backend server...
python backend\run.py
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Backend failed to start or terminated with error.
    pause
    exit /b %ERRORLEVEL%
)

pause
