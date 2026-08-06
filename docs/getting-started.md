# Getting Started

This guide gets a Windows machine ready for development or local operation.

## Requirements

| Requirement | Recommended |
|---|---|
| Windows | Windows 10 or Windows 11 |
| Python | 3.12 |
| Git | Current stable release |
| Ollama | Required for local privacy mode |
| Microphone and webcam | Required for voice interviews and proctoring |

Confirm Python is available:

```bat
python --version
```

## Development Setup

```bat
git clone https://github.com/your-org/AI-Recruitment-System.git
cd AI-Recruitment-System
python -m venv venv
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
python scripts\setup_vosk.py
```

The Tesseract OCR runtime is expected under `models\Tesseract-OCR\`. If it is missing, restore it before processing scanned resumes.

## Launching the App

| Method | Command |
|---|---|
| Silent desktop launch | Double-click `Start.vbs` |
| Console launch | `scripts\run.bat` |
| Direct Python | `python main.py` |

The desktop UI opens through pywebview. The local UI uses an HTTP server on `127.0.0.1`; the candidate portal uses HTTPS.

## First Launch

On first launch, the app creates:

- SQLite database.
- Resume and output directories.
- Self-signed SSL certificate for candidate interviews.
- Runtime config file.

For installed builds, runtime files are stored in:

```text
%LOCALAPPDATA%\AI Recruitment System\
```

## Candidate Access on a Local Network

To expose candidate interviews to another device on the same LAN:

```bat
set ARS_CANDIDATE_HOST=0.0.0.0
python main.py
```

Allow the candidate HTTPS port through Windows Firewall. The default preferred port is `5000`, but the app can use another free port if the preferred one is busy.

## Stopping the App

Close the desktop window. During development, `scripts\kill.bat` can stop lingering Python processes if a previous run did not exit cleanly.
