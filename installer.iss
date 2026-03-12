; ─────────────────────────────────────────────────────────────
; Inno Setup Script — AI Recruitment System Installer
; ─────────────────────────────────────────────────────────────
; Requires: Inno Setup 6+ (free) — https://jrsoftware.org/isinfo.php
;
; This script packages:
;   1. The PyInstaller output   (dist\ARS\*)
;   2. Tesseract-OCR folder     (Tesseract-OCR\*)
;   3. Vosk speech model        (vosk-model-small-en-in-0.4\*)
;   4. Setup helper             (setup_vosk.py)
;   5. Config file              (config.py — editable post-install)
;   6. Google Calendar creds    (credentials.json — if present)
;
; The installer creates a Start Menu shortcut and optional Desktop shortcut.
; ─────────────────────────────────────────────────────────────

#define MyAppName      "AI Recruitment System"
#define MyAppVersion   "1.0"
#define MyAppPublisher "ARS Team"
#define MyAppExeName   "ARS.exe"
#define MyAppIcon      "static\icon\ai.ico"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir=installer_output
OutputBaseFilename=ARS_Setup_{#MyAppVersion}
SetupIconFile={#MyAppIcon}
UninstallDisplayIcon={app}\ai.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
DisableProgramGroupPage=yes
LicenseFile=
; Minimum Windows 10
MinVersion=10.0

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
; ── 1. PyInstaller output (the main app + all Python deps) ──
Source: "dist\ARS\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; ── 2. Tesseract OCR (portable, ~65 MB) ──
Source: "Tesseract-OCR\*"; DestDir: "{app}\Tesseract-OCR"; Flags: ignoreversion recursesubdirs createallsubdirs

; ── 3. Vosk speech model (~36 MB) ──
Source: "vosk-model-small-en-in-0.4\*"; DestDir: "{app}\vosk-model-small-en-in-0.4"; Flags: ignoreversion recursesubdirs createallsubdirs

; ── 4. Editable config (never overwrite if user modified it) ──
Source: "config.py"; DestDir: "{app}"; Flags: onlyifdoesntexist

; ── 5. App icon for shortcuts/uninstall entry ──
Source: "static\icon\ai.ico"; DestDir: "{app}"; DestName: "ai.ico"; Flags: ignoreversion

; ── 6. Google Calendar credentials (optional) ──
Source: "credentials.json"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

[Dirs]
; Create output folders so the app doesn't crash on first run
Name: "{app}\output"
Name: "{app}\output\txt"
Name: "{app}\output\nlp"
Name: "{app}\output\ranking"
Name: "{app}\output\scheduling"
Name: "{app}\output\interviews"
Name: "{app}\output\reports"
Name: "{app}\output\ssl"
Name: "{app}\resumes"

[Icons]
Name: "{group}\{#MyAppName}";   Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\ai.ico"
Name: "{group}\Uninstall ARS";  Filename: "{uninstallexe}"
Name: "{commondesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\ai.ico"; Tasks: desktopicon

[Run]
; Launch app after install (optional)
Filename: "{app}\{#MyAppExeName}"; Description: "Launch AI Recruitment System"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Clean up generated files on uninstall
Type: files; Name: "{app}\output\*"
Type: dirifempty; Name: "{app}\output"
Type: files; Name: "{app}\resumes\*"
Type: dirifempty; Name: "{app}\resumes"
Type: files; Name: "{app}\ars.db"
Type: files; Name: "{app}\token.json"
