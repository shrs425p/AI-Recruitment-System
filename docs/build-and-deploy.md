# Build and Deploy

This document explains how to compile the AI Recruitment System into a standalone Windows executable using PyInstaller, and how to package it into a Windows installer using Inno Setup.

---

## Overview

The build pipeline consists of two stages:

```
Source code  ->  PyInstaller  ->  dist/ARS/ARS.exe  ->  Inno Setup  ->  installer_output/ARS_Setup_1.0.exe
```

Both stages are automated by `scripts/build_installer.bat`.

---

## Prerequisites

| Tool | Version | Installation |
|---|---|---|
| PyInstaller | 6.x | `pip install pyinstaller` |
| Inno Setup | 6.x | [https://jrsoftware.org/isdl.php](https://jrsoftware.org/isdl.php) |

Install Inno Setup to its default location (`C:\Program Files (x86)\Inno Setup 6\`). The build script auto-detects it.

---

## Building the Executable

### Option A — Full Build (Executable + Installer)

```bat
scripts\build_installer.bat
```

This script:
1. Activates the virtual environment.
2. Runs PyInstaller with `build/build.spec`.
3. Runs Inno Setup with `build/installer.iss`.

Output:
- `dist/ARS/ARS.exe` — standalone folder build
- `installer_output/ARS_Setup_1.0.exe` — Windows installer

### Option B — PyInstaller Only

```bat
call venv\Scripts\activate.bat
venv\Scripts\pyinstaller.exe --clean --noconfirm build\build.spec
```

### Option C — Inno Setup Only (after PyInstaller)

```bat
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" build\installer.iss
```

---

## PyInstaller Specification (`build/build.spec`)

### Entry Point

```python
a = Analysis(['main.py'], pathex=[ROOT], ...)
```

`ROOT` is resolved to the project root automatically (one level above `build/`).

### Bundled Data Files

| Source | Destination in bundle |
|---|---|
| `app/templates/` | `app/templates/` |
| `app/static/` | `app/static/` |
| `config/config.py` | `config/` |
| Vosk package directory | `vosk/` |
| speech_recognition data | `speech_recognition/` |
| MediaPipe data files | (collected automatically) |

### Hidden Imports

The spec collects all submodules from:
- `mediapipe`
- `google.auth`
- `google_auth_oauthlib`
- `googleapiclient`
- `vosk`
- `speech_recognition`
- `pyttsx3.drivers`

### Excluded Packages

The following are excluded to reduce build size:

```python
excludes=['tkinter', 'matplotlib', 'scipy', 'notebook', 'IPython']
```

### Build Mode

The build produces a **single folder** (`dist/ARS/`) rather than a one-file executable. This is intentional — one-file mode has significantly longer startup times due to extraction overhead, and is incompatible with the pywebview native bindings.

---

## Inno Setup Specification (`build/installer.iss`)

### What the Installer Packages

| Content | Source | Installed To |
|---|---|---|
| Application bundle | `dist\ARS\*` | `{app}\` |
| Tesseract OCR | `models\Tesseract-OCR\*` | `{app}\models\Tesseract-OCR\` |
| Vosk speech model | `models\vosk-model-small-en-in-0.4\*` | `{app}\models\vosk-model-small-en-in-0.4\` |
| Configuration | `config\config.py` | `{app}\config\` |
| App icon | `app\static\icon\ai.ico` | `{app}\ai.ico` |
| Google credentials | `credentials.json` (if present) | `{app}\` |

### Installation Details

| Setting | Value |
|---|---|
| Default install path | `C:\Program Files\AI Recruitment System\` |
| Minimum Windows | Windows 10 |
| Privileges | Administrator required |
| Output file | `installer_output\ARS_Setup_1.0.exe` |

### Directories Created at Install Time

The installer creates the following empty directories so the application does not fail on first run:

```
{app}\data\
{app}\data\output\txt\
{app}\data\output\nlp\
{app}\data\output\ranking\
{app}\data\output\scheduling\
{app}\data\output\interviews\
{app}\data\output\reports\
{app}\data\output\ssl\
{app}\data\resumes\
```

### Uninstall Cleanup

The uninstaller removes:
- All files in `{app}\data\output\*`
- All files in `{app}\data\resumes\*`
- `{app}\data\ars.db`
- `{app}\data\token.json`

---

## Runtime Path Resolution

When running from the installer (`dist/ARS/ARS.exe`), PyInstaller sets `sys._MEIPASS` to the extraction directory. The `resource_path` function in `app/app_paths.py` handles this transparently:

```python
def resource_path(relative: str) -> Path:
    base = getattr(sys, '_MEIPASS', Path(__file__).parent.parent)
    return Path(base) / relative
```

All writable runtime paths (`data/`, `config/`) are resolved relative to the executable's actual location on disk, not `_MEIPASS`. This ensures user data persists across updates.

---

## Updating the Version Number

To release a new version:

1. Update `#define MyAppVersion` in `build/installer.iss`.
2. Update the `AppId` GUID if the install path or registry keys should change.
3. Add a new entry to `docs/changelog.md`.
4. Run the build script.

---

## Code Signing (Optional)

To sign the executable and installer with a code signing certificate:

```bat
signtool sign /f certificate.pfx /p <password> /t http://timestamp.digicert.com dist\ARS\ARS.exe
signtool sign /f certificate.pfx /p <password> /t http://timestamp.digicert.com installer_output\ARS_Setup_1.0.exe
```

Signed builds will not trigger Windows SmartScreen warnings.
