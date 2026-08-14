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

## Credential Encryption at Rest

All sensitive configuration values (API keys, SMTP password, Flask secret key) are encrypted before being written to the SQLite database.

### How It Works

**Key Derivation** (`src/security.py`):
1. A 16-byte random salt is generated on first run and saved to `%LOCALAPPDATA%\AI Recruitment System\.secret_salt`
2. PBKDF2-HMAC-SHA256 is run with 100,000 iterations and the application name as the password
3. The derived 32-byte key is base64-encoded → used as the AES-Fernet key

**Encryption:**
```python
encrypt_secret("my-api-key")  →  "ENC:gAAAAAB..."
```

**Decryption:**
```python
decrypt_secret("ENC:gAAAAAB...")  →  "my-api-key"
```

**In the database:** Encrypted values are stored with an `ENC:` prefix. The app checks for this prefix before attempting decryption.

### Which Keys Are Encrypted

```
ANTHROPIC_KEY, GEMINI_KEY, GROQ_KEY, OPENAI_KEY,
NVIDIA_KEY, OPENROUTER_KEY, GITHUB_KEY, OLLAMA_CLOUD_KEY,
SMTP_PASSWORD, FLASK_SECRET_KEY
```

All other settings (theme, model names, enabled flags) are stored in plain text.

### Important: The Salt File

The encryption key is derived from the salt at `%LOCALAPPDATA%\AI Recruitment System\.secret_salt`. If this file is deleted or the application is moved to a different machine, the encrypted values **cannot be decrypted**. You will need to re-enter all API keys in Settings.

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
- AI-triggered endpoints (NLP, ranking, interview evaluation)

The limiter tracks requests per IP address and returns HTTP 429 (`Too Many Requests`) when the limit is exceeded. The 429 response is handled by the registered error handler and returns a JSON error or error page.

---

## Session Security

Flask sessions are signed with `FLASK_SECRET_KEY`. If this key is not set in config, the app generates a random one via `secrets.token_hex(32)` on each startup — meaning all existing sessions are invalidated on restart.

To keep sessions persistent across restarts, set a fixed `FLASK_SECRET_KEY` in Settings.

Session settings:
- `SESSION_COOKIE_HTTPONLY = True` — JS cannot access the session cookie
- `SESSION_COOKIE_SAMESITE = "Lax"` — CSRF protection for cross-site requests
- `PERMANENT_SESSION_LIFETIME = timedelta(hours=8)` — sessions expire after 8 hours

---

## Candidate Token Security

Interview tokens are UUIDs generated with `uuid.uuid4()`. They are:
- Single-use per interview run (completing the interview invalidates the token)
- Stored in the database linked to the candidate name and job title
- Not time-expiring by default — the HR manager manually closes sessions if needed

The candidate-facing API routes validate the token on every request during the session using HMAC-signed session keys, not just on the initial load.
