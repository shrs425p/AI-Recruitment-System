@echo off
echo ===================================================
echo     AI Recruitment System - Force Kill All
echo ===================================================

echo Stopping all Python backend and frontend processes...
taskkill /F /IM python.exe /T

echo.
echo All processes terminated successfully!
pause
