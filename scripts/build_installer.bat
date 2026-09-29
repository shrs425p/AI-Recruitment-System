@echo off
REM ===========================================================
REM  BUILD SCRIPT — AI Recruitment System (DUAL RELEASE)
REM  Creates:
REM   1. installer_output\ARS_Setup_1.0_Public.exe (NO CREDENTIALS)
REM   2. installer_output\ARS_Setup_1.0_Private.exe (BUNDLED CREDENTIALS)
REM ===========================================================

cd /d "%~dp0.."

set "DISPLAY_OUTPUT=%ARS_INSTALLER_OUTPUT%"
if "%DISPLAY_OUTPUT%"=="" set "DISPLAY_OUTPUT=installer_output"

echo.
echo +-----------------------------------------------+
echo ^|   AI Recruitment System - Dual Installer Build  ^|
echo +-----------------------------------------------+
echo.

echo [1/4] Activating virtual environment...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Could not activate venv.
    pause
    exit /b 1
)

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
        echo ERROR: Inno Setup not found. Install from https://jrsoftware.org/isdl.php
        pause
        exit /b 1
    )
    set "ISCC=ISCC"
)

if not exist "venv\Scripts\pyinstaller.exe" (
    echo [1.5/4] Installing PyInstaller dependency...
    venv\Scripts\python.exe -m pip install pyinstaller
    if errorlevel 1 (
        echo ERROR: Could not install PyInstaller.
        pause
        exit /b 1
    )
)

REM ===========================================================
REM BUILD 1: PUBLIC (No Credentials)
REM ===========================================================
echo.
echo [2/4] Building PUBLIC release (No credentials)...
set BUNDLE_CREDS=0

venv\Scripts\pyinstaller.exe --clean --noconfirm scripts\build.spec
if errorlevel 1 (
    echo ERROR: PyInstaller failed on Public build.
    pause
    exit /b 1
)

"%ISCC%" /F"ARS_Setup_1.0_Public" scripts\installer.iss
if errorlevel 1 (
    echo ERROR: Inno Setup failed on Public build.
    pause
    exit /b 1
)

REM ===========================================================
REM BUILD 2: PRIVATE (Bundled Credentials)
REM ===========================================================
echo.
echo [3/4] Building PRIVATE release (Bundled credentials)...
set BUNDLE_CREDS=1

venv\Scripts\pyinstaller.exe --clean --noconfirm scripts\build.spec
if errorlevel 1 (
    echo ERROR: PyInstaller failed on Private build.
    pause
    exit /b 1
)

"%ISCC%" /F"ARS_Setup_1.0_Private" scripts\installer.iss
if errorlevel 1 (
    echo ERROR: Inno Setup failed on Private build.
    pause
    exit /b 1
)

REM ===========================================================
REM FINISH
REM ===========================================================
echo.
echo [4/4] Build Complete! Both installers generated.
echo.
echo -----------------------------------------------------------
echo  PUBLIC RELEASE (Safe for GitHub/Web):
echo  %DISPLAY_OUTPUT%\ARS_Setup_1.0_Public.exe
echo.
echo  PRIVATE RELEASE (For internal HR team only):
echo  %DISPLAY_OUTPUT%\ARS_Setup_1.0_Private.exe
echo -----------------------------------------------------------
echo.
pause
