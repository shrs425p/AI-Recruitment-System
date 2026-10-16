@echo off
echo ===================================================
echo     AI Recruitment System - Force Kill All
echo ===================================================

echo Stopping all ARS application processes...
taskkill /F /IM ARS.exe /T 2>nul
taskkill /F /IM pythonw.exe /T 2>nul
taskkill /F /IM python.exe /T 2>nul

echo.
echo All processes terminated successfully!
pause
