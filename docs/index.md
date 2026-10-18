# AI Recruitment System — Documentation

> **Platform:** Windows 10/11  
> **Stack:** Python · Flask · pywebview · SQLite · Tesseract OCR · OpenCV · MediaPipe

---

## What Is It?

The **AI Recruitment System (ARS)** is an offline-capable desktop application that automates the recruitment pipeline — from uploading resumes and extracting structured candidate profiles to candidate ranking, proctored live interviews, and talent intelligence analytics.

It operates with a two-server model:
1. **Desktop HR Application (`http://127.0.0.1:5001`):** Hosted locally via Waitress and rendered within a native OS desktop window powered by `pywebview`.
2. **Candidate Interview Portal (`https://<host-ip>:5000`):** An isolated, token-authenticated HTTPS server accessible to candidates across the local network without granting access to HR dashboards.

---

## Key Features

| Feature | Details |
|---|---|
| **Resume Ingestion** | Microsoft Word (`.docx`), PDF (digital and scanned), PNG, JPG |
| **Document & OCR Parsing** | `python-docx` for `.docx`, `pypdf` for text PDFs, bundled Tesseract OCR for scanned documents and images |
| **NLP Profile Extraction** | Structured JSON schema: skills, experience, education, projects, certifications, domain |
| **Candidate Ranking** | 5-criterion weighted AI scoring against any job description, with automatic weight balancing and knockouts |
| **Recruiter Notes & Tags** | In-place recruiter notes and status tagging saved directly in SQLite |
| **CSV / Excel Export** | Single-click RFC 4180 candidate spreadsheet export for ATS integration and offline reviews |
| **Interview Scheduling** | Top-N shortlist, slot coordination, `.ics` calendar invites, Google Calendar sync |
| **Candidate Interview Portal** | Isolated HTTPS server, token authentication, and candidate privacy consent |
| **Configurable Interviews** | Customizable technical question count, behavioral question count, and per-question timers in Settings |
| **Adaptive Interview Engine** | Role-adaptive blueprints (`is_tech_role`), dynamic follow-up probing for vague or shallow answers |
| **Real-Time HR Notifications** | Automated desktop notifications and dashboard alert tray upon candidate interview completion |
| **Voice Mode** | Offline HTML5 Web Speech API (`SpeechSynthesis` + `SpeechRecognition`) with backend fallback |
| **Webcam Proctoring** | Real-time face detection (MediaPipe + OpenCV Haar cascade fallback) |
| **Violation Tracking** | Tab switches, copy-paste events, face absence, multiple faces, response delays |
| **Report Generation** | Material Design 3 monochrome PDF reports with rubrics, full transcripts, and proctoring summary |
| **Talent Intelligence Suite** | Vector semantic search, candidate comparison matrix, AI feedback letters, and 6 visual analytics modules |
| **100% Air-Gapped Clean** | Local font assets (Inter, JetBrainsMono) and local Chart.js bundle with zero outbound CDN calls |
| **Multi-Provider AI** | 8 cloud providers plus local Ollama, with round-robin load balancing and automatic fallback |
| **Privacy Mode** | Fully offline execution: Ollama local LLM, zero network egress |
| **Encrypted Storage** | API credentials, candidate PII in database, and uploaded resumes encrypted at rest (AES-Fernet + PBKDF2) |

---

## Documentation Index

| Document | Description |
|---|---|
| [Getting Started](getting-started.md) | Installation, first run, prerequisites, and initial setup |
| [Architecture](architecture.md) | System design, two-server model, subsystem boundaries, data flow |
| [Pipeline](pipeline.md) | Step-by-step recruitment workflow from upload to final evaluation |
| [Talent Intelligence](talent-intelligence.md) | Vector semantic search, candidate comparison matrix, feedback letters, and 6 talent analytics modules |
| [Air-Gapped Operation](airgap.md) | Zero-outbound CDN architecture, bundled fonts, local Chart.js, and offline deployment |
| [Interview System](interview-system.md) | Token authentication, question generation, adaptive probing, voice, proctoring |
| [Reports](reports.md) | Report layout, combined score calculation, PDF exports, and HR completion notifications |
| [Configuration](configuration.md) | Database-backed settings reference, default values, and environment variables |
| [AI Providers](ai-providers.md) | Cloud vs Privacy mode, provider setup, model selection |
| [Security](security.md) | Authentication, encryption at rest, HTTPS, rate limiting, sessions |
| [API Reference](api-reference.md) | Complete reference of all HTTP endpoints, headers, and request/response schemas |
| [Testing](testing.md) | Test suite architecture, running tests (140 tests), and domain modules |
| [Google Calendar](google-calendar.md) | OAuth integration and automatic calendar invite sync |
| [Email Setup](email-setup.md) | SMTP configuration and invitation templates |
| [Data Formats](data-formats.md) | JSON schemas and SQLite database tables |
| [Customization](customization.md) | Tunable parameters (weights, thresholds, question limits) |
| [Data Management](data-management.md) | Backup, restore, and data cleanup procedures |
| [Deployment](deployment.md) | Building the portable executable and Inno Setup Windows installer |
| [Troubleshooting](troubleshooting.md) | Diagnostic steps and fixes for common runtime issues |
| [FAQ](faq.md) | Frequently asked questions |
| [Contributing](contributing.md) | Code conventions, architecture invariants, and contribution guidelines |

---

## Technology Stack

### Core Runtime
| Layer | Technology |
|---|---|
| Desktop Shell | `pywebview` 5.x — native OS window wrapping a web view |
| Web Framework | `Flask` — serves both HR dashboard and candidate portal |
| Local WSGI Server | `Waitress` — production WSGI server for the desktop UI (`127.0.0.1:5001`) |
| Candidate Server | Flask dev server with self-signed TLS (`0.0.0.0:5000`) |
| Database | `SQLite` via transactional ORM layer (`app/database.py`) |
| Configuration | Database-backed dynamic config module (`config/__init__.py`) |

### AI, NLP & Parsing
| Component | Technology |
|---|---|
| Local LLM | `Ollama` (`llama3.2:3b` default) |
| Cloud Providers | NVIDIA NIM, OpenAI, Anthropic, Google Gemini, Groq, OpenRouter, GitHub Models, Ollama Cloud |
| Word Document Extraction | `python-docx` — native `.docx` XML parsing |
| Digital PDF Parsing | `pypdf` — digital PDF stream text extraction |
| Scanned Document OCR | `Tesseract OCR` (bundled in `models/Tesseract-OCR/`) |
| Voice STT | HTML5 Web Speech API (`SpeechRecognition`) with backend fallback |
| Voice TTS | HTML5 Web Speech API (`SpeechSynthesis`) with backend fallback |

### Proctoring & Vision
| Component | Technology |
|---|---|
| Face Detection (primary) | `MediaPipe` face detection |
| Face Detection (fallback) | OpenCV Haar cascade (`haarcascade_frontalface_default.xml`) |
| Webcam Capture | `OpenCV (cv2)` |

### Security & Cryptography
| Component | Technology |
|---|---|
| Credential & Data Encryption | `cryptography` — AES-Fernet with PBKDF2-HMAC-SHA256 key derivation |
| CSRF Protection | Scoped CSRF token validation (`X-CSRF-Token` header) |
| Password Hashing | `werkzeug.security` — scrypt-based password hashing |
| Desktop Auth | Single-use cryptographically random nonce pool |
| TLS | Self-signed RSA-2048 certificate (10-year validity) |
| Rate Limiter | Thread-safe in-memory sliding window rate limiter |
| Sandboxing | Strict XML containment tags against prompt injection attacks |

### Reporting & Visualization
| Component | Technology |
|---|---|
| PDF Reports | `fpdf2` (Material Design 3 monochrome format) |
| Charting & Visuals | Bundled `chart.umd.min.js` (zero external CDN dependency) |
| Typography | Bundled Inter and JetBrainsMono fonts |
| Calendar Invites | `icalendar` (`.ics` files) |
| Google Calendar | `google-api-python-client` |
| Email Notifications | `smtplib` (configurable host/port/TLS) |
