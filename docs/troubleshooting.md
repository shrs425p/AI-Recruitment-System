# Troubleshooting

Diagnostic steps and fixes for common runtime issues.

---

## 1. Startup & Environment

### `ModuleNotFoundError: No module named 'docx'`
Install the Word document parsing dependency:
```bash
pip install python-docx
```

### `ModuleNotFoundError: No module named 'webview'` or `'waitress'`
Install the desktop shell and WSGI server:
```bash
pip install pywebview waitress
```

### Verify Entire Runtime Environment
Run the automated test suite to verify all 14 domain modules:
```bash
pytest -v
```
All 140 tests should pass. If any test fails, run with verbose logging:
```bash
pytest tests/test_api.py -v -s
```

### Port Already in Use (5001 or 5000)
If ports 5001 (HR desktop) or 5000 (Candidate portal) are occupied:
```powershell
netstat -ano | findstr :5001
taskkill /F /PID <PID>
```
Or set custom ports in your environment before starting:
```powershell
$env:FLASK_PORT=5002
$env:CANDIDATE_PORT=5003
python main.py
```

---

## 2. Document & Text Extraction

### Word (.docx) Resume Extraction Issues
- **Password-Protected Documents:** The system rejects password-encrypted `.docx` files. Ask the candidate to re-upload an unencrypted file.
- **Corrupted XML Structure:** If a Word file fails parsing, verify that it opens cleanly in Microsoft Word or LibreOffice.
- **Table Formatting:** Tables in `.docx` files are parsed into space-delimited text lines. Ensure candidates don't hide crucial skills inside deeply nested drawing canvases.

### Scanned PDF Produces Empty Text
1. Verify the PDF isn't a completely blank scan.
2. Ensure Tesseract OCR is installed at `models/Tesseract-OCR/tesseract.exe`.
3. Check that the English trained data file exists: `models/Tesseract-OCR/tessdata/eng.traineddata`.
4. Ensure scanned documents have a minimum resolution of 300 DPI for reliable OCR text recognition.

---

## 3. Database & SQLite Locks

### `sqlite3.OperationalError: database is locked`
Occurs if multiple processes attempt to write simultaneously or an unclosed connection persists:
- ARS uses a transactional context manager with automatic rollback and WAL (Write-Ahead Logging) mode.
- Close duplicate running instances of `python main.py` in the Windows Task Manager.
- Ensure the database file at `data/recruitment.db` is not opened in an exclusive-lock database viewer.

### Corrupted Database Reset
To reinitialize a clean schema without losing uploaded resumes:
```powershell
Remove-Item data\recruitment.db -Force
python main.py
```
The application will automatically recreate all 9 relational tables on startup.

---

## 4. Candidate Portal & Network Connectivity

### Candidate Sees SSL / HTTPS Warning
Because the candidate portal runs on a local network IP address (`https://<LAN-IP>:5000`), it uses an auto-generated self-signed RSA-2048 certificate.
- Instruct candidates to click **Advanced → Proceed to Site**.
- This is normal and expected for self-signed certificates on local networks.

### Candidate Cannot Connect from Mobile / Laptop on LAN
1. Verify the host machine's firewall allows inbound TCP traffic on port 5000:
   ```cmd
   netsh advfirewall firewall add rule name="ARS Portal" dir=in action=allow protocol=TCP localport=5000
   ```
2. Verify that both the host PC and the candidate's device are connected to the same Wi-Fi or subnet.
3. Ensure client isolation is disabled on your office or home Wi-Fi router.

---

## 5. HR Desktop Notifications

### Desktop Pop-Up Does Not Appear on Interview Completion
- **Windows Focus Assist / Do Not Disturb:** If Windows Do Not Disturb is enabled, desktop notifications are silenced. Check your Windows Action Center.
- **Notifications Disabled for Python:** Go to **Windows Settings → System → Notifications** and ensure notifications are enabled.
- **Fallback Alert Tray:** Even if OS desktop pop-ups are silenced, the internal alert tray in the top navigation bar will display the unread notification badge and list all completions.

---

## 6. Offline Air-Gap Verification

### Charts Not Rendering Offline
- Confirm that `app/static/js/chart.umd.min.js` exists and is non-empty.
- Verify that `tests/test_airgap.py` passes:
  ```bash
  pytest tests/test_airgap.py -v
  ```
- Ensure the browser is not running in an aggressive script-blocking mode.

---

## 7. AI & Inference Providers

### HTTP 429 Too Many Requests (Cloud Provider)
When using cloud models (Gemini, OpenAI, NVIDIA), provider rate limits may be reached during parallel candidate ranking:
- The system automatically catches 429 errors and falls back to local Ollama.
- To prevent cloud rate limits entirely, switch to **Privacy Mode** in Settings, which runs inference locally on your GPU/CPU via Ollama.

### Ollama Not Responding
1. Verify Ollama is running in your terminal:
   ```bash
   ollama serve
   ```
2. Check available models:
   ```bash
   ollama list
   ```
3. Pull the required model:
   ```bash
   ollama pull llama3.2:3b
   ```
4. Verify the connection endpoint:
   ```bash
   curl http://127.0.0.1:11434/api/tags
   ```
