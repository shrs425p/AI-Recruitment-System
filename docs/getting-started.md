# Getting Started

This guide covers everything needed to install, configure, and launch the AI Recruitment System on a Windows machine for the first time.

---

## Prerequisites

The following software must be installed before running the application.

| Requirement | Minimum Version | Notes |
|---|---|---|
| Windows | 10 (build 1903) | Windows 11 recommended |
| Python | 3.10 | 3.11 or 3.12 preferred |
| Git | Any | For cloning the repository |
| Ollama | 0.1.7 | Required for privacy mode (local AI) |

Python must be added to the system `PATH`. Verify with:

```bat
python --version
```

---

## Installation

### 1. Clone the Repository

```bat
git clone https://github.com/your-org/AI-Recruitment-System.git
cd AI-Recruitment-System
```

### 2. Create a Virtual Environment

```bat
python -m venv venv
call venv\Scripts\activate.bat
```

### 3. Install Dependencies

```bat
pip install --upgrade pip
pip install -r requirements.txt
```

> **Note:** The `mediapipe` package may take several minutes to download. This is expected.

### 4. Download the Offline Speech Model

The Vosk Indian-English speech model is required for voice-based interviews. It is approximately 36 MB.

```bat
python scripts/setup_vosk.py
```

To download the higher-accuracy 1 GB model instead:

```bat
python scripts/setup_vosk.py --large
```

The model is extracted to `models/vosk-model-small-en-in-0.4/`.

### 5. Verify the Tesseract OCR Engine

The Tesseract binary is bundled at `models/Tesseract-OCR/tesseract.exe`. No additional installation is required. If it is missing, download the portable build from [UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract/wiki) and extract it to `models/Tesseract-OCR/`.

---

## Running the Application

### Option A — Silent Launch (Recommended)

Double-click `Start.vbs` in the project root. The application starts without a console window.

### Option B — Console Launch

```bat
scripts\run.bat
```

This activates the virtual environment, installs any missing packages, and launches `main.py`. A console window remains open showing server logs.

### Option C — Direct Python

```bat
call venv\Scripts\activate.bat
python main.py
```

Once started, the application opens at `http://127.0.0.1:5001` in a pywebview desktop window. The HTTPS server also runs at `https://0.0.0.0:5000` for candidate interview access over the local network.

---

## First-Run Setup

On first launch the application will:

1. Create `data/ars.db` (SQLite database with all required tables).
2. Create `data/resumes/`, `data/output/`, and all output subdirectories.
3. Generate a self-signed SSL certificate at `data/output/ssl/cert.pem` and `key.pem`.

No manual database migration is needed.

---

## Network Setup

Candidates take interviews via the HTTPS server on port 5000. To allow inbound connections on the local network:

```bat
:: Run as Administrator
scripts\setup_firewall.bat
```

This adds a Windows Firewall inbound rule for port 5000. Candidates access the interview portal at:

```
https://<your-local-ip>:5000/candidate-interview/<token>
```

The interview token is generated from the Interview page after scheduling is complete.

---

## Stopping the Application

Close the pywebview window, or force-terminate all Python processes:

```bat
scripts\kill.bat
```

---

## Upgrading

```bat
git pull
call venv\Scripts\activate.bat
pip install -r requirements.txt --upgrade
```

The database schema is backward-compatible. No migration is required for minor version updates.
