# Troubleshooting

Common issues and how to fix them.

---

## Application Won't Start

### `ModuleNotFoundError: No module named 'webview'`
```bash
pip install pywebview
```

### `ModuleNotFoundError: No module named 'waitress'`
```bash
pip install waitress
```

### Any other `ModuleNotFoundError`
Run the environment checker:
```bash
python scripts/verify_environment.py
```
It lists all missing packages. Then:
```bash
pip install -r requirements.txt
```

### Port already in use
If port 5001 or 5000 is already taken by another process:
```bash
# Find what's using the port
netstat -ano | findstr :5001

# Kill it (replace PID with the actual process ID)
taskkill /F /PID <PID>
```
Or change the ports using environment variables before launching:
```
set ARS_DESKTOP_PORT=5002
set ARS_CANDIDATE_PORT=5003
python main.py
```

---

## Database Issues

### Settings not saving / reverting to defaults
The database is at `%LOCALAPPDATA%\AI Recruitment System\data\ars.db`.  
If it's corrupted, delete it and let the app recreate it on next launch:
```
del "%LOCALAPPDATA%\AI Recruitment System\data\ars.db"
```
**Note:** This resets all settings. You will need to re-enter API keys.

### `sqlite3.OperationalError: database is locked`
The database is being accessed by two processes simultaneously. Close the app, wait a few seconds, then relaunch.

### Encrypted values showing as blank after moving the app
The encryption key is derived from `.secret_salt` at `%LOCALAPPDATA%\AI Recruitment System\.secret_salt`. If the app was reinstalled or moved, the old salt file may be missing. You'll need to re-enter all API keys in Settings.

---

## AI / Provider Issues

### "No cloud providers are enabled"
Go to Settings → AI Providers:
- Make sure at least one provider is enabled
- Make sure the API key is not a placeholder (`nvapi-...`, `sk-...`, etc.)
- Save settings

### AI returns empty response or garbage
- The model may be too small for the task. Try switching to a larger model (e.g. `llama3.1:8b` instead of `llama3.2:3b`)
- Check that the AI provider is responding: `python scripts/verify_providers.py`
- Check the live log (Sidebar → Logs) for specific error messages

### Provider returns HTTP 401 / Invalid API Key
- The key may have been copied incorrectly — re-copy from the provider's dashboard
- The key may have been revoked — generate a new one
- Update it in Settings → AI Providers

### Provider returns HTTP 429 / Rate Limit
The provider's rate limit was hit. Options:
- Enable additional providers so the router can spread load
- Wait and retry (rate limits usually reset per minute)
- Switch to a higher-tier plan on the provider

### Ollama not responding
1. Make sure Ollama is installed: [ollama.com/download](https://ollama.com/download)
2. Make sure Ollama is running:
   ```bash
   ollama serve
   ```
3. Make sure the model is pulled:
   ```bash
   ollama list
   ollama pull llama3.2:3b
   ```
4. Check the Base URL in Settings matches your Ollama address (default: `http://localhost:11434`)
5. Test it directly:
   ```bash
   curl http://localhost:11434/api/tags
   ```

### NLP extraction produces empty or wrong fields
- The AI failed to parse the resume. Check the live log for provider error messages.
- The resume text extraction may have failed — check if a `.txt` file was created in `data/output/txt/`
- If the `.txt` file is empty, OCR may have failed (see OCR section below)

---

## OCR Issues

### Tesseract not found
The bundled Tesseract binary is at `models/Tesseract-OCR/tesseract.exe`. If it's missing:
```bash
# Check if it exists
dir models\Tesseract-OCR\tesseract.exe
```
If the `models/Tesseract-OCR/` directory is empty or missing, the file was likely not committed to git (check `.gitignore`) or was deleted.

### Scanned PDF produces empty text
1. Check if the PDF renders correctly when opened — if not, the PDF itself may be corrupt
2. Try a higher-resolution scan (300 DPI minimum for good OCR accuracy)
3. Check if Tesseract is finding the correct language data:
   - Language files are in `models/Tesseract-OCR/tessdata/`
   - `eng.traineddata` must be present for English OCR

### Image files (PNG/JPG) produce no text
- Very low resolution images will fail OCR. 300 DPI or higher is recommended.
- Check that Pillow is installed: `pip install Pillow`

---

## Voice / Microphone Issues

### Voice mode not showing up in the interview
The system checks microphone and TTS availability when loading the interview page. One of them failed.

**Check manually:**
```bash
python -c "from src.voice_interview import check_microphone, check_tts; print(check_microphone()); print(check_tts())"
```

### Microphone not detected
- Check Windows sound settings: Settings → System → Sound → Input — make sure a microphone is listed
- Check that the microphone is not muted
- Try a different USB port or device

### Vosk model not found
The Vosk model must be at `models/vosk-model-small-en-in-0.4/`. If missing:
```bash
python scripts/setup_vosk.py
```

### `pyttsx3` not working / TTS silent
- Check that a TTS voice is installed in Windows: Settings → Accessibility → Speech
- Try `pip install pypiwin32` if on Windows and pyttsx3 fails to initialise

### Speech recognition very inaccurate
The bundled model is the small English-India model which trades accuracy for size. If accuracy is poor:
- Speak slowly and clearly
- Reduce background noise
- Download a larger Vosk model from [alphacephei.com/vosk/models](https://alphacephei.com/vosk/models) and replace the model folder

---

## Webcam / Proctoring Issues

### Webcam not detected
```bash
python -c "import cv2; cap = cv2.VideoCapture(0); print(cap.isOpened()); cap.release()"
```
If `False`, OpenCV can't access the webcam. Check:
- Webcam is connected and drivers are installed
- No other application is using the webcam
- Windows camera permissions: Settings → Privacy → Camera → allow Python

### Face not being detected (Haar cascade)
- Make sure you are in a well-lit environment
- Face must be clearly visible and facing the camera
- The Haar cascade `haarcascade_frontalface_default.xml` must exist in OpenCV's data directory

### MediaPipe not working
```bash
pip install mediapipe>=0.10.9
```
If it installs but still fails on import, check your Python version (MediaPipe requires Python 3.8–3.11).

### Proctor stream not showing in HR dashboard
The proctor frame is served as a base64 JPEG via a polling endpoint. If the stream is blank:
- The webcam is not started (interview session not active)
- The browser is blocking mixed content (HTTP polling from an HTTPS page) — this should not happen on localhost

---

## Candidate Portal Issues

### Candidate sees SSL certificate warning
This is expected for the self-signed certificate. Candidates need to click **Advanced → Proceed to site** (exact text varies by browser). This is a one-time step per browser.

### Candidate cannot reach the interview URL
- Make sure the candidate is on the same local network (LAN/WiFi)
- The URL uses the HR machine's local IP address — not `localhost`
- Find your IP: `ipconfig` → look for IPv4 address under your active adapter
- Make sure the firewall allows inbound connections on port 5000:
  ```bash
  scripts\setup_firewall.bat
  ```
- Make sure the Flask HTTPS server is running (check the live log)

### Token invalid or expired
- The candidate may have already used the token
- The application may have been restarted (in-memory session data is lost on restart)
- Re-generate a token from the Scheduling page

---

## Log File Locations

| Log | Location |
|---|---|
| Live application log | Sidebar → Logs (in the app UI) |
| Crash log | `%LOCALAPPDATA%\AI Recruitment System\crash.log` |
| NLP output | `%LOCALAPPDATA%\AI Recruitment System\data\output\nlp\` |
| Interview transcripts | `%LOCALAPPDATA%\AI Recruitment System\data\output\interviews\` |

For detailed debugging, run:
```
set ARS_DEBUG=1
python main.py
```
This enables Flask debug mode with more verbose error output in the log.
