@echo off
setlocal
echo ===================================================
echo     AI Recruitment System - Startup Loader
echo ===================================================

REM Move to project root (one directory up from scripts\)
cd /d "%~dp0.."

set "PYTHON_CMD=python"
python --version >nul 2>&1
if errorlevel 1 (
    set "PYTHON_CMD=py -3.12"
    py -3.12 --version >nul 2>&1
)

if errorlevel 1 (
    echo [ERROR] Python 3.10-3.12 was not found.
    echo Install Python from https://www.python.org/downloads/ and run this file again.
    pause
    exit /b 1
)

set "REBUILD_VENV=0"
if not exist "venv\Scripts\python.exe" set "REBUILD_VENV=1"
if "%REBUILD_VENV%"=="0" (
    venv\Scripts\python.exe -c "import flask, webview, waitress" >nul 2>&1
    if errorlevel 1 set "REBUILD_VENV=1"
)

if "%REBUILD_VENV%"=="1" (
    if exist "venv" (
        echo [1/3] Replacing damaged virtual environment...
        rmdir /s /q venv
    ) else (
        echo [1/3] Creating Python virtual environment...
    )
    call %PYTHON_CMD% -m venv venv
    if errorlevel 1 goto :startup_failed
    echo [2/3] Installing application dependencies...
    venv\Scripts\python.exe -m pip install --upgrade pip --quiet
    venv\Scripts\python.exe -m pip install -r requirements.txt --quiet
    if errorlevel 1 goto :startup_failed
) else (
    echo [1/2] Verified existing virtual environment.
)

echo [2/2] Starting the Application Server...
venv\Scripts\python.exe main.py

if %ERRORLEVEL% neq 0 (
    goto :startup_failed
)
exit /b 0

:startup_failed
echo.
echo [ERROR] Application failed to start. Review the message above and try again.
pause
exit /b 1
