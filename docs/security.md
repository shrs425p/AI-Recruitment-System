# Security

This document covers all the security mechanisms in the system: authentication, credential encryption, the nonce-based desktop login, HTTPS for the candidate portal, and rate limiting.

---

## Desktop Authentication (Nonce System)

The HR dashboard runs on `http://127.0.0.1:5001` (loopback only). When the pywebview window opens, it needs to authenticate with Flask without exposing a password in a URL or relying on a standard login form.

This is done with a **one-time nonce system**:

```
pywebview window opens (http://127.0.0.1:5001/desktop-bootstrap)
          │
          │ page loads JS
          │
          ▼
window.pywebview.api.get_auth_nonce()
          │
          │ calls Python directly via pywebview JS bridge
          │
          ▼
main.py: Api.get_auth_nonce()
  - generates secrets.token_urlsafe(32) → cryptographically random 32-byte nonce
  - adds nonce to app.config["_NONCE_POOL"] (a set, protected by threading.Lock)
  - returns nonce to JS
          │
          ▼
JS: POST /api/desktop-login  { nonce: "<value>" }
          │
          ▼
Flask: api_desktop_login()
  - acquires _NONCE_LOCK
  - checks if nonce is in _NONCE_POOL
  - if yes: removes it (single-use), sets session["logged_in"] = True
  - if no: returns 403
```

**Why this works:**
- The nonce is generated in Python and shared to JS via the pywebview bridge (not via HTTP)
- Each nonce is single-use — replaying it fails
- The nonce pool is cleared on application restart
- The login endpoint is on loopback only — no external device can reach it

---

## HR Dashboard Login (Optional)

When `LOGIN_ENABLED = True`, the HR dashboard requires a username and password.

- Passwords are hashed using `werkzeug.security.generate_password_hash` (scrypt algorithm by default)
- The hash is stored in the database (`HR_PASSWORD_HASH`), never the plain-text password
- Login uses `check_password_hash` for constant-time comparison (prevents timing attacks)
- Sessions are server-side Flask sessions signed with `FLASK_SECRET_KEY`
- Session lifetime: 8 hours (`PERMANENT_SESSION_LIFETIME`)
- Session cookies: `HttpOnly=True`, `SameSite=Lax`

When `LOGIN_ENABLED = False` (the default), the nonce-based desktop login still runs for the pywebview window, but the standard web login form is not shown.

---

## Data & Credential Encryption at Rest

Sensitive configuration values, candidate personally identifiable information (PII), and uploaded resume files on disk are encrypted at rest using AES-Fernet.

### Key Derivation (`src/security.py`)
1. A 16-byte cryptographically random salt is generated on first initialization and stored at `%LOCALAPPDATA%\AI Recruitment System\.secret_salt`.
2. PBKDF2-HMAC-SHA256 is executed with 100,000 iterations and the application identifier.
3. The derived 32-byte key is base64-encoded and used to instantiate the AES-Fernet cipher.

### 1. Configuration Credentials
Sensitive settings in the SQLite database (`app_settings` table) are stored with an `ENC:` prefix:
```
ANTHROPIC_KEY, GEMINI_KEY, GROQ_KEY, OPENAI_KEY,
NVIDIA_KEY, OPENROUTER_KEY, GITHUB_KEY, OLLAMA_CLOUD_KEY,
SMTP_PASSWORD, FLASK_SECRET_KEY
```
- `encrypt_secret("plaintext")` -> `"ENC:gAAAAAB..."`
- `decrypt_secret("ENC:gAAAAAB...")` -> `"plaintext"`

### 2. Candidate Database Records (PII)
Candidate names, email addresses, and phone numbers stored within the local SQLite database are encrypted at rest with AES-Fernet before writing to disk, and decrypted into memory only during active HR workflows.

### 3. Uploaded Resume Files on Disk
Resumes stored in `data/resumes/` are encrypted at rest using `encrypt_bytes()`, adding an `ARS_ENC:` binary magic prefix. When `pdf_to_txt.py` or OCR processes these files, `decrypt_bytes()` decrypts them directly in-memory without writing unencrypted temporary files to disk.

### The Salt File
The master AES-Fernet key is derived from the salt at `%LOCALAPPDATA%\AI Recruitment System\.secret_salt`. If this file is removed or corrupted, encrypted credentials, stored PII, and encrypted resume files cannot be decrypted. Backup routines should preserve both `ars.db` and `.secret_salt` together.

---

## HTTPS for the Candidate Portal

The candidate interview portal (port 5000) runs over HTTPS with a self-signed TLS certificate.

**Certificate generation** happens automatically on first run:
- RSA 2048-bit private key
- Self-signed X.509 certificate (10-year validity, localhost CN)
- Saved to `data/output/ssl/cert.pem` and `key.pem`
- Uses the `cryptography` library

**Why self-signed?**
The candidate portal runs on a local network (LAN), not a public domain, so a CA-signed certificate is not obtainable. Candidates will see a browser warning — they need to click "Advanced → Proceed" to continue.

For a production deployment with a public domain, you could replace `cert.pem`/`key.pem` with a Let's Encrypt certificate and the HTTPS server would use it automatically.

---

## Route Protection

Two mechanisms protect the HR dashboard routes from unauthorised access:

### 1. `@login_required` Decorator
Applied to all HR-only routes by `protect_hr_routes()` in `app/utils.py`. If the session does not have `logged_in = True`, the request is redirected to the login page (for browser requests) or returns 401 JSON (for API requests).

### 2. Public Path Exemptions
These paths bypass `login_required` and are accessible without authentication:
```
/candidate-interview/    ← Candidate portal (token-authenticated separately)
/api/desktop-login       ← Nonce-based desktop auth endpoint
/login                   ← Login form
/health                  ← Health check endpoint
/static/                 ← Static assets
```

---

## Security Headers

Every HTTP response includes these headers (added by `add_security_headers` in `app/__init__.py`):

| Header | Value | Purpose |
|---|---|---|
| `Cache-Control` | `no-store` | Prevent browser from caching sensitive pages |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Limit referrer info sent cross-origin |
| `X-Content-Type-Options` | `nosniff` | Prevent MIME-type sniffing |
| `X-Frame-Options` | `SAMEORIGIN` | Prevent clickjacking via iframes |

---

## Rate Limiting

The application includes a rate limiter (`app/rate_limiter.py`) to prevent abuse of the API endpoints.

Rate limiting is applied to:
- `/api/desktop-login` — nonce consumption endpoint
- AI-triggered endpoints (NLP extraction, ranking, interview answer evaluation)

The limiter uses a bounded-capacity sliding window algorithm with automatic LRU purging to prevent memory exhaustion attacks. Requests exceeding thresholds return HTTP 429 (`Too Many Requests`).

---

## CSRF Protection

Cross-Site Request Forgery (CSRF) protection is enforced across the application using `Flask-WTF` and custom header verification:

- **HR Dashboard & Management APIs:** All state-changing HTTP requests (`POST`, `PUT`, `DELETE`, `PATCH`) require a valid CSRF token provided via the `X-CSRF-Token` HTTP header or form parameter.
- **Candidate Portal Exemption & Isolation:** Candidate interview endpoints (`/candidate-interview/`, `/api/candidate/`) do not use browser session cookies for state. Instead, they require a cryptographically generated HMAC session key (`X-Session-Key` header or payload) verified against the active in-memory session. Because ambient cookie credentials are not accepted for candidate state changes, cookie-based CSRF is structurally prevented.

---

## Session Security

Flask sessions are signed with `FLASK_SECRET_KEY`. If this key is not set in config, the app generates a random one via `secrets.token_hex(32)` on each startup — meaning all existing sessions are invalidated on restart.

To keep sessions persistent across restarts, set a fixed `FLASK_SECRET_KEY` in Settings.

Session settings:
- `SESSION_COOKIE_HTTPONLY = True` — JS cannot access the session cookie
- `SESSION_COOKIE_SAMESITE = "Lax"` — limits cookie transmission on cross-site requests
- `PERMANENT_SESSION_LIFETIME = timedelta(hours=8)` — sessions expire after 8 hours

---

## Candidate Token Security

Interview tokens are UUIDs generated with `uuid.uuid4()`. They are:
- Single-use per interview run (completing the interview invalidates the token)
- Stored in the database linked to the candidate name and job title
- Protected on every request during the session using HMAC-signed session keys (`X-Session-Key`)

---

## Prompt Sandboxing & PII Minimization

To defend against indirect prompt injection and maintain candidate privacy:

- **Input Sandboxing:** Untrusted candidate responses and resume extracts are wrapped in explicit boundary tags (e.g. `<candidate_answer>...</candidate_answer>`) and sanitized to strip instruction-override patterns before evaluation prompts are assembled.
- **PII Minimization:** Raw candidate contact details (phone numbers, full street addresses, email addresses) are stripped before sending text to external LLMs for scoring or question generation. Only technical experience and relevant domain data are included in evaluation payloads.

---

## Supply Chain & Permissive Licensing

The application strictly utilizes commercially permissive licenses (MIT, BSD-3-Clause, Apache-2.0):
- PDF text extraction relies on `pypdf` (BSD-3-Clause), eliminating AGPL copyleft encumbrances associated with libraries like PyMuPDF.
- All dependencies are vetted for production use in Windows enterprise desktop environments.
