# AI Recruitment System — Documentation

**Version 1.0**  |  Flask · SQLite · Ollama · pywebview  |  Windows Desktop

This is the official documentation for the **Recruit Pipeline Manager**, a self-hosted, AI-powered recruitment automation platform designed for HR teams. All processing is local by default — no candidate data leaves the machine unless a cloud AI provider is explicitly configured.

---

## Table of Contents

| Document | Description |
|---|---|
| [Getting Started](getting-started.md) | Installation, prerequisites, and first launch |
| [Architecture](architecture.md) | System design, folder layout, and data flow |
| [Pipeline Guide](pipeline.md) | All six pipeline steps — manual and automatic modes |
| [Configuration Reference](configuration.md) | Every setting in `config/config.py` explained |
| [AI Providers](ai-providers.md) | Ollama, Claude, Gemini, Groq, and OpenAI setup |
| [Interview System](interview-system.md) | Candidate tokens, voice mode, and proctoring |
| [Google Calendar](google-calendar.md) | OAuth2 setup and automated calendar event creation |
| [API Reference](api-reference.md) | Complete Flask REST API endpoint catalogue |
| [Build and Deploy](build-and-deploy.md) | PyInstaller executable and Inno Setup installer |
| [Theming and UI](theming.md) | Dark and light mode, colour palettes, customisation |
| [Troubleshooting](troubleshooting.md) | Common errors, diagnostics, and resolutions |
| [Changelog](changelog.md) | Version history and release notes |

---

## Navigation by Role

### First-time User
1. [Prerequisites](getting-started.md#prerequisites)
2. [Installation](getting-started.md#installation)
3. [Running the Application](getting-started.md#running-the-application)
4. [Upload Resumes](pipeline.md#step-1-upload)

### HR Administrator
1. [Configuration Reference](configuration.md)
2. [AI Provider Setup](ai-providers.md)
3. [Google Calendar Integration](google-calendar.md)
4. [Network Setup for Candidate Interviews](getting-started.md#network-setup)

### Developer or Contributor
1. [Architecture Overview](architecture.md)
2. [API Reference](api-reference.md)
3. [Build and Deploy](build-and-deploy.md)
4. [Folder Structure](architecture.md#folder-structure)

---

## Quick Start

```bat
:: 1. Install Python dependencies
pip install -r requirements.txt

:: 2. Download the offline Vosk speech model (36 MB)
python scripts/setup_vosk.py

:: 3. Launch the application
Start.vbs
```

The application opens at `http://127.0.0.1:5001` in a native desktop window powered by pywebview.

---

## Pipeline Overview

```
Resume Upload  ->  PDF to TXT  ->  NLP Extract  ->  AI Rank  ->  Schedule  ->  Interview  ->  Report
   Step 1           Step 2           Step 3         Step 4       Step 5        Step 6
```

Each step produces structured output consumed by the next step. All data is written to the `data/` directory.

---

## Privacy and Data Handling

The system is designed for air-gapped or privacy-sensitive environments:

| Component | Default | Location |
|---|---|---|
| AI inference | Ollama (local) | `localhost:11434` |
| OCR engine | Tesseract (bundled) | `models/Tesseract-OCR/` |
| Speech recognition | Vosk (offline) | `models/vosk-model-small-en-in-0.4/` |
| Database | SQLite | `data/ars.db` |
| Resume files | Local filesystem | `data/resumes/` |

No data is transmitted externally unless a cloud AI provider is explicitly enabled in `config/config.py`.

---

*Documentation maintained by the ARS development team. Last updated: May 2026.*
