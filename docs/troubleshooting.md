# Troubleshooting

This document covers the most common errors encountered when running, building, or deploying the AI Recruitment System, and the steps required to resolve them.

---

## Application Fails to Start

### Symptom

The console shows a traceback immediately after running `python main.py` or `scripts\run.bat`.

### Diagnosis

Run the verification script from the project root:

```bat
call venv\Scripts\activate.bat
python -c "import main"
```

The full traceback will identify the failing module.

### Common Causes

| Error | Resolution |
|---|---|
| `ModuleNotFoundError: No module named 'flask'` | Run `pip install -r requirements.txt` |
| `ModuleNotFoundError: No module named 'webview'` | Run `pip install pywebview` |
| `ImportError: cannot import name 'X' from 'Y'` | See Import Errors section below |
| `Address already in use` | Port 5000 or 5001 is occupied — run `scripts\kill.bat` or change the port in `main.py` |

---

## Import Errors

### `cannot import name 'process_file_async' from 'nlp_extractor'`

The async wrapper is missing from `src/nlp_extractor.py`. Add to the end of the file:

```python
async def process_file_async(txt_file, output_path):
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, process_file, txt_file, output_path)
```

### `cannot import name 'create_event_from_dict' from 'google_calendar'`

The wrapper function is missing from `src/google_calendar.py`. It should delegate to `create_interview_event` using HR settings from `config`.

### `SyntaxError: name 'X' is assigned to before global declaration`

A `global` statement appears after a variable assignment in the same scope. Move the `global` declaration to the top of the function, before any assignments.

---

## AI / Ollama Issues

### Ollama Not Reachable

**Symptom:** `Connection refused` errors when the NLP or ranking step runs.

**Resolution:**

```bat
:: Check if Ollama is running
curl http://localhost:11434/api/tags

:: Start Ollama if not running
ollama serve
```

Ensure the OLLAMA_BASE_URL in `config/config.py` matches the actual Ollama server address.

### Model Not Pulled

**Symptom:** Ollama responds but returns `model not found`.

**Resolution:**

```bat
ollama pull llama3.2:3b
```

### Slow AI Responses

Typical NLP extraction takes 10–60 seconds per resume depending on hardware. For faster processing:

1. Use a smaller model: `ollama pull llama3.2:1b`
2. Enable a cloud provider in `APP_MODE = 'cloud'` mode.
3. Increase available RAM — the 3B model requires approximately 4 GB of free RAM.

### Cloud Provider Returns 401 or 403

The API key is invalid or expired. Regenerate the key from the provider's console and update `config/config.py`.

---

## OCR Issues

### Tesseract Binary Not Found

**Symptom:** `TesseractNotFoundError` during the PDF-to-text step.

**Resolution:** Verify the binary exists at `models/Tesseract-OCR/tesseract.exe`. If missing:

1. Download the portable Tesseract build from [UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract/wiki).
2. Extract it to `models/Tesseract-OCR/`.

### OCR Output is Empty or Garbled

- For scanned PDFs, increase the render resolution in `src/pdf_to_txt.py` (default: `Matrix(3, 3)` = ~216 dpi).
- Ensure the resume language is supported by the installed Tesseract language packs. English is included by default.
- Some image resumes use JPEG compression artifacts that reduce OCR accuracy. Request a higher-quality file from the candidate.

---

## Speech and Voice Issues

### Vosk Model Not Found

**Symptom:** `[STT] Vosk model directory not found` in the console.

**Resolution:**

```bat
python scripts/setup_vosk.py
```

The model should appear at `models/vosk-model-small-en-in-0.4/`.

### Microphone Not Detected

**Resolution:**

1. Ensure a microphone is connected.
2. Check Windows sound settings — set the correct input device as default.
3. Verify the Python process has microphone permissions (Windows Privacy Settings).

### pyttsx3 TTS Silent

Some Windows systems have SAPI voices disabled. Check **Settings > Time and Language > Speech > Manage voices** and ensure at least one voice is installed.

---

## Google Calendar Issues

| Error | Resolution |
|---|---|
| `credentials.json not found` | Download OAuth credentials from Google Cloud Console and place in project root |
| `Calendar API has not been used` | Enable the Google Calendar API in Google Cloud Console |
| `Token expired or invalid` | Delete `data/token.json` and re-authenticate |
| `accessNotConfigured` | The Cloud project does not have billing enabled or the API is disabled |

---

## Database Issues

### Database Locked

**Symptom:** `sqlite3.OperationalError: database is locked`

**Resolution:** Only one process should access `data/ars.db` at a time. Ensure no other instance of the application is running. If the issue persists after stopping all instances, the database may have a stale lock — restart the machine.

### Missing Table

**Symptom:** `sqlite3.OperationalError: no such table: X`

**Resolution:** The database was created by an older version missing the new table. Delete `data/ars.db` and restart the application. The database will be recreated with the current schema.

> **Warning:** Deleting `ars.db` removes all historical run data, candidate records, schedules, and interview tokens.

---

## SSL Certificate Errors

### Symptom

Candidates see a browser warning when opening the interview link.

### Explanation

The application uses a self-signed certificate generated at first launch (`data/output/ssl/cert.pem`). Self-signed certificates are not trusted by browsers by default.

### Resolution

Instruct candidates to:
1. Open the interview link.
2. Click **Advanced** in the browser warning.
3. Click **Proceed to site (unsafe)**.

For production deployments requiring trusted certificates, replace the self-signed cert with one issued by a CA such as Let's Encrypt. Update the `cert_path` and `key_path` in `main.py` accordingly.

### Regenerating the Certificate

Delete `data/output/ssl/cert.pem` and `key.pem`, then restart the application.

---

## Build Issues

### PyInstaller Fails on mediapipe

MediaPipe has complex native dependencies. Ensure `mediapipe>=0.10` is installed in the venv and use the `collect_submodules('mediapipe')` hook in `build/build.spec`.

### Missing DLL Errors at Runtime

Run the built executable from a clean Windows machine (without Python installed). If DLLs are missing, add them to the `binaries` list in `build/build.spec`:

```python
binaries=[('path/to/missing.dll', '.')],
```

### Inno Setup — File Not Found

All paths in `build/installer.iss` are relative to the project root. Ensure:
- `dist/ARS/` exists (PyInstaller ran successfully).
- `models/Tesseract-OCR/` exists.
- `models/vosk-model-small-en-in-0.4/` exists.

---

## Reporting a Bug

When reporting an issue, include:

1. The full error traceback from the console.
2. The contents of `config/config.py` (redact API keys).
3. The Python version (`python --version`).
4. The Windows version.
5. The output of `pip list` from the virtual environment.
