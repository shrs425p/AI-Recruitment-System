# Configuration Reference

All settings are stored in the SQLite database (`ars.db`) — there is no `.env` file or `config.py` file on disk. Settings are managed through the app's Settings page and accessed at runtime via the `config` package (`config/__init__.py`).

Sensitive values (API keys, passwords) are encrypted at rest using AES-Fernet. See [Security](security.md) for details.

---

## Accessing Settings

**In the UI:** Sidebar → Settings  
**In code:** `import config; value = getattr(config, "KEY_NAME", default)`  
**In database:** `app_settings` table in `ars.db`

---

## General Settings

| Key | Default | Description |
|---|---|---|
| `HR_DISPLAY_NAME` | `"HR Admin"` | Display name shown in the UI header |
| `HR_EMAIL` | `""` | HR manager's email address (used as the sender in scheduling emails) |
| `HR_COMPANY` | `""` | Company name shown in emails and reports |
| `THEME` | `"light"` | UI theme — `"light"` or `"dark"` |
| `COLOR_PALETTE` | `"rose"` | Colour accent for the UI (options vary by theme) |

---

## Authentication Settings

| Key | Default | Description |
|---|---|---|
| `LOGIN_ENABLED` | `False` | If `True`, the HR dashboard requires username + password to access |
| `HR_USERNAME` | `"hr"` | Login username for the HR dashboard |
| `HR_PASSWORD` | `""` | Plain-text password (only used during initial setup — replaced by hash on save) |
| `HR_PASSWORD_HASH` | `""` | Scrypt-hashed password stored by `werkzeug.security` |
| `FLASK_SECRET_KEY` | `""` | Flask session signing key. Auto-generated on first run if empty |

> **Note:** When `LOGIN_ENABLED` is `False`, the HR dashboard is accessible to anyone who can reach the server. This is fine for single-user local use, but enable login if others can access the network.

---

## AI Mode Settings

| Key | Default | Description |
|---|---|---|
| `APP_MODE` | `"cloud"` | `"cloud"` uses the provider router; `"privacy"` uses local Ollama only |
| `AI_RETRY_ATTEMPTS` | `3` | Number of times to retry a failed AI call before giving up |
| `AI_RETRY_BACKOFF` | `2` | Seconds multiplier between retries (attempt 1 waits 2s, attempt 2 waits 4s, etc.) |

### APP_MODE: `"cloud"` vs `"privacy"`

**`cloud`** — Routes AI calls through the `ProviderRouter`, which load-balances across all enabled cloud providers (NVIDIA, OpenAI, Anthropic, etc.). Requires at least one provider to be enabled with a valid API key.

**`privacy`** — Sends all AI calls to a local Ollama server running on the same machine. No data leaves the device. Falls back to Anthropic cloud if Ollama times out and `CLOUD_ENABLED` is `True`.

---

## Local Ollama Settings

Used in Privacy mode or as a fallback.

| Key | Default | Description |
|---|---|---|
| `OLLAMA_MODEL` | `"llama3.2:3b"` | Model name to use with local Ollama (must be pulled first) |
| `OLLAMA_BASE_URL` | `"http://localhost:11434"` | URL of the local Ollama server |
| `PRIVACY_MODEL` | `"llama3.2:3b"` | Model used specifically in Privacy mode |

To pull a model for Ollama:
```bash
ollama pull llama3.2:3b
```

---

## Cloud Provider Settings

Each cloud provider has three settings: an API key, a model name, and an enabled flag.

### NVIDIA NIM

| Key | Default | Description |
|---|---|---|
| `NVIDIA_KEY` | `""` | API key from [build.nvidia.com](https://build.nvidia.com) |
| `NVIDIA_MODEL` | `"meta/llama-3.1-8b-instruct"` | Model to use |
| `NVIDIA_ENABLED` | `True` | Enable this provider |

NVIDIA NIM is enabled by default because it offers free credits. Get a key at `build.nvidia.com`.

---

### Anthropic (Claude)

| Key | Default | Description |
|---|---|---|
| `ANTHROPIC_KEY` | `""` | API key from [console.anthropic.com](https://console.anthropic.com) |
| `ANTHROPIC_MODEL` | `"claude-3-5-haiku-latest"` | Model to use |
| `ANTHROPIC_ENABLED` | `False` | Enable this provider |
| `CLOUD_ENABLED` | `False` | Legacy toggle — also enables Anthropic as a fallback in Privacy mode |
| `CLOUD_MODEL` | `"claude-3-5-haiku-latest"` | Model used for the Privacy mode fallback |

---

### Gemini (Google)

| Key | Default | Description |
|---|---|---|
| `GEMINI_KEY` | `""` | API key from [aistudio.google.com](https://aistudio.google.com) |
| `GEMINI_MODEL` | `"gemini-1.5-flash"` | Model to use |
| `GEMINI_ENABLED` | `False` | Enable this provider |

---

### Groq

| Key | Default | Description |
|---|---|---|
| `GROQ_KEY` | `""` | API key from [console.groq.com](https://console.groq.com) |
| `GROQ_MODEL` | `"llama3-8b-8192"` | Model to use |
| `GROQ_ENABLED` | `False` | Enable this provider |

---

### OpenAI

| Key | Default | Description |
|---|---|---|
| `OPENAI_KEY` | `""` | API key from [platform.openai.com](https://platform.openai.com) |
| `OPENAI_MODEL` | `"gpt-4o-mini"` | Model to use |
| `OPENAI_ENABLED` | `False` | Enable this provider |

---

### OpenRouter

| Key | Default | Description |
|---|---|---|
| `OPENROUTER_KEY` | `""` | API key from [openrouter.ai](https://openrouter.ai) |
| `OPENROUTER_MODEL` | `"meta-llama/llama-3.1-8b-instruct:free"` | Model to use |
| `OPENROUTER_ENABLED` | `False` | Enable this provider |

---

### GitHub Models

| Key | Default | Description |
|---|---|---|
| `GITHUB_KEY` | `""` | GitHub personal access token (with model access) |
| `GITHUB_MODEL` | `"gpt-4o-mini"` | Model to use |
| `GITHUB_ENABLED` | `False` | Enable this provider |

---

### Ollama Cloud (Remote Ollama)

| Key | Default | Description |
|---|---|---|
| `OLLAMA_CLOUD_KEY` | `""` | Not required (Ollama has no auth by default) |
| `OLLAMA_CLOUD_MODEL` | `"llama3.2:3b"` | Model to use |
| `OLLAMA_CLOUD_ENABLED` | `False` | Enable this provider |

---

## Email Settings

Used for sending scheduling emails to candidates.

| Key | Default | Description |
|---|---|---|
| `SMTP_HOST` | `"smtp.gmail.com"` | SMTP server hostname |
| `SMTP_PORT` | `587` | SMTP port (587 = STARTTLS, 465 = SSL) |
| `SMTP_EMAIL` | `""` | Sender email address |
| `SMTP_PASSWORD` | `""` | Sender email password / app password (stored encrypted) |
| `EMAIL_TEMPLATE_SUBJECT` | `""` | Default subject line for scheduling emails |
| `EMAIL_TEMPLATE_BODY` | `""` | Default body template (supports `{name}`, `{slots}`, `{link}` placeholders) |

> **Gmail users:** Use an App Password (not your regular password). Go to Google Account → Security → 2-Step Verification → App passwords.

---

## Encrypted Keys

The following keys are automatically encrypted before being saved to the database. They are decrypted in memory when needed and never written in plain text to disk.

```
ANTHROPIC_KEY, GEMINI_KEY, GROQ_KEY, OPENAI_KEY,
NVIDIA_KEY, OPENROUTER_KEY, GITHUB_KEY, OLLAMA_CLOUD_KEY,
SMTP_PASSWORD, FLASK_SECRET_KEY
```

Encrypted values are stored with an `ENC:` prefix in the database. If you see `ENC:...` in the `app_settings` table, that is an encrypted value — do not modify it manually.
