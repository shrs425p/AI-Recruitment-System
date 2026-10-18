# Getting Started

This guide details installing the AI Recruitment System, verifying dependencies, running tests, and performing initial configuration.

---

## System Requirements

| Requirement | Minimum | Recommended |
|---|---|---|
| OS | Windows 10 (64-bit) | Windows 11 (64-bit) |
| RAM | 8 GB | 16 GB |
| Storage | 4 GB free disk space | 10 GB free disk space |
| CPU | 4-core x64 processor | 8-core x64 processor |
| GPU | Optional | NVIDIA GPU (recommended for local Ollama acceleration) |
| Python | 3.10+ | 3.11 / 3.12 |
| Internet | Optional | Required only when using cloud AI providers |

Bundled local dependencies include Tesseract OCR (`models/Tesseract-OCR/`) and local web assets (`app/static/`). The system functions in air-gapped environments without external network connections.

---

## Installation

### 1. Clone the Repository
```bash
git clone https://github.com/shrs425p/AI-Recruitment-System.git
cd AI-Recruitment-System
```

### 2. Create and Activate Virtual Environment
```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Install Required Dependencies
```bash
pip install -r requirements.txt
```

### 4. Verify the Installation (Run Tests)
Execute the complete test suite to verify all 14 domain modules:
```bash
pytest -v
```
All 140 tests should pass cleanly.

---

## Launching the Application

### Standard Desktop Launch
```bash
python main.py
```
Upon execution, the launcher:
1. Initializes or migrates the SQLite schema across all 9 relational tables at `data/recruitment.db`.
2. Starts the **HR Desktop Server** (Waitress WSGI) on `http://127.0.0.1:5001`.
3. Starts the **Candidate Interview Server** (Flask HTTPS) on `https://<LAN-IP>:5000`.
4. Launches the desktop application shell via `pywebview`.

### Headless / Browser-Only Mode
If running on a remote workstation or without `pywebview`:
```bash
python main.py
```
Then navigate to `http://127.0.0.1:5001` in your web browser.

---

## First-Time Setup Workflow

### Step 1 — Review Application Settings
Navigate to the **Settings** tab in the sidebar:
- **Interview Configuration:** Adjust technical question counts, behavioral question counts, and per-question timers.
- **AI Providers:** Select your active provider (`ollama` for local privacy mode, or configure API keys for NVIDIA NIM, OpenAI, Gemini, Groq, Anthropic).
- **Security:** Configure or update the HR password.
- **SMTP Settings:** Configure outbound email host, port, and credentials for candidate invitations.

### Step 2 — Ingest Resumes
Navigate to **Upload** in the sidebar. The system accepts:
- Microsoft Word (`.docx`)
- Digital and scanned PDF (`.pdf`)
- Image resumes (`.png`, `.jpg`, `.jpeg`)

### Step 3 — Execute Recruitment Pipeline
1. **Upload:** Ingest applicant resumes into `data/resumes/`.
2. **Text Extraction:** Converts resumes into plain text in `data/output/txt/`.
3. **NLP Extraction:** Extracts structured JSON profiles into `data/output/nlp/`.
4. **Candidate Ranking:** Evaluates candidates against a target Job Description with customizable weights and knockout rules. Annotate candidate rows with notes and tags, or click **Export to CSV**.
5. **Scheduling:** Shortlist finalists, allocate time slots, and issue interview tokens.
6. **Live Interview:** Candidates connect to `https://<host-ip>:5000/candidate-interview/<token>` to complete the proctored interview.
7. **Reports:** Generate final PDF dossiers with combined fit scores (40% resume + 60% interview). Real-time desktop notifications alert HR upon completion.
8. **Talent Intelligence:** Query the talent pool using semantic vector search and review executive analytics.
