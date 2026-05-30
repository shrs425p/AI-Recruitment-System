# Configuration Reference

All application settings are stored in `config/config.py`. This file is read at startup and can be edited directly. Changes take effect after restarting the application. The Settings UI also writes to this file automatically.

---

## Login and Security

| Key | Type | Default | Description |
|---|---|---|---|
| `LOGIN_ENABLED` | bool | `False` | Require HR username and password to access the dashboard |
| `HR_USERNAME` | str | `'admin'` | Username for HR login |
| `HR_PASSWORD` | str | `'admin'` | Password for HR login |
| `FLASK_SECRET_KEY` | str | `'ars_secure_key_2026'` | Flask session signing key — change this in production |

> **Security note:** If `LOGIN_ENABLED` is `False`, the dashboard is accessible to anyone on the network. Enable it when running in a shared environment.

---

## HR Profile

| Key | Type | Default | Description |
|---|---|---|---|
| `HR_DISPLAY_NAME` | str | `'HR Admin'` | Name displayed on reports and calendar events |
| `HR_EMAIL` | str | `''` | HR email address — used as calendar event attendee |
| `HR_COMPANY` | str | `''` | Company name — shown on the Settings page |

---

## UI Theme

| Key | Type | Default | Options | Description |
|---|---|---|---|---|
| `THEME` | str | `'light'` | `'light'`, `'dark'` | Application colour scheme |
| `COLOR_PALETTE` | str | `'lavender'` | `'lavender'`, `'sage'`, `'blue'`, `'rose'` | Accent colour palette |

Theme and palette settings are persisted to `config/config.py` immediately when changed via the top navigation bar controls.

---

## Ollama Settings (Privacy Mode)

| Key | Type | Default | Description |
|---|---|---|---|
| `OLLAMA_MODEL` | str | `'llama3.2:3b'` | Model tag used for all AI calls in privacy mode |
| `OLLAMA_BASE_URL` | str | `'http://localhost:11434'` | Ollama API base URL |
| `PRIVACY_MODEL` | str | `'llama3.2:3b'` | Alias — same as `OLLAMA_MODEL` |

See [AI Providers — Ollama](ai-providers.md#ollama) for model download instructions.

---

## AI Mode

| Key | Type | Default | Options | Description |
|---|---|---|---|---|
| `APP_MODE` | str | `'privacy'` | `'privacy'`, `'cloud'` | Selects the AI inference backend |

When `APP_MODE = 'cloud'`, the `provider_router.py` module iterates enabled cloud providers in priority order and uses the first one that responds successfully.

---

## Cloud AI Providers

Each provider has a key, a model, and an enable flag.

### API Keys

| Key | Provider |
|---|---|
| `ANTHROPIC_KEY` | Anthropic (Claude) |
| `GEMINI_KEY` | Google Gemini |
| `GROQ_KEY` | Groq |
| `OPENAI_KEY` | OpenAI |
| `NVIDIA_KEY` | NVIDIA NIM |
| `OPENROUTER_KEY` | OpenRouter |
| `GITHUB_KEY` | GitHub Models |
| `OLLAMA_CLOUD_KEY` | Ollama Cloud |

### Models

| Key | Default |
|---|---|
| `ANTHROPIC_MODEL` | `'claude-3-5-haiku-latest'` |
| `GEMINI_MODEL` | `'gemini-1.5-flash'` |
| `GROQ_MODEL` | `'llama3-8b-8192'` |
| `OPENAI_MODEL` | `'gpt-4o-mini'` |
| `NVIDIA_MODEL` | `'meta/llama-3.1-nemotron-70b-instruct'` |
| `OPENROUTER_MODEL` | `'meta-llama/llama-3.1-8b-instruct:free'` |
| `GITHUB_MODEL` | `'gpt-4o-mini'` |
| `OLLAMA_CLOUD_MODEL` | `'llama3.2:3b'` |

### Enable Flags

Set the corresponding flag to `True` to include the provider in the fallback chain:

```python
ANTHROPIC_ENABLED = True
GEMINI_ENABLED    = False
GROQ_ENABLED      = False
OPENAI_ENABLED    = False
NVIDIA_ENABLED    = False
OPENROUTER_ENABLED = False
GITHUB_ENABLED    = False
OLLAMA_CLOUD_ENABLED = False
```

---

## Email / SMTP Settings

| Key | Type | Default | Description |
|---|---|---|---|
| `SMTP_HOST` | str | `'smtp.gmail.com'` | SMTP server hostname |
| `SMTP_PORT` | int | `587` | SMTP port (587 = STARTTLS) |
| `SMTP_EMAIL` | str | `''` | Sender email address |
| `SMTP_PASSWORD` | str | `''` | Gmail App Password (not account password) |

To generate a Gmail App Password:
1. Enable two-factor authentication on the Gmail account.
2. Go to **Google Account > Security > App Passwords**.
3. Create a new app password and paste it into `SMTP_PASSWORD`.

---

## Retry and Backoff

| Key | Type | Default | Description |
|---|---|---|---|
| `AI_RETRY_ATTEMPTS` | int | `3` | Number of retry attempts on AI call failure |
| `AI_RETRY_BACKOFF` | int | `2` | Exponential backoff multiplier (seconds) |

---

## Cloud Fallback (Legacy Keys)

| Key | Description |
|---|---|
| `CLOUD_ENABLED` | Deprecated — use `APP_MODE = 'cloud'` instead |
| `CLOUD_MODEL` | Deprecated — use `ANTHROPIC_MODEL` |

These keys remain for backward compatibility and have no effect when `APP_MODE` is set correctly.

---

## Configuration Persistence

When HR saves settings via the UI, the `_save_config` function in `main.py`:

1. Reads the current `config/config.py` contents.
2. Replaces the changed key-value pairs in-place.
3. Writes the updated content back to `config/config.py`.
4. Also writes a copy to `data/config.py` for the running process to reload.

The configuration file is plain Python. Do not add executable code or imports to it.
