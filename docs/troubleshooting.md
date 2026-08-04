# Troubleshooting

Use this guide for common development, runtime, and packaging issues.

## Packaged App Crash

If the app shows `Failed to execute script 'main'`, check:

```text
%LOCALAPPDATA%\AI Recruitment System\crash.log
```

Common causes:

| Error | Fix |
|---|---|
| Import from the wrong module | Import shared paths from `app.app_paths` |
| Missing hidden import | Add it to `build/build.spec` |
| Missing data file | Add it to PyInstaller datas or Inno Setup files |
| Developer config bundled accidentally | Remove config from build datas |

## App Starts With Old Test Data

Installed builds use per-user app data. Delete or reset:

```text
%LOCALAPPDATA%\AI Recruitment System\
```

The installer also has an optional reset task for a fresh install.

## Port Conflicts

The app prefers desktop port `5001` and candidate port `5000`, but automatically falls back to free ports. To force known ports:

```bat
set ARS_DESKTOP_PORT=55321
set ARS_CANDIDATE_PORT=55322
python main.py
```

## Ollama Issues

| Symptom | Fix |
|---|---|
| Connection refused | Start Ollama and verify `curl http://localhost:11434/api/tags` |
| Model not found | Run `ollama pull llama3.2:3b` |
| Slow responses | Use a smaller local model or enable an approved cloud provider |

## OCR Issues

| Symptom | Fix |
|---|---|
| Tesseract not found | Restore `models\Tesseract-OCR\tesseract.exe` |
| Empty scanned output | Use a clearer scan or increase render quality in `src/pdf_to_txt.py` |
| Garbled text | Confirm the language pack exists in Tesseract |

## Voice and Webcam Issues

| Symptom | Fix |
|---|---|
| Vosk model missing | Run `python scripts\setup_vosk.py` |
| Microphone unavailable | Check Windows privacy and default input device |
| TTS silent | Install or enable a Windows SAPI voice |
| Webcam blocked | Grant camera permission to the browser/webview runtime |

## Database Issues

| Symptom | Fix |
|---|---|
| `database is locked` | Close duplicate app instances |
| Missing table | Recreate the database after backing up data |
| Health endpoint degraded | Inspect `data\ars.db` permissions and crash log |

## Build Issues

| Symptom | Fix |
|---|---|
| PyInstaller cannot find native dependency | Add binary/data collection in `build\build.spec` |
| Inno Setup file not found | Build PyInstaller first and verify `dist\ARS\` exists |
| Installer output in wrong folder | Set `ARS_INSTALLER_OUTPUT` |

## Useful Checks

```bat
venv\Scripts\python.exe -m ruff check .
venv\Scripts\python.exe -m pytest
venv\Scripts\python.exe -m compileall -q main.py app src tests
venv\Scripts\python.exe -m pip_audit -r requirements.txt
venv\Scripts\python.exe -m bandit -q -r app src main.py -x venv,build,dist -ll
```
