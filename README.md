# AI Recruitment System

AI Recruitment System is a Windows desktop application for managing a complete recruitment pipeline: resume intake, OCR/text extraction, AI profile parsing, candidate ranking, scheduling, interviews, proctoring, and post-interview reports.

The app is built with Flask and pywebview, stores data locally in SQLite, and supports privacy-first AI through Ollama. Cloud AI providers can be enabled explicitly from Settings when needed.

## Highlights

| Area | Capability |
|---|---|
| Resume intake | Upload PDF, PNG, JPG, and JPEG resumes |
| Extraction | PyMuPDF for digital PDFs, Tesseract OCR for scans and images |
| AI parsing | Structured candidate profiles from resume text |
| Ranking | Job-description-based scoring and leaderboard generation |
| Scheduling | Slot assignment, ICS generation, Google Calendar integration |
| Interviews | Token-based candidate portal with text or voice answers |
| Security | Candidate API rate limiting, global error middleware, session TTL |
| Proctoring | Browser integrity checks and webcam face detection |
| Reports | AI-assisted hiring reports and final summaries |
| Production | Pre-flight environment diagnostics, SQLite WAL + busy timeout |
| Packaging | PyInstaller folder build and Inno Setup installer |

## One-Click Pipeline

The dashboard includes an Auto-Pipeline action that runs the operational stages in sequence:

```text
Resume files -> Text extraction -> NLP profiles -> Ranking -> Scheduling -> Reports
```

The interview itself remains candidate-driven because it requires live answers and proctoring. Once completed interview transcripts exist, reports are generated automatically by the pipeline.

## Quick Start

```bat
python -m venv venv
call venv\Scripts\activate.bat
pip install -r requirements.txt
python scripts\setup_vosk.py
python main.py
```

For normal desktop use, double-click `Start.vbs` or run `scripts\run.bat`.

## Installed App Behavior

Production builds do not ship a developer `config.py`. On first launch, the app creates a clean runtime config under the current user's local app-data folder:

```text
%LOCALAPPDATA%\AI Recruitment System\
```

This prevents test credentials, local paths, and development data from being bundled into the installer.

## Documentation

The full documentation is split by topic:

| Document | Purpose |
|---|---|
| [Documentation Index](docs/index.md) | Start here for role-based navigation |
| [Getting Started](docs/getting-started.md) | Install, launch, and first-run setup |
| [Pipeline Guide](docs/pipeline.md) | Manual and automatic pipeline behavior |
| [Configuration](docs/configuration.md) | Runtime settings and environment overrides |
| [Architecture](docs/architecture.md) | Modules, data flow, threading, and paths |
| [AI Providers](docs/ai-providers.md) | Ollama and cloud provider setup |
| [Interview System](docs/interview-system.md) | Candidate tokens, voice mode, and proctoring |
| [Google Calendar](docs/google-calendar.md) | OAuth setup and calendar event creation |
| [API Reference](docs/api-reference.md) | Flask endpoints and response shapes |
| [Build and Deploy](docs/build-and-deploy.md) | PyInstaller and Inno Setup release process |
| [Theming](docs/theming.md) | UI palette and theme customization |
| [Troubleshooting](docs/troubleshooting.md) | Common failures and fixes |
| [Changelog](docs/changelog.md) | Release notes |

## Build Installer

`scripts\build_installer.bat` builds both outputs:

1. `dist\ARS\ARS.exe` through PyInstaller.
2. `ARS_Setup_*.exe` through Inno Setup.

To write the installer to Downloads:

```bat
set ARS_INSTALLER_OUTPUT=%USERPROFILE%\Downloads
scripts\build_installer.bat
```

## Development Checks

```bat
venv\Scripts\python.exe scripts\verify_environment.py
venv\Scripts\python.exe -m ruff check .
venv\Scripts\python.exe -m pytest
venv\Scripts\python.exe -m compileall -q main.py app src tests
```

Optional release checks:

```bat
venv\Scripts\python.exe -m pip_audit -r requirements.txt
venv\Scripts\python.exe -m bandit -q -r app src main.py -x venv,build,dist -ll
```

## License

This project is released under the MIT License. See [LICENSE](LICENSE).
