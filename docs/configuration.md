# Configuration

Settings are managed from the Settings page and saved to the active runtime config. Editing config files manually is useful for development, but the UI is safer for normal use.

## Runtime Config Location

| Mode | Config location |
|---|---|
| Development | `config/config.py` mirror plus project runtime paths |
| Packaged app | `%LOCALAPPDATA%\AI Recruitment System\config.py` |

Do not bundle a developer config into installers. The app creates a clean config on first packaged launch.

## Security Settings

| Key | Default | Notes |
|---|---|---|
| `LOGIN_ENABLED` | `False` | Enable for shared machines or LAN access |
| `HR_USERNAME` | `''` | HR login username |
| `HR_PASSWORD` | `''` | Legacy fallback only |
| `HR_PASSWORD_HASH` | `''` | Preferred saved password format |
| `FLASK_SECRET_KEY` | generated | Used for session signing |

When login is enabled, passwords saved through Settings are hashed.

## AI Mode

| Key | Default | Description |
|---|---|---|
| `APP_MODE` | `privacy` | `privacy` uses Ollama; `cloud` uses enabled providers |
| `OLLAMA_MODEL` | `llama3.2:3b` | Local model tag |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Local Ollama endpoint |
| `AI_RETRY_ATTEMPTS` | `3` | Retry count for failed AI calls |
| `AI_RETRY_BACKOFF` | `2` | Backoff multiplier in seconds |

Cloud provider keys and enable flags are described in [AI Providers](ai-providers.md).

## Email Settings

| Key | Default | Description |
|---|---|---|
| `SMTP_HOST` | `smtp.gmail.com` | SMTP server |
| `SMTP_PORT` | `587` | STARTTLS port |
| `SMTP_EMAIL` | `''` | Sender email |
| `SMTP_PASSWORD` | `''` | App password or SMTP password |

Use a Gmail App Password instead of a normal account password.

## HR Profile

| Key | Default | Used by |
|---|---|---|
| `HR_DISPLAY_NAME` | `HR Admin` | Reports, calendar events |
| `HR_EMAIL` | `''` | Calendar events, email metadata |
| `HR_COMPANY` | `''` | UI and report branding |

## Theme Settings

| Key | Default | Options |
|---|---|---|
| `THEME` | `light` | `light`, `dark` |
| `COLOR_PALETTE` | `lavender` | `lavender`, `sage`, `blue`, `rose` |

## Environment Variables

Use these for deployment or smoke testing without editing config files:

| Variable | Purpose |
|---|---|
| `ARS_DESKTOP_PORT` | Preferred local desktop HTTP port |
| `ARS_CANDIDATE_PORT` | Preferred candidate HTTPS port |
| `ARS_CANDIDATE_HOST` | Candidate server bind host, for example `0.0.0.0` |
| `ARS_INSTALLER_OUTPUT` | Output folder for Inno Setup builds |

If a preferred port is unavailable, the app selects a free port automatically.

## Safe Defaults

For a fresh production install:

- Login is disabled until the HR user enables it.
- Credentials are blank.
- Cloud providers are disabled.
- Runtime config is generated per Windows user.
- Existing app data is preserved unless the installer reset task is selected.
