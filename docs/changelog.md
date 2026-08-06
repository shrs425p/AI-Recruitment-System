# Changelog

All notable changes to the **AI Recruitment System** project are documented in this file.

## [1.1.0] - Production Release - 2026-08-05

### Added
- **Candidate API Rate Limiting**: Added thread-safe token bucket rate limiting (`app/rate_limiter.py`) protecting `/api/candidate/*` endpoints against request flooding.
- **Centralized HTTP Error Middleware**: Global Flask error handlers in `app/__init__.py` returning JSON for API endpoints (400, 403, 404, 429, 500) and styled pages for web routes.
- **Pre-Flight Environment Diagnostic Verifier**: CLI script `scripts/verify_environment.py` checking Python version, dependencies, SQLite schema/indexes, Tesseract OCR path, and Ollama connectivity.
- **Database Context Manager**: `@contextmanager def db_session()` in `app/database.py` with auto-commit, automatic exception rollback, and connection cleanup.
- **SQLite Performance & Lock Resilience**: Added `PRAGMA busy_timeout = 10000` and database indexes on `candidates(run_id)`, `schedules(run_id)`, `schedules(status)`, and `interview_tokens(token)`.
- **Fault-Tolerant LLM JSON Extraction**: Enhanced `clean_json_response()` in `app/utils.py` to repair trailing commas in objects and arrays emitted by smaller local models.
- **Interview Session TTL Expiration**: Added 2-hour session lifetime and `_cleanup_expired_sessions()` helper to `app/routes/interview.py` preventing memory accumulation.
- **Expanded Test Suite**: Added 13 new unit/integration tests covering rate limiting, database transactions, error handling, session TTL, ranking weights, and NLP prompts (25 total tests).

### Changed
- Standardized logging across core modules (`pdf_to_txt`, `nlp_extractor`, `ranking_engine`, `interview_bot`).
- Added package initialization `src/__init__.py` and import fallbacks in `app/utils.py`.

---

## [1.0.0] - Initial Release - 2026-08-01

- Initial offline-first recruitment pipeline release.
- PDF/OCR text extraction, NLP parsing, candidate ranking, interview portal, and report generation.
