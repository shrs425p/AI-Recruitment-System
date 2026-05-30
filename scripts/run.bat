@echo off
echo ===================================================
echo     AI Recruitment System - Startup Loader
echo ===================================================

REM Move to project root (one directory up from scripts\)
cd /d "%~dp0.."

if not exist "venv\Scripts\activate.bat" (
    echo [1/3] Creating Python virtual environment...
    python -m venv venv
    echo [2/3] Activating environment and installing requirements...
    call venv\Scripts\activate.bat
    python -m pip install --upgrade pip --quiet
    pip install -r requirements.txt --quiet
) else (
    echo [1/2] Activating virtual environment...
    call venv\Scripts\activate.bat
)

echo [2/2] Starting the Application Server...
python main.py

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Application crashed or exited with an error.
    pause
)
