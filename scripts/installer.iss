[Setup]
AppName=AI Recruitment System
AppVersion=1.0
DefaultDirName={autopf}\ARS
DefaultGroupName=AI Recruitment System
UninstallDisplayIcon={app}\ARS.exe
Compression=lzma2
SolidCompression=yes
OutputDir=..\installer_output
OutputBaseFilename=ARS_Setup_1.0
ArchitecturesInstallIn64BitMode=x64
SetupIconFile=..\app\static\icon\ai.ico

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\ARS\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\AI Recruitment System"; Filename: "{app}\ARS.exe"
Name: "{group}\{cm:UninstallProgram,AI Recruitment System}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\AI Recruitment System"; Filename: "{app}\ARS.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\ARS.exe"; Description: "{cm:LaunchProgram,AI Recruitment System}"; Flags: nowait postinstall skipifsilent
