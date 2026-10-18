# AI Recruitment System

<div align="center">
  <img src="media/logo.png" alt="AI Recruitment System" width="85%">
  
  <br><br>

  <p>
    <a href="docs/getting-started.md">Getting Started</a> | 
    <a href="docs/index.md">Documentation</a> | 
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
    <b>Built With:</b><br>
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

**AI Recruitment System** is an offline-capable desktop application for resume document parsing, AI candidate ranking against job descriptions, proctored technical interviews, and talent intelligence analytics. It supports local inference via Ollama and cloud AI models with automatic fallback.

---

## Features

| Feature | Details |
|---|---|
| Resume Upload | Microsoft Word (`.docx`), PDF (digital and scanned), PNG, JPG |
| Document Extraction | `python-docx` for `.docx`, `pypdf` for digital text PDFs, bundled Tesseract OCR for scanned documents and images |
| NLP Extraction | Structured extraction: skills, experience, education, projects, certifications, domain |
| Candidate Ranking | 5-criterion weighted scoring with auto-balancing and knockout criteria (experience, mandatory skills, certs) |
| Recruiter Notes & Tags | Custom recruiter notes and status tags persisted directly in SQLite |
| CSV / Excel Export | One-click RFC 4180 CSV export for candidate rankings and shortlist sharing |
| Scheduling | Top-N shortlist, HR slot coordination, `.ics` calendar files |
| Google Calendar | Optional OAuth integration for automatic invite creation |
| Interview Portal | Token-authenticated standalone HTTPS portal for candidates (`https://<host-ip>:5000`) |
| Configurable Interviews | Dynamic technical question count, behavioral question count, and per-question time limits |
| Adaptive Interview Bot | Role-adaptive blueprints (`is_tech_role`), adaptive follow-up probing for shallow answers |
| Real-Time Notifications | Automated desktop and dashboard notifications to HR upon candidate interview completion |
| Voice Mode | Browser-native HTML5 Web Speech API with backend speech fallbacks |
| Webcam Proctoring | Face detection via MediaPipe with OpenCV Haar cascade fallback |
| Violation Tracking | Tab switches, copy-paste events, face absence, multiple faces, response timeouts |
| PDF Reports | Material Design 3 monochrome reports with 4-part rubrics, verbatim answers, AI assessment, and proctoring logs |
| Talent Intelligence | Semantic vector search, candidate side-by-side comparison, feedback letters, and 6 visual analytics modules |
| 100% Air-Gapped Clean | Fully offline operation with bundled fonts and local Chart.js (zero outbound CDN calls) |
| Privacy Mode | All AI inference runs locally via Ollama with zero network egress |
| Encrypted Storage | API credentials, candidate database PII, and resumes encrypted at rest (AES-Fernet + PBKDF2) |
| CSRF & Session Security | CSRF token validation (`X-CSRF-Token`) on state-changing endpoints, scoped sessions, rate limiting |
| Email Notifications | SMTP scheduling emails with customizable templates |

---

## Quick Start

```bash
git clone https://github.com/shrs425p/AI-Recruitment-System.git
cd AI-Recruitment-System

python -m venv venv
venv\Scripts\activate

pip install -r requirements.txt
python main.py
```

The desktop application starts on `http://127.0.0.1:5001`. The candidate interview portal runs on `https://<your-ip>:5000`.

For full prerequisites, environment verification, and local Ollama setup, see [Getting Started](docs/getting-started.md).

---

## Documentation

| Guide | Description |
|---|---|
| [Getting Started](docs/getting-started.md) | Installation, first run, environment verification, configuration |
| [Architecture](docs/architecture.md) | Two-server model, subsystem boundaries, data flow |
| [Pipeline](docs/pipeline.md) | Step-by-step walkthrough of all recruitment stages |
| [Talent Intelligence](docs/talent-intelligence.md) | Semantic vector search, candidate comparison, feedback letters, and 6 talent analytics modules |
| [Air-Gapped Operation](docs/airgap.md) | 100% offline air-gapped setup, bundled fonts, local Chart.js, zero CDN assets |
| [Interview System](docs/interview-system.md) | Tokens, questions, adaptive follow-ups, voice mode, proctoring |
| [Reports](docs/reports.md) | Report layout, combined scoring, PDF exports, and HR completion notifications |
| [Configuration](docs/configuration.md) | Database-backed settings reference and default values |
| [AI Providers](docs/ai-providers.md) | Cloud vs Privacy mode, provider setup, model selection |
| [Security](docs/security.md) | Authentication, encryption at rest, HTTPS, rate limiting, sessions |
| [API Reference](docs/api-reference.md) | HTTP routes, CSRF requirements, request/response formats |
| [Testing](docs/testing.md) | Running the test suite (140 tests), coverage, and domain modules |
| [Google Calendar](docs/google-calendar.md) | OAuth integration and automatic calendar invite sync |
| [Email Setup](docs/email-setup.md) | SMTP configuration and invitation templates |
| [Data Formats](docs/data-formats.md) | JSON and SQLite schemas for all data models |
| [Customization](docs/customization.md) | Tunable parameters (weights, thresholds, question limits) |
| [Data Management](docs/data-management.md) | Backup, restore, and data cleanup procedures |
| [Deployment](docs/deployment.md) | Building the portable executable and Inno Setup Windows installer |
| [Troubleshooting](docs/troubleshooting.md) | Diagnostic steps and fixes for common runtime issues |
| [FAQ](docs/faq.md) | Frequently asked questions |
| [Contributing](docs/contributing.md) | Code conventions and contribution guidelines |

---

## License

MIT License — see [LICENSE](LICENSE) for details.
