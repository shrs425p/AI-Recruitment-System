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
│   ├── ars.db                  ← SQLite database (13 relational tables + settings)
│   ├── resumes\                ← Uploaded resume files (.pdf, .docx, .png, .jpg)
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

Always back up both `ars.db` AND `.secret_salt` together — the database and files contain encrypted API keys, candidate PII, and resumes that can only be decrypted with the matching salt.

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

Interview invitation tokens are stored in the dedicated `interview_tokens` SQLite table:

```sql
CREATE TABLE interview_tokens (
    token        TEXT PRIMARY KEY,
    candidate_id TEXT,
    role         TEXT,
    expires_at   TEXT,
    created_at   TEXT,
    used         INTEGER DEFAULT 0
);
```

- When an interview starts, the token is validated against expiry and usage.
- Once completed, the session is recorded in `interview_sessions` and the token is flagged as used (`used = 1`).
- To view active tokens via the command line:
  ```bash
  python -c "import sqlite3; conn = sqlite3.connect(r'%LOCALAPPDATA%\AI Recruitment System\data\ars.db'); print(conn.execute('SELECT token, candidate_id, expires_at, used FROM interview_tokens').fetchall()); conn.close()"
  ```

---

## Candidate Data Purging (GDPR Compliance)

To permanently purge a candidate and all associated PII:
- **UI Action:** Click the **Purge Candidate** button on the candidate profile card.
- **API Endpoint:** Send an authenticated HTTP `DELETE` or `POST` to `/api/candidate/<candidate_id>/purge` with a valid CSRF token.
- **Actions Performed Automatically:**
  1. Deletes the candidate row from `candidates`.
  2. Deletes candidate notes from `candidate_notes`.
  3. Deletes interview sessions from `interview_sessions`.
  4. Deletes active tokens from `interview_tokens`.
  5. Deletes semantic embeddings from `candidate_embeddings`.
  6. Deletes candidate feedback records from `candidate_feedback`.
  7. Unlinks and removes candidate notification records from `hr_notifications`.
  8. Unlinks candidate files: original resume (`.pdf`/`.docx`), parsed `.txt`, NLP profile (`*_nlp.json`), and PDF report from disk.

---

## Database Inspection

The SQLite database (`ars.db`) contains 13 core relational tables:
1. `pipeline_runs`: Pipeline execution history, timestamps, and parameters
2. `candidates`: Extracted candidate profiles, contact info, and scores
3. `schedules`: Scheduled interview slots and status
4. `email_log`: Record of sent emails and dispatch timestamps
5. `interview_tokens`: Candidate interview tokens and expiration
6. `job_templates`: Saved job descriptions and evaluation criteria
7. `app_settings`: Key-value application configurations and encrypted secrets
8. `interview_sessions`: Candidate interview answers, scores, and proctor logs
9. `candidate_embeddings`: 384-dimensional vector embeddings for semantic search
10. `ai_telemetry`: Latency, token usage, and provider telemetry metrics
11. `candidate_feedback`: AI-generated personalized candidate feedback letters
12. `candidate_notes`: Recruiter notes and triage tags
13. `hr_notifications`: Real-time candidate interview completion alerts

To inspect table counts directly:

```bash
python -c "
import sqlite3
conn = sqlite3.connect(r'%LOCALAPPDATA%\AI Recruitment System\data\ars.db')
cursor = conn.cursor()
tables = [r[0] for r in cursor.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()]
for t in tables:
    count = cursor.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
    print(f'{t:22} : {count} rows')
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
