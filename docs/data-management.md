# Data Management

This document covers how to back up, restore, clear, and manage the data the system stores during operation.

---

## Where Data Is Stored

All runtime data lives in:
```
%LOCALAPPDATA%\AI Recruitment System\
```

On a typical Windows installation this is:
```
C:\Users\<YourName>\AppData\Local\AI Recruitment System\
```

### Full Directory Structure

```
AI Recruitment System\
│
├── data\
│   ├── ars.db                  ← SQLite database (all settings)
│   ├── resumes\                ← Uploaded resume files (PDF, PNG, JPG)
│   ├── credentials.json        ← Google Calendar OAuth credentials (if set up)
│   ├── token.json              ← Google Calendar OAuth token (auto-generated)
│   └── output\
│       ├── txt\                ← Plain text extracted from resumes
│       ├── nlp\                ← NLP JSON + TXT profiles (one per candidate)
│       ├── ranking\            ← Ranked leaderboard JSON files
│       ├── scheduling\         ← Schedule JSON + .ics calendar invites
│       ├── interviews\         ← Interview transcript JSON files
│       ├── reports\            ← Generated PDF reports + report JSON
│       └── ssl\                ← Auto-generated TLS certificate (cert.pem, key.pem)
│
└── .secret_salt                ← Encryption salt (do not delete or move)
```

---

## Backing Up

### Full Backup

Copy the entire `AI Recruitment System` folder:
```bat
xcopy "%LOCALAPPDATA%\AI Recruitment System" "D:\Backup\ARS-%date%" /E /I /H
```

This backs up settings, all data files, and the encryption salt.

### Settings Only Backup

```bat
copy "%LOCALAPPDATA%\AI Recruitment System\data\ars.db" "D:\Backup\ars_backup.db"
copy "%LOCALAPPDATA%\AI Recruitment System\.secret_salt" "D:\Backup\.secret_salt"
```

Always back up both `ars.db` AND `.secret_salt` together — the database contains encrypted API keys that can only be decrypted with the matching salt.

### Resume and Output Files Backup

```bat
xcopy "%LOCALAPPDATA%\AI Recruitment System\data\resumes" "D:\Backup\resumes" /E /I
xcopy "%LOCALAPPDATA%\AI Recruitment System\data\output" "D:\Backup\output" /E /I
```

---

## Restoring

### Restore to the Same Machine

Replace the data folder with your backup:
```bat
xcopy "D:\Backup\ARS-<date>" "%LOCALAPPDATA%\AI Recruitment System" /E /I /H /Y
```

### Restore to a Different Machine

1. Install the app on the new machine (run through first launch once to create the directory structure)
2. Stop the app
3. Copy your backup files:
   ```bat
   copy "D:\Backup\ars_backup.db" "%LOCALAPPDATA%\AI Recruitment System\data\ars.db"
   copy "D:\Backup\.secret_salt"  "%LOCALAPPDATA%\AI Recruitment System\.secret_salt"
   ```
4. Copy output folders if needed
5. Restart the app — all settings and API keys will be intact

> **Important:** The `.secret_salt` file MUST match the `ars.db` file. If they don't match, encrypted values (API keys, passwords) will not decrypt correctly and will appear blank in Settings.

---

## Clearing Data

### Clear Resumes and Pipeline Output (Keep Settings)

To start a fresh recruitment run without losing your settings and API keys:

```bat
del /Q "%LOCALAPPDATA%\AI Recruitment System\data\resumes\*"
del /Q "%LOCALAPPDATA%\AI Recruitment System\data\output\txt\*"
del /Q "%LOCALAPPDATA%\AI Recruitment System\data\output\nlp\*"
del /Q "%LOCALAPPDATA%\AI Recruitment System\data\output\ranking\*"
del /Q "%LOCALAPPDATA%\AI Recruitment System\data\output\scheduling\*"
del /Q "%LOCALAPPDATA%\AI Recruitment System\data\output\interviews\*"
del /Q "%LOCALAPPDATA%\AI Recruitment System\data\output\reports\*"
```

Or from PowerShell:
```powershell
$base = "$env:LOCALAPPDATA\AI Recruitment System\data"
Remove-Item "$base\resumes\*" -Force
Remove-Item "$base\output\txt\*" -Force
Remove-Item "$base\output\nlp\*" -Force
Remove-Item "$base\output\ranking\*" -Force
Remove-Item "$base\output\scheduling\*" -Force
Remove-Item "$base\output\interviews\*" -Force
Remove-Item "$base\output\reports\*" -Force
```

### Reset Settings (Wipes Everything Including API Keys)

```bat
del "%LOCALAPPDATA%\AI Recruitment System\data\ars.db"
del "%LOCALAPPDATA%\AI Recruitment System\.secret_salt"
```

The next launch recreates the database with default settings. You will need to re-enter all API keys.

### Complete Reset

```bat
rmdir /s /q "%LOCALAPPDATA%\AI Recruitment System"
```

The next launch creates a fresh installation.

---

## Managing Resumes

### Re-uploading a Resume

If you re-upload a resume with the same filename, it **does not overwrite** the existing file — rename it first (e.g. `john_doe_v2.pdf`) if you want to re-process it.

The NLP extractor skips already-processed files. To force re-extraction:
1. Delete the corresponding `*_nlp.json` from `data/output/nlp/`
2. Delete the corresponding `.txt` from `data/output/txt/`
3. Re-run NLP extraction

### Removing a Candidate from Ranking

To exclude a candidate from the next ranking run:
1. Delete their `*_nlp.json` from `data/output/nlp/`
2. Re-run ranking

---

## Managing Interview Tokens

Tokens are stored in the `app_settings` table as a JSON blob. There is no built-in token management UI — to revoke or clear tokens manually:

1. Open the database with SQLite browser or from the command line:
   ```bash
   python -c "from app.database import get_setting, set_setting; print(get_setting('interview_tokens', '[]'))"
   ```
2. Tokens expire naturally when the interview is completed. Incomplete tokens remain until the database is cleared.

---

## Database Inspection

To inspect the database directly:

```bash
python -c "
import sqlite3, json
conn = sqlite3.connect(r'%LOCALAPPDATA%\AI Recruitment System\data\ars.db')
rows = conn.execute('SELECT key, value, is_encrypted FROM app_settings').fetchall()
for key, val, enc in rows:
    if enc:
        print(f'{key}: [ENCRYPTED]')
    else:
        print(f'{key}: {val}')
conn.close()
"
```

Or use a GUI tool like **DB Browser for SQLite** ([sqlitebrowser.org](https://sqlitebrowser.org)).

---

## Log Files

| Log | Location |
|---|---|
| Crash log | `%LOCALAPPDATA%\AI Recruitment System\crash.log` |
| Live app log | Visible in the app UI under Sidebar → Logs |

Crash logs are written only when the app exits unexpectedly. They contain the full Python traceback. Clear them manually:
```bat
del "%LOCALAPPDATA%\AI Recruitment System\crash.log"
```
