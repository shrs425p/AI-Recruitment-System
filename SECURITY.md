# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.x (latest) | ✅ Active support |
| < 1.0 | ❌ End of life |

---

## Reporting a Vulnerability

**Please do NOT open a public GitHub Issue for security vulnerabilities.**

Report security issues privately using one of the following methods:

### Option 1 — GitHub Security Advisory (Preferred)
1. Go to the repository on GitHub.
2. Click **Security → Advisories → Report a vulnerability**.
3. Fill in the advisory form with as much detail as possible.

### Option 2 — Email
Send a detailed report to **pawarshreyas425@gmail.com** with the subject line:
`[SECURITY] AI-Recruitment-System — <brief description>`

Please include:
- A description of the vulnerability and its impact.
- Steps to reproduce (proof-of-concept code if safe to share).
- Affected versions / components.
- Your suggested fix or mitigation (optional but appreciated).

---

## Response SLA

| Stage | Target |
|-------|--------|
| Initial acknowledgement | Within **48 hours** |
| Severity assessment | Within **5 business days** |
| Patch / mitigation | **Critical**: ≤ 7 days · **High**: ≤ 14 days · **Medium/Low**: next release |
| CVE assignment | Requested for Critical/High issues where applicable |

---

## Scope

### In scope
- `app/` — Flask backend routes, authentication, rate limiting
- `src/` — AI routing, NLP extraction, ranking engine
- `main.py` — Desktop launcher, pywebview integration
- Authentication flows (JWT, session validation, nonce-based desktop login)
- Candidate PII handling (encryption at rest, data retention)
- Dependency vulnerabilities (CVEs in `requirements.txt`)

### Out of scope
- Vulnerabilities in upstream dependencies that have already been publicly reported
- Social engineering attacks
- Denial-of-service against the single-tenant local server
- Issues in demo/sample data (`scripts/generate_resumes.py`)

---

## Data Handling & PII Statement

The AI Recruitment System is designed as a **privacy-first, single-tenant desktop application**:

- **Candidate PII** (names, emails) is encrypted at rest using **AES-256-GCM** with a key protected by Windows DPAPI.
- **Local-only mode**: all AI inference can run on-device via Ollama — zero data egress.
- **No telemetry** is sent by default. Opt-in error reporting (`TELEMETRY_ENABLED = True` in `config.py`) sends anonymous crash reports to Sentry with `send_default_pii=False`.
- Data retention is configurable (`GDPR_RETENTION_DAYS`) and candidates can be permanently deleted via the HR dashboard.
- Secrets (API keys) are stored in the OS keystore (Windows DPAPI), not in source files.

---

## Preferred Languages

We accept vulnerability reports in **English**.

---

## Acknowledgements

We credit researchers who responsibly disclose valid vulnerabilities in the project changelog and, if desired, in this file.
