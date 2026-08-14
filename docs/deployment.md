# Building and Deployment

This document explains how to build the Windows installer, run the app as a portable executable, and set it up on another machine.

---

## Overview

The build process has two stages:

1. **PyInstaller** — bundles Python, all dependencies, and the app into a single `dist/ARS/` folder
2. **Inno Setup** — wraps `dist/ARS/` into a standard Windows installer (`ARS_Setup_1.0.exe`)

---

## Prerequisites

### PyInstaller

```bash
pip install pyinstaller
```

### Inno Setup 6

Download and install from [jrsoftware.org/isdl.php](https://jrsoftware.org/isdl.php).

The build script looks for Inno Setup in these locations:
- `Inno Setup 6\ISCC.exe` (in the project folder — used if bundled)
- `C:\Program Files (x86)\Inno Setup 6\ISCC.exe` (standard install path)
- `C:\Program Files\Inno Setup 6\ISCC.exe` (64-bit install)
- `ISCC` on the system PATH

---

## Building the Installer

### Option 1 — Double-click the batch script

```
scripts\build_installer.bat
```

The script runs three steps automatically:
1. Activates the virtual environment (`venv\Scripts\activate.bat`)
2. Runs PyInstaller with `build\build.spec`
3. Runs Inno Setup with `build\installer.iss`

**Output:**
- Portable build: `dist\ARS\ARS.exe`
- Windows installer: `installer_output\ARS_Setup_1.0.exe`

### Option 2 — Run steps manually

**Step 1 — PyInstaller:**
```bash
venv\Scripts\activate
pyinstaller --clean --noconfirm build\build.spec
```

**Step 2 — Inno Setup:**
```bash
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" build\installer.iss
```

---

## Build Configuration Files

### `build/build.spec`

This is the PyInstaller spec file. It controls:
- Entry point (`main.py`)
- Which data files to bundle (templates, static, models)
- Hidden imports (packages PyInstaller can't auto-detect)
- Output name and paths

If you add new dependencies or data files, you may need to update `build.spec`.

### `build/installer.iss`

Inno Setup script that defines:
- App name, version, publisher
- Which files to include in the installer
- Installation directory (`Program Files\AI Recruitment System`)
- Start menu shortcut creation
- Uninstaller registration

---

## Portable Build (No Installer)

If you only ran PyInstaller (not Inno Setup), you can still run the app directly:

```
dist\ARS\ARS.exe
```

The `dist\ARS\` folder is self-contained — you can copy it to any Windows machine and run `ARS.exe`. No Python installation needed on the target machine.

---

## Custom Output Path

To change where the installer is saved:

```bat
set ARS_INSTALLER_OUTPUT=D:\Builds\ARS
scripts\build_installer.bat
```

---

## Installing on Another Machine

1. Copy `installer_output\ARS_Setup_1.0.exe` to the target machine
2. Double-click to run the installer
3. Follow the installation wizard
4. Launch from the Start menu shortcut or `ARS.exe` in the install directory

### What Gets Installed

The installer copies:
- `ARS.exe` and all bundled dependencies
- Bundled models (`Tesseract-OCR/`, `vosk-model-small-en-in-0.4/`)
- Templates, static files, scripts

### What Is NOT Installed

User data is stored separately in `%LOCALAPPDATA%\AI Recruitment System\` and is **not affected by install/uninstall**. This means:
- Settings are preserved across reinstalls
- Uploaded resumes and interview data persist
- API keys survive upgrades

---

## First Run After Installation

The first time the installed app runs:
1. It creates `%LOCALAPPDATA%\AI Recruitment System\` if it doesn't exist
2. Initialises the SQLite database
3. Generates a self-signed TLS certificate for the candidate portal
4. Opens the desktop window

---

## Uninstalling

Use **Add or Remove Programs** in Windows Settings or run the uninstaller from:
```
C:\Program Files\AI Recruitment System\unins000.exe
```

User data in `%LOCALAPPDATA%\AI Recruitment System\` is **not deleted** on uninstall. Delete it manually if you want a clean removal:
```
rmdir /s /q "%LOCALAPPDATA%\AI Recruitment System"
```

---

## Network Setup for Candidate Portal

The candidate interview portal (port 5000 HTTPS) needs to be reachable from candidates' devices on the local network.

### Find your IP address

```bat
ipconfig
```

Look for **IPv4 Address** under your active network adapter (usually Wi-Fi or Ethernet). Example: `192.168.1.100`.

The candidate URL will be:
```
https://192.168.1.100:5000/candidate-interview/<token>
```

### Open Windows Firewall

The build includes a helper script:
```bat
scripts\setup_firewall.bat
```

Run it as Administrator to allow inbound connections on port 5000. Or manually:
1. Windows Defender Firewall → Advanced Settings
2. Inbound Rules → New Rule
3. Port → TCP → 5000 → Allow the connection
4. Apply to all profiles

### Candidates on a different network (remote interviews)

The candidate portal runs on your local machine — it is not publicly accessible by default. For remote interviews:

**Option 1 — VPN:** Both HR and candidates connect to the same VPN. The LAN IP becomes reachable.

**Option 2 — Port forwarding:** Forward port 5000 on your router to your machine's local IP. Candidates use your public IP.

**Option 3 — ngrok (quick tunnel):**
```bash
pip install ngrok
ngrok http https://localhost:5000
```
ngrok gives you a public `https://xxx.ngrok.io` URL that tunnels to your local candidate portal.

---

## Build Times

| Stage | First Run | Subsequent Runs |
|---|---|---|
| PyInstaller | 5–10 minutes | 2–3 minutes |
| Inno Setup | 30–60 seconds | 30–60 seconds |

PyInstaller caches compiled `.pyc` files, so subsequent builds are faster. Use `--clean` to force a full rebuild if you see stale file issues.
