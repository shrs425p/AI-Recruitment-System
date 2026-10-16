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
| **Document & OCR Extraction** | pypdf for digital PDFs, Tesseract OCR for scanned documents and images |
| **NLP Profile Extraction** | AI-powered structured JSON: skills, experience, education, projects, certifications, awards |
| **Candidate Ranking** | 5-criterion weighted AI scoring against any job description |
| **Interview Scheduling** | Top-N shortlist, slot coordination, `.ics` calendar invites, Google Calendar sync |
| **AI Interview Portal** | Token-authenticated candidate portal, 8 personalised questions per candidate |
| **Voice Mode** | Offline HTML5 Web Speech API (`SpeechSynthesis` + `SpeechRecognition`) |
| **Webcam Proctoring** | Real-time face detection (MediaPipe + OpenCV Haar cascade fallback) |
| **Violation Tracking** | Tab switches, copy-paste events, face absence, multiple faces |
| **Report Generation** | Material Design 3 monochrome PDF reports with rubrics, full transcripts, and proctoring summary |
| **Multi-Provider AI** | 8 cloud providers + local Ollama, with round-robin load balancing and dynamic live model fetching |
| **Privacy Mode** | Fully offline: Ollama local LLM, no data leaves the machine |
| **Encrypted Storage** | API credentials, candidate PII in database, and uploaded resumes encrypted at rest (AES-Fernet + PBKDF2) |
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
| Resume Parsing | `pypdf` — digital PDF text extraction |
| OCR | `Tesseract OCR` (bundled in `models/Tesseract-OCR/`) |
| Voice STT | HTML5 Web Speech API (`SpeechRecognition`) |
| Voice TTS | HTML5 Web Speech API (`SpeechSynthesis`) |

### Proctoring & Vision
| Component | Technology |
|---|---|
| Face Detection (primary) | `MediaPipe` face detection (requires `pip install mediapipe>=0.10.9`) |
| Face Detection (fallback) | OpenCV Haar cascade (`haarcascade_frontalface_default.xml`) |
| Webcam Capture | `OpenCV (cv2)` |

### Security
| Component | Technology |
|---|---|
| Credential & Data Encryption | `cryptography` — AES-Fernet with PBKDF2-HMAC-SHA256 key derivation |
| CSRF Protection | `Flask-WTF` / `X-CSRF-Token` header verification on state-changing routes |
| Password Hashing | `werkzeug.security` — scrypt-based password hashing |
| Desktop Auth | One-time nonce pool (cryptographically random, single-use tokens) |
| TLS | `cryptography` — self-signed RSA-2048 certificate (10-year validity) |

### Reporting & Scheduling
| Component | Technology |
|---|---|
| PDF Reports | `fpdf2` (Material Design 3 monochrome evaluation format) |
| Calendar Invites | `icalendar` (`.ics` files) |
| Google Calendar | `google-api-python-client` |
| Email | `smtplib` (SMTP, configurable host/port) |

---

For detailed module responsibilities and subsystem architecture, see [Architecture](architecture.md).  
For developer conventions, file organization, and contribution guidelines, see [Contributing](contributing.md).
