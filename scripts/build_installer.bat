@echo off
REM ===========================================================
REM  BUILD SCRIPT — AI Recruitment System
REM  Creates: %ARS_INSTALLER_OUTPUT%\ARS_Setup_1.0.exe when set,
REM           otherwise installer_output\ARS_Setup_1.0.exe
REM ===========================================================
REM
REM  Prerequisites (one-time):
REM    1. pip install pyinstaller
REM    2. Install Inno Setup 6  →  https://jrsoftware.org/isdl.php
REM       (default path: "C:\Program Files (x86)\Inno Setup 6")
REM
REM  Usage:
REM    Double-click this file, or run:  scripts\build_installer.bat
REM ===========================================================

REM Move to project root (one directory up from scripts\)
cd /d "%~dp0.."

set "DISPLAY_OUTPUT=%ARS_INSTALLER_OUTPUT%"
if "%DISPLAY_OUTPUT%"=="" set "DISPLAY_OUTPUT=installer_output"

echo.
echo +-----------------------------------------------+
echo ^|   AI Recruitment System - Build Installer     ^|
echo +-----------------------------------------------+
echo.

REM ── Step 1: Activate venv ──
echo [1/3] Activating virtual environment...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Could not activate venv. Make sure venv\ exists.
    pause
    exit /b 1
)

REM ── Step 2: PyInstaller (from venv so all packages are found) ──
if not exist "venv\Scripts\pyinstaller.exe" (
    echo [2/3] Installing the release packaging dependency...
    venv\Scripts\python.exe -m pip install pyinstaller
    if errorlevel 1 (
        echo ERROR: Could not install PyInstaller.
        pause
        exit /b 1
    )
)
echo [2/3] Building app with PyInstaller...
echo       This may take 3-5 minutes on first run.
echo.
venv\Scripts\pyinstaller.exe --clean --noconfirm build\build.spec
if errorlevel 1 (
    echo.
    echo ERROR: PyInstaller failed. Check the output above.
    pause
    exit /b 1
)
echo.
echo       PyInstaller complete - dist\ARS\ created
echo.

REM ── Step 3: Inno Setup ──
echo [3/3] Building setup installer with Inno Setup...

REM Try common Inno Setup paths
set ISCC=
if exist "%~dp0..\Inno Setup 6\ISCC.exe" (
    set "ISCC=%~dp0..\Inno Setup 6\ISCC.exe"
) else if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
    set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
) else if exist "C:\Program Files\Inno Setup 6\ISCC.exe" (
    set "ISCC=C:\Program Files\Inno Setup 6\ISCC.exe"
) else (
    where ISCC >nul 2>&1
    if errorlevel 1 (
        echo.
        echo WARNING: Inno Setup not found.
        echo Install from: https://jrsoftware.org/isdl.php
        echo Then re-run this script, OR compile manually:
        echo   "C:\...\ISCC.exe" build\installer.iss
        echo.
        echo The PyInstaller output is ready at: dist\ARS\
        echo You can still run dist\ARS\ARS.exe directly.
        pause
        exit /b 0
    )
    set "ISCC=ISCC"
)

set "INNO_ATTEMPT=1"
:RUN_INNO
"%ISCC%" build\installer.iss
if errorlevel 1 if "%INNO_ATTEMPT%"=="1" (
    echo.
    echo WARNING: Inno Setup failed on the first attempt. Retrying once...
    set "INNO_ATTEMPT=2"
    timeout /t 3 /nobreak >nul
    goto RUN_INNO
)
if errorlevel 1 (
    echo.
    echo ERROR: Inno Setup compilation failed.
    pause
    exit /b 1
)

echo.
echo ===================================================
echo  BUILD COMPLETE!
echo.
echo  Installer: %DISPLAY_OUTPUT%\ARS_Setup_1.0.exe
echo  Portable:  dist\ARS\ARS.exe
echo ===================================================
echo.
pause
