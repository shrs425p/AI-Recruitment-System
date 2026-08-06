# Security & Production-Readiness Audit

## Summary
- **Scope:** repo scan (source only), full test run, dependency review, hardcode detection. Focus: produce a production-grade hardening checklist while keeping the project usable for local/dev work.
- **Date:** 2026-08-05
- **Status:** Tests pass (30/30). Multiple hardcoded/default credentials and configuration issues found. See Findings and Remediation.

## Quick Findings (high priority)
- `HR_PASSWORD` defaults in [config/config.py](config/config.py#L1) and similar fallbacks in [main.py](main.py#L1) — move secrets to env or secret manager.
- AI provider keys referenced in [app/utils.py](app/utils.py#L1) and possibly `src/` modules — ensure they are not committed and are loaded from secure config.
- Tests contain hardcoded secrets (e.g., `app.secret_key = "test-secret"`) in [tests/test_auto_pipeline.py](tests/test_auto_pipeline.py#L1) and [tests/test_auth.py](tests/test_auth.py#L1) — use fixtures or env overrides.
- `scan_hardcodes.py` reports numerous matches across `src/` (report stored locally) — review matches and triage false positives.
- `requirements.txt` contains broad ranges; pin critical production packages and run SCA (software composition analysis).

## Production-Grade Remediation Checklist (prioritized)
1. Secrets & Configuration
   - Centralize configuration using environment variables with a strict loader (e.g., `python-dotenv` for local dev, or a secrets manager integration for real deployments).
   - Remove all hardcoded credentials from source and tests. Rotate any secrets accidentally committed.
   - Add a `config.example.env` documenting required env vars (no values).

2. Secrets Detection & Git Hygiene
   - Add `pre-commit` with `detect-secrets` and `pre-commit-hooks` to block commits containing secrets.
   - Add `git-secrets` or `truffleHog` to CI as an additional gate.
   - Ensure `.gitignore` excludes `venv/`, `hardcode_results.json`, and other local artifacts. Current `.gitignore` references `hardcode_results.json`.

3. Dependency Security
   - Pin production-critical dependency versions in `requirements.txt` or add a `requirements.lock`/`constraints.txt`.
   - Add `pip-audit` or `safety` to CI; run locally now:

```powershell
venv\\Scripts\\python -m pip install pip-audit
venv\\Scripts\\pip-audit
```

4. CI / Automation
   - Add a CI workflow (GitHub Actions or equivalent) that runs:
     - `pytest -q`
     - `pip-audit` (fail on high/critical findings)
     - `pre-commit` hooks or `detect-secrets` scan
   - Optionally run SAST (e.g., `semgrep`) and DAST for web endpoints.

5. Runtime & App Hardening
   - Add input validation and strict file upload handling (size limits, type checks, scan uploaded resumes for malicious content).
   - Sanitize candidate data and minimize PII retention. Encrypt sensitive data at rest (AES-256) and in transit (HTTPS/TLS). Document retention policy.
   - Add rate-limiting (existing `rate_limiter.py`) and ensure it is enabled for public endpoints.
   - Secure session management: set `SESSION_COOKIE_SECURE`, `SameSite`, and use strong secrets for Flask `SECRET_KEY`.

6. ML / AI Safety
   - Treat LLM inputs/outputs as untrusted. Add prompt validation and sanitization, and log prompts (redacting PII) for auditability.
   - Limit context sent to external models; enforce rate-limits and provider quotas.
   - Add a model-usage policy and a safety review for prompts that process resumes/interviews (privacy + bias considerations).

7. Observability & Incident Response
   - Add structured logging (JSON) and a configurable log level. Send to file and/or a logging backend in staging.
   - Add health checks and readiness probes (see `app/routes/health.py`).
   - Add basic monitoring/alerting for high error rates, high latency, or abnormal model usage.

8. Testing & Quality
   - Keep or expand unit tests and add integration tests for critical flows (auth, upload, ranking, scheduling).
   - Add fuzzing or property-based tests for parsing resume content.

## Concrete, Minimal Changes I Can Apply Now (pick by letter)
- A) Replace test hardcoded secrets with fixtures/env usage and re-run tests. (safe, small patch)
- B) Run `pip-audit` and append a vulnerability section to this report. (quick scan)
- C) Add `pre-commit` config and a basic GitHub Actions `ci.yml` that runs tests + `pip-audit` + `detect-secrets`. (medium change)
- D) Create `config.example.env`, add guidance in `README.md`, and update `config/config.py` to load from `os.getenv`. (small change)

## Short-Term Priorities (first 48–72 hours)
1. Replace secrets in tests and add `config.example.env` (A + D). Verify tests pass.
2. Add `pre-commit` locally and run `detect-secrets` to catch any remaining issues.
3. Run `pip-audit` and fix/upgrade any high/critical CVEs.

## Long-Term / Optional (production-ready)
- Containerize with a small `Dockerfile`, add multi-stage build and non-root user.
- Add an infrastructure-as-code blueprint (Terraform) and a deployment checklist (TLS certs, secret rotation, RBAC).
- Add SAST (Semgrep), DAST, and a secure release checklist (vulnerability triage, third-party license checks).

## Findings (files of interest)
- `config/config.py` — defaults and config loading. See [config/config.py](config/config.py#L1).
- `main.py` — app entrypoint and default fallbacks. See [main.py](main.py#L1).
- `app/utils.py` — AI provider usage. See [app/utils.py](app/utils.py#L1).
- `tests/` — contains a few hardcoded test secrets. See [tests/test_auto_pipeline.py](tests/test_auto_pipeline.py#L1) and [tests/test_auth.py](tests/test_auth.py#L1).
- `scan_hardcodes.py` — scanner used; keep and refine its regexes. See [scan_hardcodes.py](scan_hardcodes.py#L1).

## Next steps — I can run these now if you say which:
1) Run `pip-audit` and append results to this file. (recommended next step)
2) Apply safe code patches: replace test secrets and add `config.example.env` + update `config/config.py` to use env vars.
3) Add `pre-commit` and a starter CI workflow.

---
Report created/updated 2026-08-05. Ask me to run any of the concrete steps above and I'll proceed.
