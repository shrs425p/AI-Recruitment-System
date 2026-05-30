# Architecture

This document describes the system architecture, folder structure, module responsibilities, and data flow of the AI Recruitment System.

---

## Overview

The application is a **Flask-backed desktop application** rendered inside a pywebview window. It follows a layered architecture:

```
+-----------------------+
|   pywebview (GUI)     |   Desktop window — renders Flask over localhost
+-----------------------+
|   Flask Routes        |   app/routes/ — HTTP endpoints and page controllers
+-----------------------+
|   Engine Modules      |   src/ — AI, OCR, speech, calendar, reporting
+-----------------------+
|   Data Layer          |   data/ars.db (SQLite) + data/output/ (files)
+-----------------------+
```

Two servers run simultaneously:

| Server | Address | Purpose |
|---|---|---|
| HTTP (local only) | `http://127.0.0.1:5001` | Desktop window (pywebview) |
| HTTPS (LAN) | `https://0.0.0.0:5000` | Candidate interview portal over WiFi |

---

## Folder Structure

```
AI-Recruitment-System/
|
+-- app/                        Flask application package
|   +-- routes/                 Route controller modules (one file per feature)
|   |   +-- auth.py             Login / logout
|   |   +-- dashboard.py        Home dashboard and pipeline status
|   |   +-- upload.py           Resume file upload handler
|   |   +-- nlp.py              NLP extraction trigger and SSE stream
|   |   +-- ranking.py          Candidate ranking trigger
|   |   +-- scheduling.py       Interview slot scheduling and calendar
|   |   +-- interview.py        Candidate token management and session
|   |   +-- reports.py          PDF report generation
|   |   +-- settings.py         Application settings UI and persistence
|   |   +-- logs.py             Live log stream endpoint
|   +-- templates/              Jinja2 HTML templates
|   +-- static/                 CSS, JavaScript, fonts, icons
|   +-- __init__.py             Flask factory (create_app)
|   +-- app_paths.py            Path resolver utility
|   +-- core.py                 Shared state: paths, queue, pipeline_tasks
|   +-- database.py             SQLite helpers and schema initialisation
|   +-- utils.py                login_required decorator, AI call wrappers
|
+-- src/                        Core engine implementations
|   +-- ai_mode.py              Reads APP_MODE from config, selects provider
|   +-- email_sender.py         SMTP email dispatch (Gmail App Password)
|   +-- google_calendar.py      Google Calendar OAuth2 + event creation
|   +-- interview_bot.py        Question generation and answer evaluation
|   +-- nlp_extractor.py        Resume NLP extraction via AI prompt
|   +-- pdf_to_txt.py           PDF / image to plain text (Tesseract OCR)
|   +-- privacy_setup.py        Ollama download and model pull automation
|   +-- provider_router.py      Multi-provider AI fallback routing
|   +-- ranking_engine.py       Candidate scoring against job description
|   +-- report_generator.py     PDF report creation (fpdf2)
|   +-- scheduling.py           Free-slot detection and ICS generation
|   +-- voice_interview.py      Vosk STT + pyttsx3 TTS for voice interviews
|   +-- webcam_proctor.py       Haar/MediaPipe face detection proctoring
|
+-- config/
|   +-- config.py               Central configuration — all runtime settings
|
+-- data/                       Runtime data (gitignored)
|   +-- ars.db                  SQLite database
|   +-- resumes/                Uploaded PDF and image resumes
|   +-- output/
|       +-- txt/                Plain-text converted resumes
|       +-- nlp/                NLP extraction JSON and TXT files
|       +-- ranking/            Ranking score JSON files
|       +-- scheduling/         Schedule JSON and ICS files
|       +-- interviews/         Interview transcript JSON files
|       +-- reports/            Generated PDF reports
|       +-- ssl/                Self-signed TLS certificate
|
+-- models/                     Offline binary dependencies
|   +-- Tesseract-OCR/          Portable Tesseract OCR engine
|   +-- vosk-model-*/           Vosk offline speech recognition model
|
+-- build/                      Build configuration
|   +-- build.spec              PyInstaller specification
|   +-- installer.iss           Inno Setup installer script
|
+-- scripts/                    Utility and launch scripts
|   +-- run.bat                 Launch with console output
|   +-- build_installer.bat     PyInstaller + Inno Setup build script
|   +-- kill.bat                Force-terminate all Python processes
|   +-- setup_firewall.bat      Add Windows Firewall rule for port 5000
|   +-- setup_vosk.py           Download and extract Vosk speech model
|
+-- docs/                       Project documentation (this folder)
+-- notebooks/                  Jupyter notebooks for experimentation
+-- tests/                      Automated test suite
+-- main.py                     Application entry point
+-- requirements.txt            Python package dependencies
+-- Start.vbs                   Silent launcher (double-click to start)
```

---

## Module Responsibilities

### app/app_paths.py

Provides three path resolver functions used throughout the codebase:

| Function | Returns |
|---|---|
| `data_path(relative)` | `<project_root>/data/<relative>` |
| `install_path(relative)` | `<project_root>/<relative>` |
| `resource_path(relative)` | PyInstaller-safe resource path |

When packaged with PyInstaller, `resource_path` resolves to the temp extraction directory (`sys._MEIPASS`).

### app/core.py

Holds shared application state imported by all route modules:

- `OUTPUT_FOLDER` — resolved `data/output/` path
- `APP_DATA_DIR` — resolved `data/` path
- `log_queue` — thread-safe `queue.Queue` for the live log stream
- `pipeline_tasks` — dictionary tracking running pipeline step statuses

### app/database.py

Manages the SQLite schema and all database operations. Tables:

| Table | Purpose |
|---|---|
| `pipeline_runs` | Audit log for each pipeline step execution |
| `candidates` | Extracted candidate records from NLP step |
| `schedules` | Interview schedule entries per run |
| `email_log` | Record of all sent interview invitation emails |
| `interview_tokens` | One-time tokens for candidate interview access |

---

## Data Flow

```
1. HR uploads PDF resumes
        |
        v
   data/resumes/*.pdf

2. pdf_to_txt.py converts each file
        |
        v
   data/output/txt/*.txt

3. nlp_extractor.py sends text to AI model
        |
        v
   data/output/nlp/*_nlp.json   (structured candidate data)
   data/output/nlp/*_nlp.txt    (human-readable summary)

4. ranking_engine.py scores candidates against job description
        |
        v
   data/output/ranking/ranking_scores_<timestamp>.json

5. scheduling.py assigns interview slots, generates ICS files
        |
        v
   data/output/scheduling/schedule_<timestamp>.json
   data/output/scheduling/*.ics

6. interview_bot.py conducts and evaluates interview
        |
        v
   data/output/interviews/interview_<name>_<timestamp>.json

7. report_generator.py creates PDF report
        |
        v
   data/output/reports/report_<name>_<timestamp>.pdf
```

---

## AI Provider Selection

The AI provider is determined at runtime by `APP_MODE` in `config/config.py`:

```
APP_MODE = 'privacy'   ->  Uses Ollama (local inference)
APP_MODE = 'cloud'     ->  Uses provider_router.py to select a cloud API
```

`provider_router.py` iterates enabled cloud providers in order of priority and falls back to the next available provider on failure. See [AI Providers](ai-providers.md) for configuration details.

---

## Threading Model

| Thread | Purpose |
|---|---|
| Main thread | pywebview event loop |
| Flask HTTPS thread (daemon) | Serves port 5000 (LAN interviews) |
| Flask HTTP thread (daemon) | Serves port 5001 (local desktop) |
| Pipeline step threads | One thread per running pipeline step |
| Proctoring thread | Background face detection during interview |

All Flask daemon threads are started before pywebview initialises.
