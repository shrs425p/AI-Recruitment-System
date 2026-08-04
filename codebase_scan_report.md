# Codebase Scan Report: Hardcoded Values & Path Analysis

This document provides a comprehensive inventory of hardcoded values, file paths, endpoints, default keys, and configuration fallbacks discovered during a complete scan of the **AI Recruitment System** codebase (under the `src/`, `app/`, `main.py`, and root files).

---

## Executive Summary

The application is well-structured as an **offline-first desktop app**, using dynamic local data folders (`APP_DATA_DIR` / `%LOCALAPPDATA%`) and utility functions (`data_path()`, `install_path()`, `resource_path()`) to avoid rigid, machine-specific hardcoded absolute paths.

However, we identified several hardcoded parameters, static URLs, local ports, fallback settings, and system-specific definitions. These have been analyzed and categorized below with file references and potential improvements.

---

## 1. Absolute & Operating System Specific File Paths

While most file operations are relative to the dynamic runtime directory, some hardcoded paths exist for external binary tools.

### Finding 1.1: Local Ollama Installation Directory
* **File:** `src/ai_mode.py` (Line 5)
* **Code Snippet:**
  ```python
  OLLAMA_INSTALL_DIR   = "C:/ollama"            # where to install Ollama silently
  ```
* **Analysis & Risks:** This path is hardcoded to a Windows drive `C:/`. While standard on Windows, this will cause issues if the user installs Ollama to a different drive, or if the system is ran on non-Windows platforms (though this portion is labeled "Windows").
* **Recommended Improvement:** Derive this path from environment variables (e.g., `%PROGRAMFILES%` or `%LOCALAPPDATA%`) or allow customization in settings.

### Finding 1.2: Hardcoded Tesseract-OCR Executable Path
* **File:** `src/pdf_to_txt.py` (Line 21)
* **Code Snippet:**
  ```python
  pytesseract.pytesseract.tesseract_cmd = str(install_path("models/Tesseract-OCR") / "tesseract.exe")
  ```
* **Analysis & Risks:** This correctly uses `install_path()`, which is a helper resolving to the relative installation folder. However, it explicitly appends `"tesseract.exe"`. On Linux/macOS, the binary is not named `tesseract.exe` and is usually resolved via the system `PATH`.
* **Recommended Improvement:** Check `sys.platform`. If non-Windows, default to seeking `"tesseract"` in the system PATH, or fallback cleanly.

---

## 2. Hardcoded IP Addresses, Hostnames, & Local Port Configurations

Local networking defaults are hardcoded to loopback addresses and preset ports.

### Finding 2.1: Local Hostnames and Loopback IP Addresses
* **Files:** Multiple
  - `main.py` (Lines 354, 359, 363, 365, 386)
  - `app/routes/interview.py` (Line 123)
  - `app/routes/settings.py` (Line 197)
  - `app/utils.py` (Line 261)
  - `src/provider_router.py` (Line 17)
* **Code Snippet (Example from `main.py`):**
  ```python
  candidate_host = os.environ.get("ARS_CANDIDATE_HOST", "127.0.0.1")
  ...
  DESKTOP_PORT = _pick_port("127.0.0.1", _env_port("ARS_DESKTOP_PORT", 5001))
  ```
* **Analysis & Risks:** `127.0.0.1` and `localhost` are used for security verification and bindings. For local development and local desktop running, these loopbacks are standard and secure. However, using environmental overrides (like `ARS_CANDIDATE_HOST`) is supported, which mitigates rigid hardcoding.
* **Recommended Improvement:** No major changes needed as fallback environment variables exist, but ensure the documentation highlights how to change these if launching on a LAN.

### Finding 2.2: Hardcoded Port Fallbacks
* **File:** `main.py` (Lines 364-365)
* **Code Snippet:**
  ```python
  CANDIDATE_PORT = _pick_port(candidate_host, _env_port("ARS_CANDIDATE_PORT", 5000))
  DESKTOP_PORT = _pick_port("127.0.0.1", _env_port("ARS_DESKTOP_PORT", 5001))
  ```
* **Analysis & Risks:** Fallback ports `5000` and `5001` are hardcoded in code if environment variables aren't set. The `_pick_port` function safely falls back to a random port (`0`) if these are in use, making this resilient.
* **Recommended Improvement:** Safe as is, due to auto-free-port assignment logic.

### Finding 2.3: Hardcoded SQLite Database Filename
* **File:** `app/database.py` (Line 11)
* **Code Snippet:**
  ```python
  DB_PATH = data_path("ars.db")
  ```
* **Analysis & Risks:** The database file name is hardcoded to `"ars.db"`. While acceptable for single-tenant desktop apps, it limits running multiple profile sessions side-by-side.
* **Recommended Improvement:** Make the database file customizable via CLI arguments or environment variables if needed.

---

## 3. Hardcoded External API Endpoints & Base URLs

Several remote endpoints for AI providers and external tools are hardcoded in files.

### Finding 3.1: Ollama Default Local API Base URL
* **Files:** `main.py` (Line 42), `src/ai_mode.py` (Line 73)
* **Code Snippet:**
  ```python
  OLLAMA_BASE_URL = 'http://localhost:11434'
  ```
* **Analysis & Risks:** If Ollama is running on a remote server or container on the LAN, this defaults to the local loopback. However, the user can override this via the Settings page UI and save it.
* **Recommended Improvement:** Retain loopback as the default but ensure the runtime settings properly persist custom endpoints.

### Finding 3.2: Hardcoded Cloud Provider API Endpoints
* **File:** `src/provider_router.py` (Lines 54, 70, 86, 88), `src/ai_mode.py` (Lines 49, 57, 65)
* **Code Snippets:**
  - Anthropic messages endpoint: `https://api.anthropic.com/v1/messages`
  - Gemini content endpoint: `https://generativelanguage.googleapis.com/v1beta/models/...`
  - OpenAI base URL: `https://api.openai.com/v1`
  - Groq base URL: `https://api.groq.com/openai/v1`
  - NVIDIA base URL: `https://integrate.api.nvidia.com/v1`
  - OpenRouter base URL: `https://openrouter.ai/api/v1`
  - GitHub base URL: `https://models.inference.ai.azure.com`
* **Analysis & Risks:** Endpoints are hardcoded in the routing system. If a provider updates their API version or URL structure, code changes are required.
* **Recommended Improvement:** Externalize API base URLs into `config.py` as user-overrideable fields alongside models/keys.

### Finding 3.3: Hardcoded Google OAuth/Console URLs
* **File:** `src/google_calendar.py` (Lines 400-402, 438-440)
* **Code Snippets:**
  - `https://console.developers.google.com/apis/api/calendar-json.googleapis.com/...`
  - `https://console.cloud.google.com/apis/library/calendar-json.googleapis.com`
* **Analysis & Risks:** These are used to print instructions to the log console to guide the HR user on enabling Google APIs.
* **Recommended Improvement:** Perfect as helpful console links; no action required.

### Finding 3.4: Hardcoded Vosk Speech Recognition Model Download URLs
* **File:** `scripts/setup_vosk.py` (Lines 22, 29)
* **Code Snippets:**
  - Small Model: `https://alphacephei.com/vosk/models/vosk-model-small-en-in-0.4.zip`
  - Large Model: `https://alphacephei.com/vosk/models/vosk-model-en-in-0.5.zip`
* **Analysis & Risks:** Used by the setup scripts to fetch packages. If the host domain changes, download fails.
* **Recommended Improvement:** Add error-handling with mirrors or instruct users where to download if setup fails.

---

## 4. Default Credentials, Security Tokens, and Config Presets

Default presets and fallbacks are defined in `main.py` and the database structure.

### Finding 4.1: Empty Config Default Key Strings
* **File:** `main.py` (Lines 29, 62-69)
* **Code Snippet:**
  ```python
  ANTHROPIC_KEY = ''
  GEMINI_KEY = ''
  GROQ_KEY = ''
  OPENAI_KEY = ''
  NVIDIA_KEY = ''
  OPENROUTER_KEY = ''
  GITHUB_KEY = ''
  OLLAMA_CLOUD_KEY = ''
  ```
* **Analysis & Risks:** They are safely left empty, acting as configuration template keys. They are overridden at runtime from the persistent `config.py` in the local app directory.
* **Recommended Improvement:** Keep as empty templates to avoid leaking keys in production builds.

### Finding 4.2: Hardcoded SMTP Mail Fallback Parameters
* **File:** `main.py` (Lines 49-50)
* **Code Snippet:**
  ```python
  SMTP_HOST = 'smtp.gmail.com'
  SMTP_PORT = 587
  ```
* **Analysis & Risks:** Standard port 587 and Gmail's SMTP are provided as initial default configurations.
* **Recommended Improvement:** Keep as is, as they can be fully updated in the settings page.

### Finding 4.3: Random Flask Secret Key Generation Fallback
* **File:** `app/__init__.py` (Line 51)
* **Code Snippet:**
  ```python
  app.secret_key = (
      os.environ.get("FLASK_SECRET_KEY")
      or getattr(config, "FLASK_SECRET_KEY", "")
      or secrets.token_hex(32)
  )
  ```
* **Analysis & Risks:** If `FLASK_SECRET_KEY` is not present in env or config, the app generates a random token using `secrets.token_hex(32)`. Although secure, this means sessions are invalidated on every application restart.
* **Recommended Improvement:** On first run, write the generated secret key permanently into the user's local `config.py` so that sessions persist across restarts.

---

## 5. Model presets and settings fallbacks

### Finding 5.1: Preset Ollama and Cloud Models
* **File:** `main.py` (Lines 41, 71-80)
* **Code Snippet:**
  ```python
  OLLAMA_MODEL = 'llama3.2:3b'
  ...
  OPENAI_MODEL = 'gpt-4o-mini'
  ```
* **Analysis & Risks:** Hardcoded model names serve as the initial out-of-the-box experience.
* **Recommended Improvement:** Fully configurable via Settings; safe as standard defaults.
