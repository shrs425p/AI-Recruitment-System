# Testing

This document details the test suite architecture, how to run tests, and how each domain-scoped test module operates.

---

## Overview

The test suite contains **140 tests** organized into 14 domain-focused test modules in `tests/`, verified under Python 3.10+ using `pytest`.

```
tests/
├── conftest.py              # Shared fixtures: temporary directories, SQLite DB, Flask clients
├── test_airgap.py           # Offline asset bundling, zero CDN checks
├── test_api.py              # System health, stats, background task workers, desktop integration
├── test_auth.py             # User authentication, password hashes, desktop nonces, route boundaries
├── test_db.py               # Database schema constraints, CRUD operations, concurrency, rollback
├── test_intelligence.py     # Semantic vector search, candidate comparisons, 6 analytics calculators
├── test_interview.py        # Role-adaptive blueprints, adaptive follow-up probing, scoring rubrics
├── test_nlp.py              # JSON repair, entity extraction schema, provider routing endpoint security
├── test_proctor.py          # Webcam face detection counters, anti-tamper timers, fast paste detection
├── test_ranking.py          # Weight balancing, knockout criteria, scoring engine, CSV spreadsheet export
├── test_reports.py          # Combined scoring, PDF binary generation, HR notification lifecycle
├── test_resume.py           # Word (.docx) parsing, PDF extraction, upload whitelisting, duplicate handling
├── test_schedule.py         # Slot allocation, calendar connectivity, email template substitution
├── test_security.py         # CSRF validation, sliding-window rate limiting, GDPR asset purge, AES encryption
└── test_voice.py            # TTS markdown formatting, voice session lifecycle, speech recognition fallbacks
```

---

## Running Tests

### Run all tests
```bash
pytest
```

### Run with verbose output
```bash
pytest -v
```

### Run a specific domain module
```bash
pytest tests/test_ranking.py -v
```

### Run a specific test class or function
```bash
pytest tests/test_auth.py::TestDesktopNonceSecurity::test_desktop_login_single_use_replay_prevention -v
```

### Run with coverage reporting
```bash
pytest --cov=app --cov=src --cov-report=term-missing
```

---

## Test Fixtures (`tests/conftest.py`)

Shared fixtures are centralized in [`tests/conftest.py`](file:///c:/Users/Shrs/OneDrive/Desktop/AI-Recruitment-System/tests/conftest.py):

| Fixture | Scope | Description |
|---|---|---|
| `temp_dir` | function | Isolated temporary directory on disk, automatically cleaned up after test completion |
| `test_db` | function | Fresh, temporary SQLite database initialized with all 9 table schemas |
| `app` | function | Flask application instance configured for testing with test DB and mocked folders |
| `candidate_app` | function | Secondary candidate portal Flask application instance configured with TLS |
| `client` | function | Unauthenticated test client for testing public and rejected routes |
| `auth_client` | function | Pre-authenticated test client with active HR session and matching CSRF headers |
| `candidate_client` | function | Candidate portal test client for interview session workflows |
| `sample_pdf_bytes` | function | In-memory minimal valid binary PDF byte stream |
| `sample_docx_bytes`| function | In-memory minimal valid Microsoft Word `.docx` byte stream |
| `sample_token_payload` | function | Pre-populated interview token record for candidate testing |

---

## Module Coverage Reference

### 1. Air-Gap & Offline Compliance ([`tests/test_airgap.py`](file:///c:/Users/Shrs/OneDrive/Desktop/AI-Recruitment-System/tests/test_airgap.py))
- Verifies physical presence of local Inter and JetBrainsMono fonts in `app/static/fonts/`.
- Verifies presence of bundled `chart.umd.min.js` in `app/static/js/`.
- Audits all HTML templates in `app/templates/` to assert zero external CDN or Google Font references.

### 2. Core REST API & Background Workers ([`tests/test_api.py`](file:///c:/Users/Shrs/OneDrive/Desktop/AI-Recruitment-System/tests/test_api.py))
- `/api/health`: Database connectivity and health payload.
- `/api/stats`: Ingestion and extraction telemetry counters.
- `/api/task-status`: Pipeline background worker execution states.
- Error handlers: Structured JSON RFC error envelopes for API routes vs HTML pages.
- Desktop integration: Traversal defense and folder launcher validation.
- Background jobs: Triggering auto-pipeline and pipeline state reset.

### 3. Authentication & Access Boundaries ([`tests/test_auth.py`](file:///c:/Users/Shrs/OneDrive/Desktop/AI-Recruitment-System/tests/test_auth.py))
- Password authentication: Scrypt verification and automatic plaintext password migration on initial login.
- Desktop Nonce security: Single-use cryptographic nonces, replay rejection, invalid nonce blocking.
- Access boundaries: Unauthenticated rejection across all HR endpoints, candidate portal isolation.

### 4. Database Schema & Concurrency ([`tests/test_db.py`](file:///c:/Users/Shrs/OneDrive/Desktop/AI-Recruitment-System/tests/test_db.py))
- Schema validation across all 9 tables (`runs`, `candidates`, `schedules`, `interview_tokens`, `interview_sessions`, `job_templates`, `hr_notifications`, `app_settings`, `talent_embeddings`).
- Foreign key constraints, candidate score ordering, and notes/tagging updates.
- Concurrency: 15-thread simultaneous write safety in SQLite.
- Bulk operations: High-throughput ingestion of 500 candidate records.

### 5. Talent Intelligence & Analytics ([`tests/test_intelligence.py`](file:///c:/Users/Shrs/OneDrive/Desktop/AI-Recruitment-System/tests/test_intelligence.py))
- Vector embedding generation and storage in SQLite.
- Semantic talent pool search with schema-key filtering.
- Candidate comparison matrix and executive deliberation briefs.
- AI feedback letter generation with template fallbacks.
- Complete analytics calculators: Skill Gap, Experience Matrix, Question Difficulty, Proctoring Risk, Velocity Tracker, Talent Mix.

### 6. Adaptive Interview Engine ([`tests/test_interview.py`](file:///c:/Users/Shrs/OneDrive/Desktop/AI-Recruitment-System/tests/test_interview.py))
- Role-adaptive blueprints: Distinction between technical (`is_tech_role`) and non-technical domains.
- Adaptive probing: Triggering follow-up questions when candidate answers lack depth (`should_probe_further`).
- Multi-dimensional answer evaluation rubrics (relevance, depth, clarity, correctness).
- Candidate interview submission endpoints with HMAC session keys.

### 7. NLP Extraction & Provider Security ([`tests/test_nlp.py`](file:///c:/Users/Shrs/OneDrive/Desktop/AI-Recruitment-System/tests/test_nlp.py))
- JSON cleaning and sanitization: Code fence stripping, conversational preamble extraction, trailing comma repairs.
- NLP extraction schema verification.
- ProviderRouter validation: Placeholder key rejection and endpoint URL scheme enforcement (`http`/`https`).

### 8. Proctoring & Anti-Tamper Integrity ([`tests/test_proctor.py`](file:///c:/Users/Shrs/OneDrive/Desktop/AI-Recruitment-System/tests/test_proctor.py))
- WebcamProctor lifecycle, missing cascade resilience, and webcam fallback modes.
- Threshold counting: Zero-face detection and multi-face alerts.
- Anti-tamper timing: Server-side elapsed time calculation (disregarding client-forged timestamps).
- Instant paste detection (<2.0s for >5 words) and response delay flags.

### 9. Candidate Ranking & CSV Export ([`tests/test_ranking.py`](file:///c:/Users/Shrs/OneDrive/Desktop/AI-Recruitment-System/tests/test_ranking.py))
- Weight auto-balancing when weights do not sum to 100.
- Knockout rules: Minimum experience knockout and mandatory required skills knockout.
- Composite score calculation and rubric clamping.
- RFC 4180 CSV spreadsheet export with role-based authentication.

### 10. Evaluation Reports & HR Notifications ([`tests/test_reports.py`](file:///c:/Users/Shrs/OneDrive/Desktop/AI-Recruitment-System/tests/test_reports.py))
- Combined score calculation (40% resume fit + 60% interview performance).
- FPDF2 Latin-1 binary PDF report generation.
- Automated HR desktop notifications upon interview completion, unread counts, and mark-as-read transitions.

### 11. Document Extraction & Whitelisting ([`tests/test_resume.py`](file:///c:/Users/Shrs/OneDrive/Desktop/AI-Recruitment-System/tests/test_resume.py))
- Microsoft Word `.docx` parsing via `python-docx`.
- Digital PDF text extraction.
- Upload extension whitelist enforcement (`.pdf`, `.docx`) and rejection of unapproved extensions.
- Duplicate filename collision handling (appending numeric counters).

### 12. Interview Scheduling & Notifications ([`tests/test_schedule.py`](file:///c:/Users/Shrs/OneDrive/Desktop/AI-Recruitment-System/tests/test_schedule.py))
- Top-N candidate slot allocation and in-place slot updating.
- Google Calendar connectivity status checks.
- Email invitation dispatch with dynamic placeholder template substitution.

### 13. Security, Encryption & GDPR Compliance ([`tests/test_security.py`](file:///c:/Users/Shrs/OneDrive/Desktop/AI-Recruitment-System/tests/test_security.py))
- CSRF validation (`X-CSRF-Token` header) and token tampering rejection.
- In-memory sliding-window rate limiting per IP address.
- Candidate privacy consent gating before starting interviews.
- GDPR candidate asset purging: Deleting database records and unlinking all associated files on disk.
- AES-Fernet encryption at rest for database secrets and uploaded documents.
- Prompt injection defense: XML container isolation and PII sanitization.
- Self-signed TLS certificate generation.

### 14. Voice Synthesis & Speech Recognition ([`tests/test_voice.py`](file:///c:/Users/Shrs/OneDrive/Desktop/AI-Recruitment-System/tests/test_voice.py))
- Markdown formatting stripping for text-to-speech queues.
- VoiceSession lifecycle, question announcements, and mute toggling.
- Speech recognition uninitialized error handling and Google speech fallback.

---

## Static Code Analysis and Formatting

Linting and formatting standards are enforced via Ruff:

```bash
# Check for lint errors
ruff check tests/

# Check formatting
ruff format --check tests/

# Apply automated formatting fixes
ruff format tests/
```
