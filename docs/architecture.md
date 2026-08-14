# Architecture

This document describes how the AI Recruitment System is structured — the runtime servers, the data flow through the pipeline, and how the major components relate to each other.

---

## High-Level Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         Windows Desktop                         │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                   pywebview Window                      │    │
│  │   (native OS frame wrapping an embedded Chromium view)  │    │
│  │                                                         │    │
│  │   http://127.0.0.1:5001  ──────►  Waitress (HTTP)       │    │
│  │                                   HR Dashboard Flask App│    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                 │
│  ┌────────────────────────┐    ┌───────────────────────────┐    │
│  │   SQLite Database      │    │  Flask HTTPS Server       │    │
│  │   ars.db               │    │  (port 5000, 0.0.0.0)     │    │
│  │   (settings, schema)   │    │ Candidate Interview Portal│    │
│  └────────────────────────┘    └──────────────▲────────────┘    │
│                                               │                 │
└───────────────────────────────────────────────│─────────────────┘
                                                │ HTTPS
                                     ┌──────────┴──────────┐
                                     │ Candidate's Browser │
                                     │ (any device on LAN) │
                                     └─────────────────────┘
```

---

## The Two-Server Model

The application runs **two Flask servers simultaneously**, each serving a distinct audience:

### Server 1 — HR Desktop Server (Waitress, HTTP)
- **Host:** `127.0.0.1` (localhost only — never exposed externally)
- **Port:** `5001` (default, configurable via `ARS_DESKTOP_PORT`)
- **Protocol:** HTTP (no TLS needed — loopback traffic only)
- **Serving:** Production WSGI via `Waitress` (8 threads by default)
- **Audience:** HR dashboard only, accessed via the embedded pywebview window
- **Authentication:** Nonce-based desktop login (see [Security](security.md))

### Server 2 — Candidate Interview Portal (Flask, HTTPS)
- **Host:** `0.0.0.0` (all network interfaces — accessible from LAN)
- **Port:** `5000` (default, configurable via `ARS_CANDIDATE_PORT`)
- **Protocol:** HTTPS with a self-signed RSA-2048 certificate (auto-generated on first run)
- **Serving:** Flask development server with `use_reloader=False`
- **Audience:** Candidates accessing from their own devices
- **Authentication:** One-time interview tokens (UUID-based, time-scoped)

Both servers share the **same Flask application instance** (`app = create_app()` in `main.py`), so all route handlers are available on both ports. Access control is enforced at the route level via the `@login_required` and token validation decorators.

---

## Application Startup Sequence

```
main.py
  │
  ├─ 1. sys.excepthook registered (crash.log on unhandled exceptions)
  ├─ 2. create_app() — Flask app factory
  │      ├─ Register error handlers (400, 403, 404, 413, 429, 500)
  │      ├─ protect_hr_routes() — apply @login_required to HR endpoints
  │      ├─ add_security_headers() — after_request hook
  │      ├─ inject_config() — context_processor (cfg available in templates)
  │      └─ Register all route blueprints (auth, dashboard, upload, nlp, ...)
  │
  ├─ 3. init_db() — create/migrate SQLite schema
  ├─ 4. Port allocation — pick_port() finds free ports
  ├─ 5. Thread 1: run_flask_https() — candidate portal (daemon)
  ├─ 6. Thread 2: run_flask_http_local() — HR desktop server (daemon)
  ├─ 7. time.sleep(1) — wait for servers to bind
  ├─ 8. webview.create_window() — open desktop window
  └─ 9. webview.start() — enter GUI event loop (blocking)
```

---

## Component Map

```
┌─────────────────── Flask App (app/) ──────────────────────────┐
│                                                               │
│  routes/upload.py     ← Receives uploaded PDF/image files     │
│  routes/nlp.py        ← Triggers NLP extraction pipeline      │
│  routes/ranking.py    ← Triggers candidate scoring            │
│  routes/scheduling.py ← Manages slots, tokens, .ics files     │
│  routes/interview.py  ← Candidate portal, live session mgmt   │
│  routes/reports.py    ← PDF report generation                 │
│  routes/dashboard.py  ← Dashboard data aggregation            │
│  routes/settings.py   ← Settings CRUD + provider config       │
│  routes/logs.py       ← Live log streaming (SSE)              │
│  routes/auth.py       ← Login, nonce-based desktop auth       │
│  routes/health.py     ← /health endpoint                      │
│                                                               │
└───────────────────────────┬───────────────────────────────────┘
                            │ calls
┌────────────────────────────▼──────────────── Business Logic (src/) ──┐
│                                                                      │
│  pdf_to_txt.py         ← PDF/image → plain text                      │
│  nlp_extractor.py      ← Resume text → structured candidate JSON     │
│  ranking_engine.py     ← Candidates + JD → ranked leaderboard        │
│  scheduling.py         ← Top-N → slots → schedule.json + .ics        │
│  interview_bot.py      ← Questions, answer evaluation, transcripts   │
│  webcam_proctor.py     ← Face detection, violation flags             │
│  voice_interview.py    ← Vosk STT + pyttsx3 TTS                      │
│  report_generator.py   ← interview transcript → PDF report           │
│  provider_router.py    ← Round-robin AI call dispatcher              │
│  google_calendar.py    ← Google Calendar API integration             │
│  email_sender.py       ← SMTP email dispatch                         │
│  security.py           ← AES-Fernet encrypt/decrypt                  │
│  common.py             ← Paths, AI call_ollama(), JSON utils         │
│  ai_mode.py            ← Privacy vs Cloud mode selector              │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow: Resume to Report

```
[1] UPLOAD
  User drops PDF/PNG/JPG into the Upload page
  └─ app/routes/upload.py saves file to:
     %LOCALAPPDATA%\AI Recruitment System\data\resumes\

[2] TEXT EXTRACTION (pdf_to_txt.py)
  For digital PDFs:
    PyMuPDF extracts embedded text directly (fast, ~ms)
    If extracted text < 800 characters → treated as scanned → OCR
  For scanned PDFs / images:
    PyMuPDF renders each page to a 300 DPI PNG
    Tesseract OCR reads the PNG and extracts text
  Output: .txt file in data/output/txt/

[3] NLP EXTRACTION (nlp_extractor.py)
  Reads the .txt file
  Sends to AI with a structured prompt
  AI returns JSON with:
    personal_info, domain, summary, total_experience_years,
    skills (technical, tools, soft, domain-specific, languages),
    education, work_experience, projects, certifications,
    awards, publications, volunteer, candidate_strength_summary
  Output: candidate_nlp.json + candidate_nlp.txt in data/output/nlp/

[4] RANKING (ranking_engine.py)
  HR enters a Job Description
  AI parses JD → extracts requirements (skills, experience, domain, education)
  For each candidate (parallel, up to 5 workers):
    AI scores on 5 criteria with strict rubrics:
      domain_match (20 pts), skills_match (35 pts),
      experience_years (20 pts), education (15 pts), certifications (10 pts)
    Returns score, percentage, strengths, gaps, hire_recommendation
  Candidates sorted by total score descending
  Output: ranking_scores_<timestamp>.json + leaderboard_<timestamp>.json

[5] SCHEDULING (scheduling.py)
  HR selects top N candidates (default: 10) and enters available slots
  For each candidate:
    3 slot options distributed across HR's availability
    .ics calendar invite generated (UUID event ID)
    Interview token generated (UUID, stored in DB)
    Optional: email sent with slot options + interview link
  Output: schedule_<timestamp>.json + per-candidate .ics files

[6] INTERVIEW (interview_bot.py + webcam_proctor.py + voice_interview.py)
  Candidate opens their unique interview URL from their browser
  Token validated → session created
  8 questions generated (5 technical + 3 behavioral, AI-personalised)
  For each question:
    Question displayed (or read via TTS in voice mode)
    Candidate answers (typed or spoken via Vosk STT)
    AI evaluates answer (score + feedback)
    Webcam proctor checks face count every 2 seconds
  Session ends → transcript saved
  Output: interview_<candidate>_<timestamp>.json

[7] REPORT GENERATION (report_generator.py)
  Loads interview transcript JSON
  Generates PDF with:
    Candidate profile summary
    Score breakdown (per question + overall)
    Proctor summary (violations, face detection results)
    Full Q&A transcript
  Output: report_<candidate>_<timestamp>.pdf in data/output/reports/
```

---

## AI Call Architecture

All AI calls in the system go through a single unified dispatcher in `src/common.py`:

```
call_ollama(system_msg, user_msg)
  │
  └─ call_ai_async(system_msg, user_msg)
       │
       ├─ Privacy mode (APP_MODE="privacy"):
       │    call_ollama_async() → local Ollama server
       │    On timeout → cloud fallback (if Anthropic key configured)
       │
       └─ Cloud mode (APP_MODE="cloud"):
            provider_router.router.call()
              │
              └─ ProviderRouter.get_provider()
                   Round-robin across all enabled, non-rate-limited providers
                   Tracks call timestamps per provider (RPM enforcement)
                   Falls back to next provider on rate limit
```

### Provider Router

The `ProviderRouter` class in `src/provider_router.py` manages **load balancing** across up to 8 simultaneous cloud AI providers:

- Maintains a per-provider **call timestamp log** in memory
- Before each call, filters out providers that have exceeded their RPM limit in the last 60 seconds
- Selects the first non-rate-limited provider from the active list
- If all providers are rate-limited, uses the first active one as a fallback
- Validates API keys against known placeholder strings — providers with placeholder keys are automatically skipped

---

## Database Schema

The SQLite database (`ars.db`) is created and managed by `app/database.py`. It uses one primary table for configuration:

### `app_settings`
| Column | Type | Description |
|---|---|---|
| `key` | TEXT (PK) | Setting name (e.g. `NVIDIA_KEY`, `THEME`) |
| `value` | TEXT | Setting value (may be `ENC:...` for encrypted values) |
| `is_encrypted` | INTEGER | `1` if the value is AES-Fernet encrypted |
| `updated_at` | TEXT | ISO timestamp of last update |

All other application state (interview sessions, tokens, proctor data) is stored in-memory during a session and persisted to JSON files in the output directories.

---

## Security Headers

Every HTTP response from the Flask app includes these headers (added by the `add_security_headers` after-request hook):

| Header | Value |
|---|---|
| `Cache-Control` | `no-store` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `X-Content-Type-Options` | `nosniff` |
| `X-Frame-Options` | `SAMEORIGIN` |
