# Changelog

All notable changes to the AI Recruitment System are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).  
Versioning follows [Semantic Versioning](https://semver.org/).

---

## [1.0.0] — 2026-05-30

### Added

**Core Pipeline**
- Six-step recruitment pipeline: Upload, PDF-to-Text, NLP Extraction, AI Ranking, Scheduling, Interview.
- Pipeline task status tracking with live progress indicators on the dashboard.
- Idempotent step execution — already-processed files are skipped on re-run.
- Manual step-by-step mode and automatic Run All mode for steps 2–4.

**AI Integration**
- Privacy mode: fully offline AI inference via Ollama (`llama3.2:3b` default).
- Cloud mode: multi-provider fallback chain (Anthropic, Gemini, Groq, OpenAI, NVIDIA, OpenRouter, GitHub, Ollama Cloud).
- Configurable retry logic with exponential backoff (`AI_RETRY_ATTEMPTS`, `AI_RETRY_BACKOFF`).
- Provider router with priority-ordered fallback on API errors or timeouts.
- Automatic Ollama installer and model pull via the Settings UI.

**Resume Processing**
- PDF to plain text conversion with PyMuPDF (digital PDFs) and Tesseract OCR (scanned PDFs and images).
- Portable Tesseract OCR binary bundled at `models/Tesseract-OCR/` — no system install required.
- Support for PDF, PNG, JPG, and JPEG resume formats.
- NLP extraction of 14 structured fields including skills, education, work experience, projects, and certifications.
- Atomic file write strategy for NLP output — no partial files on failure.
- Domain and industry auto-detection across all professional fields.

**Candidate Ranking**
- AI-driven scoring against a recruiter-provided job description.
- Five-dimension scoring rubric: skills match, experience, education, domain fit, achievements.
- Ranked JSON output with per-candidate scores and AI reasoning.

**Interview Scheduling**
- Slot assignment engine distributing top-N candidates across HR-provided time slots.
- ICS file generation for each confirmed candidate.
- Google Calendar OAuth2 integration with automatic event creation.
- Free-slot detection by scanning HR's Google Calendar for availability.
- Per-candidate slot override from the Scheduling UI.

**Interview System**
- One-time cryptographic interview tokens for each candidate.
- Candidate-facing interview portal accessible over HTTPS on the local network.
- Dynamic AI question generation per candidate (technical + behavioural).
- Real-time answer evaluation with 10-point rubric per question.
- Voice interview mode using Vosk offline STT and pyttsx3 TTS.
- Browser-level proctoring: tab switch, copy-paste, and full-screen exit detection.
- Webcam proctoring: face detection using MediaPipe Face Mesh with Haar cascade fallback.
- Interview transcript storage in JSON format with full question-answer-score records.

**Reporting**
- Automated PDF report generation per candidate using fpdf2.
- Report includes ranking score, interview performance, proctoring status, and AI-written evaluation.

**Notifications**
- Gmail SMTP email dispatch for interview invitations.
- Configurable sender address and App Password.

**Settings and Configuration**
- All settings editable from the Settings UI — persisted immediately to `config/config.py`.
- HR profile (display name, email, company).
- AI provider and model selection per provider.
- UI theme (light/dark) and colour palette (lavender, sage, blue, rose).
- Login system with configurable HR username and password.

**User Interface**
- Material Design 3-inspired design system with CSS custom properties.
- Light and dark modes with immediate toggle.
- Four colour palettes: Lavender, Organic Sage, Slate Blue, Terracotta Rose.
- Frameless pywebview window with custom title bar and window controls.
- Live log stream on the Logs page using Server-Sent Events.
- Candidate interview portal with voice, webcam, and text input modes.

**Infrastructure**
- Dual-server architecture: HTTP on port 5001 (desktop), HTTPS on port 5000 (LAN interviews).
- Self-signed SSL certificate generated on first launch.
- SQLite database with six tables: pipeline_runs, candidates, schedules, email_log, interview_tokens, and sqlite_sequence.
- Thread-safe log queue for live log streaming across Flask routes.
- pywebview JS API bridge for native window control from JavaScript.

**Build and Distribution**
- PyInstaller single-folder build (`dist/ARS/`).
- Inno Setup installer packaging Tesseract, Vosk model, config, and application bundle.
- Automated build script (`scripts/build_installer.bat`).

**Project Structure**
- Modular folder layout: `app/`, `src/`, `config/`, `data/`, `models/`, `build/`, `scripts/`, `docs/`, `notebooks/`, `tests/`.
- All runtime write paths consolidated under `data/`.
- Offline models consolidated under `models/`.
- Build configurations consolidated under `build/`.
- Utility and launch scripts consolidated under `scripts/`.
- Full documentation suite in `docs/` (12 files).

---

## Planned

The following features are planned for future releases:

| Feature | Target Version |
|---|---|
| Multi-language resume support | 1.1.0 |
| Bulk email dispatch with per-candidate interview links | 1.1.0 |
| Dashboard analytics charts (conversion rate, score distributions) | 1.1.0 |
| Configurable interview question count and categories | 1.1.0 |
| Export ranking and schedule data to CSV and Excel | 1.2.0 |
| REST API authentication (API key header) | 1.2.0 |
| PostgreSQL support as an alternative to SQLite | 2.0.0 |
| Containerised deployment (Docker) | 2.0.0 |
| Multi-HR-user support with role-based access control | 2.0.0 |
