@echo off
echo ===================================================
echo     AI Recruitment System - One-Click Start
echo ===================================================

if not exist ".venv\Scripts\activate.bat" (
    echo [1/3] Creating Python virtual environment...
    python -m venv venv
)

echo [2/3] Activating environment and checking dependencies...
call venv\Scripts\activate.bat
pip install -r requirements.txt --quiet

echo [3/3] Starting the Application Server...
echo Please ensure Ollama is running (ollama serve) before continuing.
echo.
python app.py

pause
