# Getting Started

This guide walks you through installing the AI Recruitment System, running it for the first time, and completing initial configuration.

---

## System Requirements

| Requirement | Minimum | Recommended |
|---|---|---|
| OS | Windows 10 (64-bit) | Windows 11 (64-bit) |
| RAM | 8 GB | 16 GB |
| Storage | 4 GB free | 10 GB free |
| CPU | 4-core x64 | 8-core x64 |
| GPU | Not required | NVIDIA GPU (for local Ollama with GPU acceleration) |
| Python | 3.10+ | 3.11 |
| Internet | Optional | Required only for cloud AI providers |

> **Note:** The Vosk speech model and Tesseract OCR engine are bundled in the `models/` directory. No separate download is needed for offline operation.

---

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/shrs425p/AI-Recruitment-System.git
cd AI-Recruitment-System
```

### 2. Create a Virtual Environment

```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

For development (includes linting, testing tools):

```bash
pip install -r requirements-dev.txt
```

### 4. Verify Your Environment

Run the environment checker to confirm all required packages and bundled models are present:

```bash
python scripts/verify_environment.py
```

This script checks for:
- Python version compatibility
- All required pip packages
- Tesseract OCR binary at `models/Tesseract-OCR/tesseract.exe`
- Vosk model at `models/vosk-model-small-en-in-0.4/`
- OpenCV availability
- MediaPipe (optional — falls back to Haar cascade if missing)

---

## Running the Application

### Standard Launch

```bash
python main.py
```

The application will:
1. Initialise the SQLite database at `%LOCALAPPDATA%\AI Recruitment System\data\ars.db`
2. Start the **HR Desktop Server** (Waitress, HTTP) on port `5001` (localhost only)
3. Start the **Candidate Interview Server** (Flask, HTTPS) on port `5000` (all interfaces)
4. Open the desktop window via pywebview pointing to `http://127.0.0.1:5001`

### Alternative Launch (No Desktop Window)

If you want to run just the Flask server (e.g. for debugging in a browser):

```bash
python main.py
# then open http://127.0.0.1:5001 in your browser
```

### Using the Batch Scripts

```
scripts\run.bat          ← Standard launch (activates venv automatically)
scripts\kill.bat         ← Force-kill all Python processes
```

---

## Environment Variables

All of these are optional overrides. The application works without any of them.

| Variable | Default | Description |
|---|---|---|
| `ARS_DESKTOP_PORT` | `5001` | Port for the HR desktop UI server |
| `ARS_CANDIDATE_PORT` | `5000` | Port for the candidate interview portal |
| `ARS_CANDIDATE_HOST` | `0.0.0.0` | Host interface for the candidate server |
| `ARS_SERVER_THREADS` | `8` | Number of Waitress worker threads |
| `ARS_MAX_UPLOAD_BYTES` | `26214400` (25 MB) | Maximum resume upload file size |
| `ARS_DEBUG` | (unset) | Set to `1` to enable Flask debug mode (dev only) |
| `FLASK_SECRET_KEY` | Auto-generated | Override the Flask session secret key |

---

## First-Time Setup

On first launch, the application creates the database and seeds all default settings. No manual configuration file is needed.

### Step 1 — Open Settings

Click the **Settings** icon in the sidebar. You will see tabs for:
- **General** — display name, company, HR email
- **AI Providers** — API keys and model selection
- **Email** — SMTP configuration for scheduling emails
- **Security** — login enable/disable, password change
- **Theme** — light/dark mode, colour palette

### Step 2 — Configure an AI Provider

The system needs at least one AI provider to run NLP extraction, ranking, and interview question generation.

**Fastest setup (free):** Enable NVIDIA NIM — it provides free API credits with a generous rate limit.

See [AI Providers](ai-providers.md) for full setup instructions for each provider.

### Step 3 — Test the Provider

```bash
python scripts/verify_providers.py
```

This sends a test prompt to all enabled providers and reports which ones respond successfully.

### Step 4 — Upload Resumes

Navigate to **Upload** in the sidebar. Supported formats:
- `.pdf` — digital (text-based) or scanned
- `.png`, `.jpg`, `.jpeg` — resume images (processed via OCR)

The uploaded files are saved to `%LOCALAPPDATA%\AI Recruitment System\data\resumes\`.

### Step 5 — Run the Pipeline

Follow the pipeline in order:
1. **Upload** → resumes ingested
2. **NLP** → AI extracts structured candidate profiles
3. **Ranking** → AI scores candidates against your job description
4. **Scheduling** → shortlist created, interview slots generated
5. **Interview** → candidates complete the AI interview via their browser
6. **Reports** → PDF reports generated for each candidate

See [Pipeline](pipeline.md) for a full walkthrough.

---

## Data Storage

All runtime data is stored in the user's `LOCALAPPDATA` directory to avoid requiring admin privileges:

```
%LOCALAPPDATA%\AI Recruitment System\
├── data\
│   ├── ars.db              ← SQLite database (settings + schema)
│   ├── resumes\            ← Uploaded resume files
│   └── output\
│       ├── txt\            ← Plain-text extracted from PDFs
│       ├── nlp\            ← AI-extracted candidate JSON profiles
│       ├── ranking\        ← Ranked candidate leaderboards
│       ├── scheduling\     ← Schedule files + .ics invites
│       ├── interviews\     ← Interview transcripts
│       ├── reports\        ← Generated PDF reports
│       └── ssl\            ← Self-signed TLS certificate (auto-generated)
└── .secret_salt            ← Random salt for credential encryption
```

> **Important:** Never move or delete `.secret_salt`. This file is used to derive the encryption key for all stored API keys and passwords. Losing it means encrypted credentials cannot be recovered.

---

## Updating

```bash
git pull origin main
pip install -r requirements.txt   # install any new dependencies
python main.py
```

The database schema is automatically migrated on startup via `app/database.py`.
