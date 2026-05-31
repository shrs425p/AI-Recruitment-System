; ─────────────────────────────────────────────────────────────
; Inno Setup Script — AI Recruitment System Installer
; ─────────────────────────────────────────────────────────────
; Requires: Inno Setup 6+ (free) — https://jrsoftware.org/isinfo.php
;
; This script packages:
;   1. The PyInstaller output   (dist\ARS\*)
;   2. Tesseract-OCR folder     (models\Tesseract-OCR\*)
;   3. Vosk speech model        (models\vosk-model-small-en-in-0.4\*)
;   4. Setup helper             (scripts\setup_vosk.py)
;   5. Google Calendar creds    (credentials.json — if present)
;
; The installer creates a Start Menu shortcut and optional Desktop shortcut.
; Run from project root: "Inno Setup 6\ISCC.exe" build\installer.iss
; ─────────────────────────────────────────────────────────────

#define MyAppName      "AI Recruitment System"
#define MyAppVersion   "1.0"
#define MyAppPublisher "ARS Team"
#define MyAppExeName   "ARS.exe"
#define MyAppIcon      "..\app\static\icon\ai.ico"
#define OutputOverride GetEnv("ARS_INSTALLER_OUTPUT")
#if OutputOverride == ""
  #define OutputDirPath "..\installer_output"
#else
  #define OutputDirPath OutputOverride
#endif

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir={#OutputDirPath}
OutputBaseFilename=ARS_Setup_{#MyAppVersion}
SetupIconFile={#MyAppIcon}
UninstallDisplayIcon={app}\ai.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
DisableProgramGroupPage=yes
LicenseFile=
; Minimum Windows 10
MinVersion=10.0

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"
Name: "resetappdata"; Description: "Reset existing local app data for a fresh install"; GroupDescription: "Data options:"; Flags: unchecked

[Files]
; ── 1. PyInstaller output (the main app + all Python deps) ──
Source: "..\dist\ARS\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; ── 2. Tesseract OCR (portable, ~65 MB) ──
Source: "..\models\Tesseract-OCR\*"; DestDir: "{app}\models\Tesseract-OCR"; Flags: ignoreversion recursesubdirs createallsubdirs

; ── 3. Vosk speech model (~36 MB) ──
Source: "..\models\vosk-model-small-en-in-0.4\*"; DestDir: "{app}\models\vosk-model-small-en-in-0.4"; Flags: ignoreversion recursesubdirs createallsubdirs

; ── 4. App icon for shortcuts/uninstall entry ──
Source: "..\app\static\icon\ai.ico"; DestDir: "{app}"; DestName: "ai.ico"; Flags: ignoreversion

; ── 5. Google Calendar credentials (optional) ──
Source: "..\credentials.json"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist

[Dirs]
; Create output folders so the app doesn't crash on first run
Name: "{app}\data"
Name: "{app}\data\output"
Name: "{app}\data\output\txt"
Name: "{app}\data\output\nlp"
Name: "{app}\data\output\ranking"
Name: "{app}\data\output\scheduling"
Name: "{app}\data\output\interviews"
Name: "{app}\data\output\reports"
Name: "{app}\data\output\ssl"
Name: "{app}\data\resumes"

[InstallDelete]
; Optional fresh-install reset. Leave unchecked when upgrading a real deployment.
Type: filesandordirs; Name: "{localappdata}\{#MyAppName}"; Check: ShouldResetAppData

[Icons]
Name: "{group}\{#MyAppName}";   Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\ai.ico"
Name: "{group}\Uninstall ARS";  Filename: "{uninstallexe}"
Name: "{userdesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\ai.ico"; Tasks: desktopicon

[Run]
; Launch app after install (optional)
Filename: "{app}\{#MyAppExeName}"; Description: "Launch AI Recruitment System"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Clean up generated files on uninstall
Type: filesandordirs; Name: "{localappdata}\{#MyAppName}"
Type: files; Name: "{app}\data\output\*"
Type: dirifempty; Name: "{app}\data\output"
Type: files; Name: "{app}\data\resumes\*"
Type: dirifempty; Name: "{app}\data\resumes"
Type: files; Name: "{app}\data\ars.db"
Type: files; Name: "{app}\data\token.json"

[Code]
function ShouldResetAppData: Boolean;
begin
  Result := WizardIsTaskSelected('resetappdata');
end;
