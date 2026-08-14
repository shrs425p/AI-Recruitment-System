# AI Recruitment System — Documentation

> **Platform:** Windows 10/11  
> **Stack:** Python · Flask · pywebview · SQLite · Tesseract OCR · Vosk · OpenCV

---

## What Is It?

The **AI Recruitment System (ARS)** is a desktop application that automates the recruitment pipeline — from uploading resumes to generating interview reports — without requiring cloud services (unless you want to use cloud AI providers).

It runs as a native Windows desktop window powered by pywebview, with a Flask web server serving the UI over localhost. A second HTTPS server runs simultaneously to host the **Candidate Interview Portal**, which candidates access from their own devices over the local network.

---

## Key Features

| Feature | Details |
|---|---|
| **Resume Upload** | PDF (digital + scanned), PNG, JPG |
| **OCR Extraction** | PyMuPDF for digital PDFs, Tesseract OCR for scanned documents |
| **NLP Profile Extraction** | AI-powered structured JSON: skills, experience, education, projects, certifications, awards |
| **Candidate Ranking** | 5-criterion weighted AI scoring against any job description |
| **Interview Scheduling** | Top-N shortlist, slot coordination, `.ics` calendar invites, Google Calendar sync |
| **AI Interview Portal** | Token-authenticated candidate portal, 8 personalised questions per candidate |
| **Voice Mode** | Offline speech-to-text (Vosk) + text-to-speech (pyttsx3) |
| **Webcam Proctoring** | Real-time face detection (MediaPipe + OpenCV Haar cascade fallback) |
| **Violation Tracking** | Tab switches, copy-paste events, face absence, multiple faces |
| **Report Generation** | PDF interview reports with transcript, scores, and proctor summary |
| **Multi-Provider AI** | 8 cloud providers + local Ollama, with round-robin load balancing |
| **Privacy Mode** | Fully offline: Ollama local LLM, no data leaves the machine |
| **Encrypted Storage** | All API keys and secrets encrypted at rest (AES-Fernet + PBKDF2) |
| **Email Notifications** | SMTP-based scheduling emails with customisable templates |

---

## Documentation Index

| Document | Who Should Read It |
|---|---|
| [Getting Started](getting-started.md) | New users — installation, first run, initial setup |
| [Architecture](architecture.md) | Developers — system design, data flow, component map |
| [Pipeline](pipeline.md) | HR users — step-by-step recruitment workflow |
| [Configuration](configuration.md) | Admins — every setting explained |
| [AI Providers](ai-providers.md) | Admins — cloud vs privacy mode, provider setup |
| [Interview System](interview-system.md) | HR users & developers — token auth, questions, voice, proctoring |
| [API Reference](api-reference.md) | Developers — all HTTP endpoints |
| [Security](security.md) | Admins & developers — auth, encryption, HTTPS, rate limiting |
| [Troubleshooting](troubleshooting.md) | Everyone — common issues and fixes |

---

## Technology Stack

### Core
| Layer | Technology |
|---|---|
| Desktop Shell | `pywebview` 5.x — native OS window wrapping a web view |
| Web Framework | `Flask` — serves both HR dashboard and candidate portal |
| Local Server | `Waitress` — production WSGI server for the desktop UI |
| Candidate Server | Flask dev server with self-signed TLS (HTTPS) |
| Database | `SQLite` via custom ORM layer (`app/database.py`) |
| Config | Database-backed dynamic config module (`config/__init__.py`) |

### AI & NLP
| Component | Technology |
|---|---|
| Local LLM | `Ollama` (llama3.2:3b default) |
| Cloud Providers | NVIDIA, OpenAI, Anthropic, Gemini, Groq, OpenRouter, GitHub Models, Ollama Cloud |
| Resume Parsing | `PyMuPDF (fitz)` — digital PDF text extraction |
| OCR | `Tesseract OCR` (bundled in `models/Tesseract-OCR/`) |
| Voice STT | `Vosk` (bundled model in `models/vosk-model-small-en-in-0.4/`) |
| Voice TTS | `pyttsx3` — offline text-to-speech |

### Proctoring & Vision
| Component | Technology |
|---|---|
| Face Detection (primary) | `MediaPipe` face detection (requires `pip install mediapipe>=0.10.9`) |
| Face Detection (fallback) | OpenCV Haar cascade (`haarcascade_frontalface_default.xml`) |
| Webcam Capture | `OpenCV (cv2)` |

### Security
| Component | Technology |
|---|---|
| Credential Encryption | `cryptography` — AES-Fernet with PBKDF2-HMAC-SHA256 key derivation |
| Password Hashing | `werkzeug.security` — scrypt-based password hashing |
| Desktop Auth | One-time nonce pool (cryptographically random, single-use tokens) |
| TLS | `cryptography` — self-signed RSA-2048 certificate (10-year validity) |

### Reporting & Scheduling
| Component | Technology |
|---|---|
| PDF Reports | `fpdf2` |
| Calendar Invites | `icalendar` (`.ics` files) |
| Google Calendar | `google-api-python-client` |
| Email | `smtplib` (SMTP, configurable host/port) |

---

## Quick Orientation

```
AI-Recruitment-System/
├── main.py                 ← Application entry point
├── app/
│   ├── __init__.py         ← Flask app factory (create_app)
│   ├── core.py             ← Log queue, live log streaming
│   ├── database.py         ← SQLite ORM and encrypted settings
│   ├── routes/             ← HTTP route handlers (one file per feature)
│   ├── templates/          ← Jinja2 HTML templates
│   └── static/             ← CSS, JS, icons
├── src/
│   ├── common.py           ← Paths, AI call dispatcher, JSON utils
│   ├── pdf_to_txt.py       ← PDF/image → plain text (PyMuPDF + Tesseract)
│   ├── nlp_extractor.py    ← Resume text → structured JSON (AI)
│   ├── ranking_engine.py   ← Candidate scoring against JD (AI)
│   ├── scheduling.py       ← Slot allocation, .ics generation
│   ├── interview_bot.py    ← Question generation and answer evaluation (AI)
│   ├── webcam_proctor.py   ← Real-time face detection and violation tracking
│   ├── voice_interview.py  ← Vosk STT + pyttsx3 TTS
│   ├── report_generator.py ← PDF report generation (fpdf2)
│   ├── provider_router.py  ← Round-robin multi-provider AI router
│   ├── security.py         ← AES-Fernet encryption/decryption
│   ├── google_calendar.py  ← Google Calendar API integration
│   └── email_sender.py     ← SMTP email dispatch
├── config/
│   └── __init__.py         ← Dynamic database-backed config module
├── models/
│   ├── Tesseract-OCR/      ← Bundled Tesseract OCR engine
│   └── vosk-model-small-en-in-0.4/ ← Bundled Vosk speech model
├── scripts/
│   ├── verify_environment.py   ← Dependency check script
│   ├── verify_providers.py     ← AI provider connectivity test
│   └── setup_vosk.py           ← Vosk model download helper
├── tests/                  ← pytest test suite
└── docs/                   ← This documentation
```
