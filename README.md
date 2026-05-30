# AI Recruitment System (ARS)

An end-to-end automated recruitment pipeline that uses artificial intelligence to screen resumes, rank candidates, schedule interviews, conduct AI-driven interviews with voice & webcam proctoring, and generate comprehensive hiring reports. Packaged as a standalone Windows desktop application.

---

## MVP Features

| # | Feature | Description |
|---|---------|-------------|
| 1 | **Resume Upload & Extraction** | Drag-and-drop PDF/PNG/JPG upload; digital PDF text extraction (PyMuPDF) + OCR fallback (Tesseract) for scanned documents |
| 2 | **AI Resume Parsing (NLP)** | Extracts name, email, phone, location, domain, skills, certifications, education, experience, and projects using a local LLM |
| 3 | **AI Candidate Ranking** | Parses job description via AI; scores candidates in parallel across 5 weighted criteria (domain, skills, experience, education, certifications) out of 100 |
| 4 | **Interview Scheduling** | Imports free HR slots from Google Calendar or manual entry; generates 3 time-slot options per candidate; creates `.ics` invite files |
| 5 | **Email Invitations** | Sends HTML + plain-text interview invitations via Gmail SMTP with candidate details and scheduled time |
| 6 | **AI Interview Bot** | Generates 5 technical + 3 behavioral questions per candidate; evaluates answers for relevance, depth, clarity, and correctness |
| 7 | **Voice Interview Mode** | Offline speech-to-text (Vosk) and text-to-speech (pyttsx3); fully private, no cloud dependency |
| 8 | **Webcam Proctoring** | Real-time face detection (MediaPipe + OpenCV fallback); flags no-face (>6s absence) and multi-face events; streams JPEG frames to browser |
| 9 | **Report Generation** | AI post-interview analysis with technical/behavioral assessment, strengths, gaps, risk level, and hire/no-hire recommendation |
| 10 | **Dashboard & Pipeline Tracking** | Step-by-step pipeline progress cards; real-time log streaming (SSE); session/state persistence across runs |
| 11 | **Auth & Token-Based Candidate Access** | HR login (session-based); unique UUID token links for candidates to access their interview page |
| 12 | **Desktop Installer** | PyInstaller → Inno Setup pipeline producing a single Windows `.exe` installer bundling all dependencies |

---

## Architecture Overview

```
 ┌──────────────────────────────────────────────────────────┐
 │           main.py (Flask + pywebview Desktop)            │
 │   20+ routes │ Session auth │ SSE log streaming          │
 └──────────────────────┬───────────────────────────────────┘
                        │
    ┌───────────────────┼───────────────────────┐
    ▼                   ▼                       ▼
 Upload            Pipeline Stages         External Services
 data/resumes/ ┌─────────────────┐      ┌──────────────────┐
               │ 1. pdf_to_txt   │      │ Ollama (local)   │
               │ 2. nlp_extractor│      │ Google Calendar  │
               │ 3. ranking      │      │ Gmail SMTP       │
               │ 4. scheduling   │      │ Tesseract OCR    │
               │ 5. interview    │      │ Vosk STT         │
               │ 6. reports      │      └──────────────────┘
               └────────┬────────┘
                        ▼
           app/database.py → data/ars.db (SQLite)
```

### Pipeline Flow

1. **Upload** — PDFs stored in `data/resumes/`
2. **PDF → Text** — Output to `data/output/txt/`
3. **NLP Extraction** — JSON profiles in `data/output/nlp/`
4. **Ranking** — Leaderboard in `data/output/ranking/`
5. **Scheduling** — Schedules + `.ics` files in `data/output/scheduling/`
6. **Interview** — Transcripts in `data/output/interviews/`
7. **Reports** — Final reports in `data/output/reports/`

---

## How It Works

### 1. Application Startup

- User launches the app (double-click `.exe` or run `Start.vbs`)
- **pywebview** opens a frameless native desktop window pointing to the Flask server
- Flask initializes on a free local port, sets up routes, and starts serving
- **app/database.py** creates/opens `data/ars.db` (SQLite) and ensures all tables exist (`pipeline_runs`, `candidates`, `schedules`, `email_log`, `interview_tokens`)
- Previous session state is restored from `data/output/session_state.json` and `data/output/task_state.json` so the user can resume where they left off
- A logging system with `QueueHandler` is set up for real-time SSE log streaming to the browser

### 2. Login

- If login is enabled in settings, the user is redirected to the **Login** page
- The user enters their HR credentials (username + password)
- Flask validates against stored config values and creates a session cookie
- All subsequent routes check for an active session via a decorator — unauthenticated requests get a 401 redirect

### 3. Resume Upload

**User Experience:** Navigates to the **Upload** page → drags and drops PDF/PNG/JPG resume files (or clicks to browse) → sees file list with names and sizes → clicks "Upload"

**Backend:**
- Files are sent as multipart form data to the `/upload` endpoint
- Flask validates file extensions (PDF, PNG, JPG only) and saves them to `data/resumes/`
- A new `pipeline_run` record is created in the database
- The dashboard pipeline card for "Upload" updates to completed

### 4. PDF to Text Conversion

**User Experience:** Clicks "Convert" on the dashboard or upload page → progress bar shows extraction status per file

**Backend:**
- For each file in `data/resumes/`, the system determines the extraction method:
  - **Digital PDFs** → PyMuPDF (`fitz`) extracts text directly (fast, milliseconds)
  - **Scanned PDFs** → `pdf2image` converts pages to images → Tesseract OCR extracts text
  - **Images (PNG/JPG)** → Pillow loads the image → Tesseract OCR extracts text
- If PyMuPDF returns empty/minimal text, it falls back to OCR automatically
- Extracted text is cleaned and saved as `.txt` files in `data/output/txt/`

### 5. NLP Extraction (AI Resume Parsing)

**User Experience:** Clicks "Extract" → sees real-time progress as each resume is parsed → can view extracted profiles (name, skills, experience, etc.) in a detailed card view

**Backend:**
- For each `.txt` file in `data/output/txt/`, the system sends the resume text to **Ollama** with a structured prompt asking the AI to extract:
  - Name, email, phone, location
  - Professional domain (e.g., "Web Development", "Data Science")
  - Technical skills (list)
  - Certifications
  - Education (degree, institution, year)
  - Work experience (company, role, duration, highlights)
  - Projects
  - Total years of experience
- The AI returns structured JSON, which is parsed (with markdown stripping via `app/utils.py`)
- Each candidate profile JSON is saved to `data/output/nlp/`
- Candidate records are inserted/updated in the `candidates` database table

### 6. AI Candidate Ranking

**User Experience:** Navigates to **Ranking** page → pastes or types the Job Description → clicks "Rank" → sees a leaderboard table with scores and a comparison chart

**Backend:**
- The job description text is first sent to **Ollama** to extract structured requirements (required domain, skills, experience, education, certifications)
- All candidate NLP profiles are loaded from `data/output/nlp/`
- Using a **ThreadPoolExecutor (5 parallel workers)**, each candidate is scored by the AI against the JD across 5 weighted criteria:
  - **Skills Match** — 35 points (highest weight)
  - **Domain Match** — 20 points
  - **Experience Years** — 20 points
  - **Education** — 15 points
  - **Certifications** — 10 points
- The AI provides a score + justification for each criterion; total out of 100
- All scoring explicitly **excludes demographic data** (name, age, gender) for fairness
- Results are sorted by total score → saved as leaderboard JSON + TXT in `data/output/ranking/`
- `candidates.score` is updated in the database

### 7. Interview Scheduling

**User Experience:** Navigates to **Scheduling** page → clicks "Import from Google Calendar" (or manually enters available time slots) → sees a schedule table with 3 offered slots per candidate → can adjust or confirm

**Backend:**
- **Top 10 ranked candidates** are loaded from the ranking results
- If using Google Calendar:
  - OAuth 2.0 flow authenticates the HR user (browser popup on first use; `token.json` stored for subsequent use)
  - The system queries Google Calendar API for free/busy slots over the next **14 days**, filtered to **9 AM – 6 PM IST** work hours in **60-minute intervals**
- If manual entry: HR inputs available date/time slots via the UI form
- Slots are distributed to candidates using a rotation strategy — **3 slot options per candidate**
- For each candidate-slot assignment:
  - An `.ics` calendar invite file is generated using the `icalendar` library
  - Saved to `data/output/scheduling/`
- A master schedule JSON is saved and the `schedules` database table is populated

### 8. Email Invitations

**User Experience:** On the **Interview** page → clicks "Send Invitations" → sees delivery status per candidate (sent/failed)

**Backend:**
- For each scheduled candidate, the system looks up their email from the NLP extraction data
- Connects to **Gmail SMTP** (port 587, TLS) using the configured app password
- Sends an email containing:
  - Candidate's name and the job title
  - Scheduled interview time
  - A unique interview link with a **UUID token** (e.g., `https://host/interview/<token>`)
  - HTML-formatted body with a plain-text fallback
- The `interview_tokens` table stores each token (marked as unused)
- Delivery status is logged in the `email_log` table

### 9. AI Interview

#### HR-Initiated Interview (In-Office)
**User Experience:** On the **Interview** page → selects a candidate → chooses **Text** or **Voice** mode → starts the interview → questions appear one by one → types or speaks answers → sees live webcam feed with proctoring status

#### Candidate Remote Interview (Via Token Link)
**User Experience:** Candidate clicks the unique link from their email → lands on the **Candidate Interview** page → sees rules/instructions → proceeds through questions → webcam is activated for proctoring

**Backend — Question Generation:**
- The candidate's NLP profile (skills, domain, experience) is sent to **Ollama**
- AI generates **5 technical questions** tailored to the candidate's skills/domain + **3 behavioral questions**
- Questions are personalized — a Python developer gets Python questions, a data scientist gets ML questions

**Backend — Answer Collection:**
- **Text mode:** Candidate types answers in a text input; 120-second timer per question
- **Voice mode:**
  - **pyttsx3** reads the question aloud (offline TTS)
  - **Vosk** listens for the candidate's spoken answer (offline STT, Indian English model)
  - Transcribed text is used as the answer

**Backend — Webcam Proctoring:**
- A background thread captures webcam frames via **OpenCV**
- Each frame is analyzed by **MediaPipe** face detection (or **Haar cascade** fallback)
- Proctoring flags are recorded:
  - **No face detected** for more than 6 seconds → "absence" flag with timestamp
  - **Multiple faces detected** → "multi-face" flag with timestamp
- Frames are encoded as JPEG and streamed to the browser in real-time

**Backend — Answer Evaluation:**
- After each answer, the question + answer + candidate context is sent to **Ollama**
- AI scores the answer on 4 dimensions: **relevance**, **depth**, **clarity**, **correctness**
- Each dimension gets a score with reasoning
- Interview session is saved to disk after every answer (survives crashes)
- Full transcript + scores + proctoring flags saved to `data/output/interviews/`

### 10. Report Generation

**User Experience:** Navigates to **Reports** page → clicks "Generate Reports" → sees individual report cards per candidate → views a final **Hiring Summary** table with recommendations

**Backend:**
- For each interviewed candidate, the system loads:
  - NLP profile (skills, experience)
  - Ranking score
  - Interview transcript (all Q&A + scores)
  - Proctoring flags
- All data is sent to **Ollama** for comprehensive analysis
- AI generates a report containing:
  - **Technical Assessment** — strengths and gaps in technical knowledge
  - **Behavioral Assessment** — communication, problem-solving, teamwork
  - **Proctoring Summary** — any flagged events during the interview
  - **Risk Level** — Low / Medium / High
  - **Hire Recommendation** — Hire / No Hire / Consider with reasoning
  - **Combined Score** — 40% resume ranking + 60% interview performance
- Reports are saved in multiple formats: JSON (machine-readable) + TXT (HR-readable) + HTML in `data/output/reports/`
- A final hiring summary aggregates all candidates into a single decision table

### 11. Settings & Configuration

**User Experience:** Navigates to **Settings** page → tabs for General, Ollama, Email, Logs, About

**Available Settings:**
- **General:** Toggle login on/off, change HR credentials, switch light/dark theme, edit HR profile (name, email, company)
- **Ollama:** Configure AI model name and base URL
- **Email:** Set SMTP host, port, sender email, and app password
- **Logs:** View and clear application logs
- **About:** System info, version, and project details

All settings are persisted to `config/config.py` and take effect immediately.

### 12. Real-Time Log Streaming

**User Experience:** Opens the **Logs** page → sees a live-updating console of all backend activity

**Backend:**
- Python's logging module is configured with a `QueueHandler` that pushes log entries into a thread-safe queue
- The `/stream-logs` Flask endpoint uses **Server-Sent Events (SSE)** — a persistent HTTP connection
- The browser's `EventSource` API connects to this endpoint
- As log entries are produced (file processing, AI calls, scoring, errors), they're streamed to the browser in real-time with no polling

---

## Tech Stack

### Backend

| Technology | Purpose |
|------------|---------|
| **Python 3.x** | Core language |
| **Flask 3.0+** | Web framework (20+ routes, API endpoints) |
| **pywebview 5.0+** | Native desktop window wrapper (frameless) |
| **SQLite3** | Database (WAL mode, foreign keys) |
| **Jinja2** | HTML templating (built into Flask) |

### AI & Machine Learning

| Technology | Purpose |
|------------|---------|
| **Ollama** | Local LLM inference (cogito model) — resume parsing, ranking, question generation, answer evaluation, report generation |
| **Vosk** | Offline speech-to-text (Apache 2.0, Indian English model) |
| **pyttsx3** | Offline text-to-speech (system TTS engine) |
| **MediaPipe** | Face detection for webcam proctoring |
| **OpenCV (cv2)** | Webcam capture, Haar cascade face detection fallback, frame encoding |

### PDF & OCR

| Technology | Purpose |
|------------|---------|
| **PyMuPDF (fitz)** | Direct text extraction from digital PDFs |
| **Tesseract OCR** | Text extraction from scanned PDFs/images (bundled binary) |
| **pytesseract** | Python wrapper for Tesseract |
| **pdf2image** | PDF to image conversion (for OCR pipeline) |
| **Pillow** | Image processing |
| **fpdf2** | PDF report generation |

### Frontend

| Technology | Purpose |
|------------|---------|
| **HTML5** | 14 Jinja2 templates (dashboard, upload, NLP, ranking, scheduling, interview, reports, settings, logs, etc.) |
| **Custom CSS** | ~3000+ line design system — light/dark themes, glassmorphism, cards, modals, score bars, sidebar (DM Sans / DM Mono fonts) |
| **Vanilla JavaScript** | Toast notifications, fetch API, SSE log streaming, drag-and-drop upload, Canvas charts, interview mode toggles |
| **Server-Sent Events** | Real-time backend log streaming to browser |

### APIs & External Services

| Service | Purpose | Auth Method |
|---------|---------|-------------|
| **Ollama (localhost:11434)** | All AI inference | None (local) |
| **Google Calendar API** | Free slot import, event creation | OAuth 2.0 (token.json) |
| **Gmail SMTP** | Interview invitation emails | App password, TLS (port 587) |
| **Tesseract OCR** | Scanned document processing | Bundled binary |

### Build & Deployment

| Tool | Purpose |
|------|---------|
| **PyInstaller** | Python → `.exe` compilation (build.spec) |
| **Inno Setup 6** | `.exe` → Windows installer (installer.iss) |
| **build_installer.bat** | Automated build pipeline script |
| **run.bat** | Development launcher |
| **kill.bat** | Process terminator |
| **setup_vosk.py** | Vosk model downloader |

---

## Python Dependencies

```
Flask >= 3.0
pywebview >= 5.0
ollama >= 0.1.7
pytesseract >= 0.3.10
Pillow >= 10.0
pdf2image >= 1.17
PyMuPDF >= 1.23
fpdf2 >= 2.7
pyttsx3 >= 2.90
SpeechRecognition >= 3.10
vosk >= 0.3
mediapipe >= 0.10
opencv-python >= 4.9
icalendar >= 5.0
google-api-python-client >= 2.100
google-auth-httplib2 >= 0.2
google-auth-oauthlib >= 1.1
```

**Standard Library (used extensively):** sqlite3, json, re, pathlib, datetime, threading, queue, logging, uuid, socket, ssl, ipaddress, concurrent.futures

---

## Database Schema (SQLite)

| Table | Purpose |
|-------|---------|
| `pipeline_runs` | Tracks pipeline executions (id, run_type, date, status, metadata) |
| `candidates` | Candidate data (name, email, source file, score, skills JSON) |
| `schedules` | Interview assignments (candidate, job, rank, slots JSON, status) |
| `email_log` | Email delivery tracking (recipient, subject, status, error) |
| `interview_tokens` | Unique token links for candidate interview access |

---

## Scoring System

| Criteria | Weight |
|----------|--------|
| Skills Match | 35 pts |
| Domain Match | 20 pts |
| Experience Years | 20 pts |
| Education | 15 pts |
| Certifications | 10 pts |
| **Total** | **100 pts** |

---

## Configuration Defaults

| Setting | Value |
|---------|-------|
| AI Model | `cogito-2.1:671b-cloud` |
| Ollama URL | `http://localhost:11434` |
| Technical Questions | 5 per candidate |
| Behavioral Questions | 3 per candidate |
| Answer Time Limit | 120 seconds |
| Top Candidates Scheduled | 10 |
| Slots per Candidate | 3 |
| Interview Duration | 60 minutes |
| Calendar Lookahead | 14 days |
| Work Hours | 9 AM – 6 PM IST |
| Theme | Light (dark mode available) |

---

## Security

| Feature | Implementation |
|---------|---------------|
| HR Login | Session-based authentication (Flask sessions) |
| Candidate Access | Unique UUID token links (single-use) |
| Google Auth | OAuth 2.0 with auto-refresh tokens |
| Email Auth | App password + TLS encryption |
| Data Privacy | Fully offline AI (Ollama + Vosk) — no data leaves the machine |
| Database | WAL journaling, foreign keys enforced |

---

## Key Technical Highlights

- **Fully Offline AI** — Local LLM via Ollama, no cloud API calls
- **Privacy-First Voice** — Vosk speech recognition (Apache 2.0, no cloud)
- **Live Webcam Proctoring** — Real-time face detection streamed to browser
- **Parallel Scoring** — ThreadPoolExecutor with 5 workers for candidate ranking
- **Single-File Installer** — PyInstaller + Inno Setup for Windows distribution
- **Google Calendar Integration** — OAuth 2.0 with bulk event creation
- **Real-Time Logs** — Server-Sent Events for live backend activity
- **Multi-Mode Interview** — Text input or voice-based (TTS + STT)
- **Proctoring Flags** — No-face detection, multi-face detection with timestamp logging

---

## Project Structure

```
AI-Recruitment-System/
├── main.py                  # Main desktop entry (Flask + pywebview wrapper)
├── pyproject.toml           # Modern python packaging & tool configuration (Ruff/pytest)
├── requirements.txt         # Production dependencies
├── requirements-dev.txt     # Development and testing tools
├── Start.vbs                # One-click background launcher
├── LICENSE                  # MIT License
├── README.md                # System documentation
│
├── app/                     # Flask Web Application Layer
│   ├── __init__.py          # Flask app creator & initializer
│   ├── core.py              # Blueprint registrations, route setup, configuration loading
│   ├── app_paths.py         # Dynamic OS-independent database and directory path resolver
│   ├── database.py          # SQLite database wrapper (schema initialization & WAL mode)
│   ├── utils.py             # Custom markdown/JSON utility parsers
│   ├── routes/              # Sub-handlers for each module
│   │   ├── auth.py          # Session authentication routes
│   │   ├── dashboard.py     # SSE logging & pipeline controller
│   │   ├── nlp.py           # NLP parse handlers
│   │   ├── ranking.py       # Candidate evaluation endpoints
│   │   ├── scheduling.py    # Google Calendar & scheduling routes
│   │   ├── interview.py     # Live stateful interview flows
│   │   ├── reports.py       # Hiring report rendering
│   │   └── settings.py      # App configuration updates
│   ├── templates/           # 14 Jinja2 HTML templates for the dashboard & candidates
│   └── static/              # Premium custom stylesheets and Javascript files
│
├── src/                     # Core Business Logic & Pipelines
│   ├── pdf_to_txt.py        # PDF extraction & Tesseract OCR fallback
│   ├── nlp_extractor.py     # Structured candidate profiling (Ollama)
│   ├── ranking_engine.py    # Parallel multi-criteria scorer (ThreadPoolExecutor)
│   ├── scheduling.py        # Time slot allocator
│   ├── interview_bot.py     # Stateful interview conductor & answer evaluator
│   ├── voice_interview.py   # Vosk offline STT & pyttsx3 offline TTS engine
│   ├── webcam_proctor.py    # MediaPipe real-time face detection tracker
│   ├── report_generator.py  # Comprehensive report writer
│   ├── email_sender.py      # SMTP invite mailer
│   ├── google_calendar.py   # Google Calendar OAuth 2.0 interface
│   ├── provider_router.py   # Load-balancing model router
│   └── ai_mode.py           # Ollama check and routing setup
│
├── config/                  # Configuration Layer
│   └── config.py            # Active settings file (overwritten dynamically via Settings UI)
│
├── data/                    # Local Storage Directory
│   ├── ars.db               # SQLite database file
│   ├── resumes/             # Raw candidate resume documents
│   └── output/              # Pipeline stage outputs
│       ├── txt/             # Extracted plain text
│       ├── nlp/             # AI candidate profiles (JSON)
│       ├── ranking/         # Leaderboard scoring results
│       ├── scheduling/      # Calendar invitations (.ics) and schedule configurations
│       ├── interviews/      # Voice/text transcripts with answer scoring
│       └── reports/         # HTML/TXT report summaries
│
└── tests/                   # Test suite for components & APIs
```
