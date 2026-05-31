# Build and Deploy

The production build has two stages: PyInstaller creates the application bundle, and Inno Setup creates the installer.

```text
source -> dist/ARS/ARS.exe -> ARS_Setup_<version>.exe
```

## Full Build

```bat
scripts\build_installer.bat
```

The script activates the virtual environment, runs PyInstaller with `build\build.spec`, then runs Inno Setup with `build\installer.iss`.

To place the installer in Downloads:

```bat
set ARS_INSTALLER_OUTPUT=%USERPROFILE%\Downloads
scripts\build_installer.bat
```

## Build Only the App Bundle

```bat
venv\Scripts\pyinstaller.exe --clean --noconfirm build\build.spec
```

Output:

```text
dist\ARS\ARS.exe
```

The app uses a folder build instead of one-file mode to improve startup time and keep pywebview native dependencies reliable.

## Build Only the Installer

Run this after `dist\ARS\` exists:

```bat
"Inno Setup 6\ISCC.exe" /FARS_Setup_1.0_production build\installer.iss
```

## Installer Behavior

| Item | Behavior |
|---|---|
| Install scope | Per-user |
| Default install path | `%LOCALAPPDATA%\Programs\AI Recruitment System\` |
| Runtime config | Generated in `%LOCALAPPDATA%\AI Recruitment System\` |
| Developer config | Not packaged |
| Existing user data | Preserved unless reset task is selected |

## Release Smoke Test

Before shipping an installer, run the packaged executable with isolated app data:

```bat
set LOCALAPPDATA=%TEMP%\ARS-Smoke
set ARS_DESKTOP_PORT=55321
set ARS_CANDIDATE_PORT=55322
dist\ARS\ARS.exe
```

Then verify:

```bat
curl http://127.0.0.1:55321/api/health
```

Expected result:

```json
{
  "success": true,
  "status": "ok",
  "database": "ok"
}
```

## Release Checklist

1. Run Ruff.
2. Run pytest.
3. Run bytecode compile.
4. Run dependency audit.
5. Run Bandit for medium/high issues.
6. Build `dist\ARS`.
7. Smoke test the packaged executable.
8. Build the Inno Setup installer.
9. Record installer path, size, and SHA256.

## Code Signing

Code signing is optional but recommended for external distribution.

```bat
signtool sign /f certificate.pfx /p <password> /t http://timestamp.digicert.com dist\ARS\ARS.exe
signtool sign /f certificate.pfx /p <password> /t http://timestamp.digicert.com "%USERPROFILE%\Downloads\ARS_Setup_1.0_production.exe"
```
