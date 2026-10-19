# AI Recruitment System

<div align="center">
  <img src="media/logo.png" alt="AI Recruitment System" width="85%">
  
  <br><br>

  <p>
    <a href="DOCUMENTATION.md">System Documentation</a> | 
    <a href="docs/getting-started.md">Getting Started</a> | 
    <a href="docs/index.md">Documentation Hub</a> | 
    <a href="https://github.com/shrs425p/AI-Recruitment-System">GitHub Repository</a>
  </p>

  <p>
    <img src="https://img.shields.io/badge/status-stable-orange?style=flat-square" alt="Status">
    <img src="https://img.shields.io/github/v/release/shrs425p/AI-Recruitment-System?style=flat-square&label=latest" alt="Latest Version">
    <img src="https://img.shields.io/badge/license-MIT-red?style=flat-square" alt="License">
    <img src="https://img.shields.io/badge/tests-140%20passed-brightgreen?style=flat-square" alt="Tests">
    <img src="https://img.shields.io/badge/python-3.10%2B-yellow?style=flat-square" alt="Python">
    <img src="https://img.shields.io/badge/platform-Windows-blue?style=flat-square" alt="Platform">
    <img src="https://img.shields.io/badge/security-verified-brightgreen?style=flat-square" alt="Security">
  </p>

  <br>

  <p>
    <b>Core Technology Stack:</b><br>
    <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
    <img src="https://img.shields.io/badge/Flask-Web_Framework-000000?style=for-the-badge&logo=flask&logoColor=white" alt="Flask">
    <img src="https://img.shields.io/badge/pywebview-Desktop_Shell-0284C7?style=for-the-badge" alt="pywebview">
    <img src="https://img.shields.io/badge/SQLite-Local_Database-003B57?style=for-the-badge&logo=sqlite&logoColor=white" alt="SQLite">
    <img src="https://img.shields.io/badge/Ollama-Local_LLM-white?style=for-the-badge&logo=ollama&logoColor=black" alt="Ollama">
    <img src="https://img.shields.io/badge/NVIDIA-NIM_Cloud-76B900?style=for-the-badge&logo=nvidia&logoColor=white" alt="NVIDIA">
    <img src="https://img.shields.io/badge/OpenCV-Computer_Vision-5C3EE8?style=for-the-badge&logo=opencv&logoColor=white" alt="OpenCV">
    <img src="https://img.shields.io/badge/MediaPipe-Face_Detection-0073E6?style=for-the-badge" alt="MediaPipe">
    <img src="https://img.shields.io/badge/Tesseract-OCR_Engine-4285F4?style=for-the-badge" alt="Tesseract">
    <img src="https://img.shields.io/badge/python--docx-Word_Parsing-2B579A?style=for-the-badge" alt="python-docx">
    <img src="https://img.shields.io/badge/pypdf-PDF_Parsing-306998?style=for-the-badge" alt="pypdf">
    <img src="https://img.shields.io/badge/fpdf2-Report_Generation-D32F2F?style=for-the-badge" alt="fpdf2">
  </p>
</div>

---

## What Is the AI Recruitment System?

The **AI Recruitment System (ARS)** is an offline-capable, privacy-first desktop application designed to automate and orchestrate the complete technical hiring workflow. Built for talent acquisition specialists, engineering hiring managers, and recruitment operators, the system automates resume ingestion, attribute extraction, applicant ranking, calendar scheduling, proctored live technical assessments, evaluation scoring, and talent intelligence analytics.

The platform operates under a local data sovereignty architecture: all resumes, contact information, interview video/audio analyses, transcripts, evaluation scorecards, and system configurations are stored locally on the operator's machine. The application can run in a 100% air-gapped environment with zero outbound network calls using bundled fonts, local charting libraries, local OCR engines, local speech recognizers, and on-device large language models via Ollama.

---

## What It Does

Traditional recruitment requires juggling fragmented tools for resume screening, spreadsheet ranking, manual calendar coordination, third-party video conferencing, and manual interview evaluations. The AI Recruitment System unifies this entire journey into a single automated pipeline:

1. **Ingests & Normalizes Resumes:** Ingests candidate applications in digital PDF, scanned PDF, Microsoft Word (`.docx`), and image formats (`.png`, `.jpg`), recovering text via native parsers and bundled OCR.
2. **Extracts Structured Profiles:** Transforms unstructured resume text into a normalized JSON schema capturing personal details, technical and soft skills, career history, education, projects, certifications, and domain classifications.
3. **Ranks Candidates & Enforces Knockouts:** Scores candidates across 5 weighted dimensions (Skills, Experience, Education, Projects, Domain) against any job description, normalizes criteria weights dynamically, and applies automated tenure and skill knockout filters.
4. **Coordinates Schedules & Sends Invitations:** Shortlists top candidates, allocates discrete interview slots across upcoming weekdays, synchronizes with Google Calendar, generates `.ics` files, and dispatches automated invitation emails via SMTP STARTTLS.
5. **Conducts Proctored Technical Assessments:** Hosts an isolated, token-authenticated HTTPS portal on Port 5000 where candidates answer role-adaptive questions under real-time MediaPipe computer vision proctoring and server-enforced elapsed timers.
6. **Probes & Evaluates Answers:** Adapts question blueprints to role archetypes, dynamically injects targeted follow-up probing questions for shallow answers, and supports voice transcription.
7. **Synthesizes Combined Fit Scores:** Evaluates interview transcripts across 4 rubric dimensions (Technical Accuracy, Communication Clarity, Problem-Solving Depth, Behavioral Alignment) and calculates a final Combined Fit Score (40% resume fit + 60% interview performance).
8. **Generates Multi-Page PDF Reports:** Automatically compiles standardized, monochrome Material Design 3 PDF evaluation reports and issues instant desktop notifications to HR upon assessment completion.
9. **Delivers Talent Intelligence & Analytics:** Provides 384-dimensional vector semantic search, 4-way candidate comparison matrices, personalized candidate feedback letters, and 6 visual talent analytics modules.

---

## System Architecture & How It Works

The platform uses a strict two-server isolated architecture that segregates administrative control from public candidate assessment interactions:

```
[ Operator Desktop Window (pywebview) ]
               │
               ▼ Loopback HTTP (Port 5001)
     [ Waitress WSGI Server ]
               │
               ├── Flask Administrative App (app/routes/api.py, intelligence.py, etc.)
               ├── Relational Storage (SQLite ars.db - 13 Tables)
               ├── Encryption at Rest (Hardware Machine-GUID AES-Fernet)
               └── AI Provider Router (Ollama Local / NVIDIA NIM / Anthropic / Gemini / Groq)

                                    * * *

[ Candidate Devices on Local Network / VPN ]
               │
               ▼ Inbound HTTPS with Self-Signed TLS (Port 5000)
    [ Flask Candidate Portal Server ]
               │
               ├── Token Authentication (interview_tokens table, single-use burn)
               ├── Server Pacing & Anti-Tampering Engine (Linear progression)
               ├── Computer Vision Proctoring (MediaPipe Face Mesh + Haar Cascade fallback)
               └── Voice Processing (HTML5 Web Speech API + Offline Vosk/pyttsx3 fallbacks)
```

### The 8-Stage Recruitment Workflow

1. **Upload & Ingestion:** The operator adds resume files (`.pdf`, `.docx`, `.png`, `.jpg`) to `data/resumes/`. Files are validated against magic byte signatures, sanitized against path traversal, and limited to 16 MB.
2. **Text Extraction & OCR:** Digital PDFs are parsed via `pypdf`, Word documents are parsed via `python-docx` (traversing paragraphs and tables), and scanned documents are rasterized and processed via bundled Tesseract OCR 5.3.
3. **Structured NLP Extraction:** Segmented text is encapsulated in XML boundaries (`<resume_text>`) and converted by the AI engine into standardized candidate profile JSON records.
4. **Candidate Ranking:** Profiles are evaluated against the target job description across 5 criteria. Knockout rules filter out unqualified applicants, scores are normalized, candidate tiers are assigned, notes and triage tags are recorded, and leaderboards can be exported to CSV.
5. **Interview Scheduling:** Top N shortlisted candidates are allocated sequential interview slots across working weekdays. Free/busy slots are scanned via Google Calendar API, `.ics` calendar files are created, and invitation emails are dispatched via SMTP STARTTLS.
6. **Candidate Assessment:** Candidates open their unique URL on Port 5000, review onboarding disclosures, grant webcam/microphone permissions, and complete sequential questions under server-enforced timers.
7. **Computer Vision Proctoring:** Real-time facial landmark tracking monitors face absence, multiple faces, window focus loss, copy-paste attempts, and timeouts, calculating an overall Proctoring Integrity Score.
8. **Evaluation & Reporting:** Transcripts are scored across 4 rubric dimensions, the 40/60 combined fit score is computed, a comprehensive PDF report is generated, and a desktop pop-up notification is delivered to the HR manager.

---

## Key Features

| Category | Capability | Technical Details |
|---|---|---|
| Document Parsing | Multi-Format Ingestion | Native `.docx` XML parsing via `python-docx`, digital PDF extraction via `pypdf`, bundled Google Tesseract OCR 5.3 for scanned documents and images. |
| NLP Extraction | Structured Candidate Profiles | Normalizes skills (technical vs. soft), work chronology, tenure in years, academic credentials, projects, certifications, and domain classifications. |
| Candidate Ranking | 5-Criterion Weighted Scoring | Weighted scoring across Skills (35%), Experience (25%), Education (15%), Projects (15%), and Domain (10%) with dynamic weight normalization. |
| Knockout Filters | Automated Screening Rules | Minimum tenure knockout threshold (`MIN_EXPERIENCE_YEARS`) and mandatory required skills filter. |
| Recruiter Tools | Notes, Tags & CSV Export | In-place recruiter notes and triage tags saved directly to SQLite; single-click RFC 4180 candidate spreadsheet export. |
| Scheduling | Automated Timetables | Weekday slot generation, Google Calendar OAuth 2.0 FreeBusy conflict resolution, RFC 5545 `.ics` file generation, and SMTP STARTTLS email dispatch. |
| Candidate Portal | Isolated HTTPS Service | Dedicated Port 5000 server with auto-generated self-signed TLS certificates, single-use token lifecycle, and server-enforced question timers. |
| Proctoring | Real-Time Computer Vision | MediaPipe Face Mesh tracking 468 landmarks (with OpenCV Haar cascade fallback); detects face absence, multiple faces, tab switching, and copy-paste injections. |
| Adaptive Interviews | Dynamic Question Blueprints | Role-adaptive blueprints (technical vs. non-technical), configurable question counts (3–10 technical, 1–5 behavioral), configurable timers (60s–180s), and dynamic follow-up probing. |
| Voice System | Dual-Layer Voice Support | In-browser HTML5 Web Speech API (`SpeechSynthesis` + `SpeechRecognition`) with offline local Vosk and `pyttsx3` fallbacks. |
| Reporting | PDF Evaluation Reports | Standardized monochrome Material Design 3 PDF reports compiled via FPDF2 with Latin-1 font sanitization, rubric scorecards, proctoring breakdown, and transcripts. |
| Notifications | Real-Time Completion Alerts | Native Windows desktop pop-up notifications and persistent in-app SQLite notification tray (`hr_notifications`). |
| Talent Intelligence | Semantic Search & Analytics | 384-dimensional vector semantic search, 4-way candidate comparison matrix, personalized feedback letters, and 6 talent analytics visual modules. |
| Air-Gapped Operation | 100% Offline Clean | Zero external CDN calls; bundled Inter and JetBrains Mono fonts; bundled local Chart.js library; local on-device inference via Ollama (`llama3.2:3b`). |
| Multi-Provider AI | Flexible Model Execution | Cloud Mode with ProviderRouter load balancing, RPM tracking, and automatic failover across 8 providers (NVIDIA NIM, Anthropic, Gemini, Groq, OpenAI, OpenRouter, GitHub, Ollama). |
| Security & Privacy | Cryptographic Hardening | AES-Fernet encryption at rest derived from Windows hardware Machine GUID and persistent salt via PBKDF2; CSRF token validation; rate limiting; desktop nonces; GDPR purge. |

---

## Quick Start

### 1. Clone the Repository and Setup Environment

```bash
git clone https://github.com/shrs425p/AI-Recruitment-System.git
cd AI-Recruitment-System

python -m venv venv
venv\Scripts\activate

pip install -r requirements.txt
```

### 2. Launch the Application

```bash
python main.py
```

- The native desktop application window will open automatically, served locally via Waitress on `http://127.0.0.1:5001`.
- The public candidate interview portal runs on `https://<your-lan-ip>:5000`.

### 3. Run Automated Verification Tests

```bash
venv\Scripts\python.exe -m pytest -v --no-cov
```

All 140 automated tests across the 14 domain-scoped test modules will execute and verify the application.

---

## Documentation Index

Comprehensive guides, architectural diagrams, and operational specifications are available:

| Document | Focus & Contents |
|---|---|
| [System Documentation](DOCUMENTATION.md) | Single-file technical documentation covering architecture, setup, APIs, schemas, security, and troubleshooting. |
| [Getting Started](docs/getting-started.md) | Installation prerequisites, environment verification, first-run guide, and initial setup. |
| [Architecture](docs/architecture.md) | Two-server network isolation model, subsystem boundaries, data flow, and threading topology. |
| [Pipeline Guide](docs/pipeline.md) | Step-by-step walkthrough of all 8 recruitment pipeline stages from upload to report generation. |
| [Talent Intelligence](docs/talent-intelligence.md) | 384-dimensional vector semantic search, candidate comparison matrix, feedback letters, and the 6 analytics modules. |
| [Air-Gapped Operation](docs/airgap.md) | Zero-outbound CDN architecture, bundled fonts, local Chart.js bundle, and offline deployment. |
| [Interview System](docs/interview-system.md) | Token authentication, question blueprints, adaptive probing, timers, voice mode, and proctoring. |
| [Reports Guide](docs/reports.md) | 40/60 combined fit scoring formula, Latin-1 PDF compilation, recruiter notes, and HR desktop alerts. |
| [Configuration](docs/configuration.md) | Database-backed settings schema (`app_settings`), default values, and operational impacts. |
| [AI Providers](docs/ai-providers.md) | Cloud Mode vs. Privacy Mode, ProviderRouter load balancing, API keys, and dynamic model fetching. |
| [Security & Privacy](docs/security.md) | Machine-GUID AES-Fernet encryption at rest, CSRF protection, rate limiting, and GDPR purging. |
| [API Reference](docs/api-reference.md) | Complete HTTP route specifications, authentication headers, request bodies, and response schemas. |
| [Testing Guide](docs/testing.md) | Test suite architecture, 14 domain modules, 140 tests, mocking strategies, and Ruff static analysis. |
| [Google Calendar](docs/google-calendar.md) | OAuth 2.0 integration, credentials placement, and automated FreeBusy conflict resolution. |
| [Email Setup](docs/email-setup.md) | SMTP STARTTLS configuration, provider setup (Gmail, Outlook, Yahoo), and template variables. |
| [Data Formats](docs/data-formats.md) | Relational DDL for all 13 SQLite tables, NLP JSON profile schema, and ranking scorecards. |
| [Customization](docs/customization.md) | Tuning parameters: scoring weights, knockout thresholds, interview timers, and question counts. |
| [Data Management](docs/data-management.md) | Backup, restore, reset commands, candidate PII purging, and database inspection. |
| [Deployment Guide](docs/deployment.md) | Building the standalone executable via PyInstaller and the Inno Setup Windows installer. |
| [Troubleshooting](docs/troubleshooting.md) | Step-by-step diagnostic and resolution workflows for common operational issues. |
| [FAQ](docs/faq.md) | Frequently asked questions regarding offline use, network access, and features. |
| [Contributing](docs/contributing.md) | Code conventions, 14 domain test structure, Ruff lint rules, and air-gap requirements. |

---

## License

MIT License — see [LICENSE](LICENSE) for details.
