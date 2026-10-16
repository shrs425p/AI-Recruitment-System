@echo off
setlocal
echo ===================================================
echo     AI Recruitment System - Resume Generator
echo ===================================================

REM Move to project root (one directory up from scripts\)
cd /d "%~dp0.."

if not exist "venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found. Please run scripts\run.bat first.
    pause
    exit /b 1
)

echo Generating synthetic resume PDFs...
venv\Scripts\python.exe scripts\generate_resumes.py %*

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Resume generation failed.
    pause
    exit /b 1
)

echo.
echo [SUCCESS] Resumes generated successfully!
pause
exit /b 0
