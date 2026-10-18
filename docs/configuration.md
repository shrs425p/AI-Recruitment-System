# Configuration

This document is the reference guide for all system configuration options, database-backed application settings, and environment variables.

---

## Configuration Architecture

Configuration in ARS is layered:

```
Default Python Config (config/__init__.py)
                    │
                    ▼
Persistent Database Settings (SQLite table: app_settings)
                    │
                    ▼
Environment Variable Overrides (Process Environment)
```

1. **Default Config:** Sensible defaults defined in code.
2. **Database Overrides:** Modified dynamically by HR users via the Settings UI or `/api/settings/save`. Values are encrypted when sensitive.
3. **Environment Variables:** Highest priority; ideal for containerized or automated headless setups.

---

## 1. Network & Server Settings

| Variable / Key | Default | Description |
|---|---|---|
| `FLASK_PORT` | `5001` | Port for the HR Dashboard desktop WSGI server (bound to `127.0.0.1`). |
| `CANDIDATE_PORT` | `5000` | Port for the remote candidate portal (bound to `0.0.0.0` with TLS). |
| `SERVER_HOST` | `<LAN-IP>` | Detected local network IPv4 address used to construct candidate invitation URLs. |

---

## 2. Dynamic Interview Settings

These settings are managed directly in the Settings tab without requiring application restarts:

| Setting Key | Type | Default | Description |
|---|---|---|---|
| `INTERVIEW_TECH_QUESTIONS` | Integer | `5` | Number of technical domain questions generated per candidate interview (range: 3 to 10). |
| `INTERVIEW_BEHAVIORAL_QUESTIONS` | Integer | `3` | Number of STAR-format behavioral questions generated per candidate (range: 1 to 5). |
| `INTERVIEW_TIME_LIMIT` | Integer | `120` | Maximum allowed time (in seconds) per question before a response timeout flag is logged (e.g. 60, 90, 120, 180). |

---

## 3. Candidate Ranking & Knockout Defaults

| Setting Key | Type | Default | Description |
|---|---|---|---|
| `WEIGHT_SKILLS` | Integer | `35` | Default weight percentage for technical skills match. |
| `WEIGHT_EXPERIENCE` | Integer | `20` | Default weight percentage for years of experience match. |
| `WEIGHT_DOMAIN` | Integer | `20` | Default weight percentage for domain and industry relevance. |
| `WEIGHT_EDUCATION` | Integer | `15` | Default weight percentage for highest educational degree. |
| `WEIGHT_CERTS` | Integer | `10` | Default weight percentage for certifications and licenses. |
| `DEFAULT_MIN_EXP` | Float | `0.0` | Default minimum experience threshold for knockout rules. |

---

## 4. AI Provider Settings

| Setting Key | Default | Description |
|---|---|---|
| `ACTIVE_PROVIDER` | `"ollama"` | Active AI provider (`"ollama"`, `"nvidia"`, `"openai"`, `"gemini"`, `"groq"`, `"anthropic"`, `"openrouter"`, `"github"`). |
| `OLLAMA_BASE_URL` | `"http://127.0.0.1:11434"` | Endpoint URL for the local Ollama daemon. |
| `OLLAMA_MODEL` | `"llama3.2:3b"` | Model used for local Ollama inference. |
| `NVIDIA_API_KEY` | `""` | Encrypted API key for NVIDIA NIM cloud inference. |
| `OPENAI_API_KEY` | `""` | Encrypted API key for OpenAI API. |
| `GEMINI_API_KEY` | `""` | Encrypted API key for Google Gemini API. |
| `GROQ_API_KEY` | `""` | Encrypted API key for Groq Cloud. |
| `ANTHROPIC_API_KEY` | `""` | Encrypted API key for Anthropic Claude. |
| `OPENROUTER_API_KEY` | `""` | Encrypted API key for OpenRouter. |
| `GITHUB_TOKEN` | `""` | Encrypted token for GitHub Models inference. |

---

## 5. Security & Encryption Settings

| Setting Key | Default | Description |
|---|---|---|
| `SECRET_KEY` | Auto-generated | Flask session encryption key. Cryptographically generated on first launch. |
| `ARS_ENCRYPTION_KEY` | Auto-generated | Base64 AES-Fernet master key used for encrypting API credentials and resumes at rest. Derived via PBKDF2. |
| `LOGIN_ENABLED` | `True` | Enforces HR password authentication. Set to `False` in closed personal desktop sessions. |
| `HR_USERNAME` | `"admin"` | Default HR dashboard administrator username. |
| `HR_PASSWORD_HASH` | Scrypt Hash | Scrypt-hashed administrator password. |
| `RATE_LIMIT_RPM` | `60` | Maximum allowed API requests per minute per IP address on public candidate endpoints. |
| `MAX_UPLOAD_SIZE_MB` | `25` | Maximum upload size in megabytes for candidate resumes. |

---

## 6. Email & Invitation Notifications

| Setting Key | Default | Description |
|---|---|---|
| `SMTP_HOST` | `"smtp.gmail.com"` | Outbound SMTP server hostname. |
| `SMTP_PORT` | `587` | Outbound SMTP server port (587 for TLS, 465 for SSL). |
| `SMTP_USER` | `""` | Username or email address for SMTP authentication. |
| `SMTP_PASSWORD` | `""` | Encrypted password or app-specific password for SMTP. |
| `SMTP_USE_TLS` | `True` | Enables STARTTLS encryption for outbound email dispatch. |
| `EMAIL_TEMPLATE_SUBJECT`| `"Interview Invitation: {job_title}"` | Email subject line with placeholder tokens. |
| `EMAIL_TEMPLATE_BODY` | Standard text | Plain-text email body template supporting `{candidate_name}`, `{job_title}`, `{interview_link}`, `{slot}`. |
