# Testing

This document explains how to run the test suite, what each test file covers, and how to add new tests.

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

### Run a specific test file

```bash
pytest tests/test_features.py -v
```

### Run a specific test function

```bash
pytest tests/test_auth.py::test_login_success -v
```

### Run with coverage report

```bash
pip install pytest-cov
pytest --cov=app --cov=src --cov-report=term-missing
```

---

## Test Setup

The test configuration is in `tests/conftest.py`. It:
- Creates a Flask test client with a separate in-memory SQLite database
- Initialises the database schema before each test
- Sets up a logged-in session so route tests don't need to authenticate manually

```python
# conftest.py creates a reusable app fixture:
@pytest.fixture
def client():
    app.config["TESTING"] = True
    app.config["DATABASE"] = ":memory:"
    with app.test_client() as client:
        yield client
```

Tests that need an authenticated session call `login(client)` at the start of the test.

---

## Test Files

### `tests/test_health.py`
Tests the `/health` endpoint returns `{"status": "ok"}` with HTTP 200. Simple sanity check that the Flask app starts.

---

### `tests/test_auth.py`
Tests authentication routes:
- Login with correct credentials returns 302 redirect to dashboard
- Login with wrong password returns 401
- Accessing a protected route without session returns 401/redirect
- Logout clears the session

---

### `tests/test_error_handlers.py`
Tests that the custom error handlers return the correct HTTP status codes and response format:
- 404 returns JSON `{"error": "...", "code": 404}` for API paths
- 404 returns HTML for browser paths
- 500 is handled gracefully

---

### `tests/test_features.py`
Integration tests for core pipeline routes:
- Upload endpoint accepts a valid PDF
- Upload endpoint rejects oversized files
- NLP endpoint returns status correctly
- Ranking endpoint responds to a job description
- Settings save and retrieve correctly

---

### `tests/test_utils.py`
Unit tests for `app/utils.py`:
- `login_required` decorator redirects unauthenticated requests
- Public path prefixes are correctly exempt from login checks
- IP validation helpers work correctly

---

### `tests/test_rate_limiter.py`
Tests the rate limiter:
- Requests within the limit are allowed
- Requests exceeding the limit return HTTP 429
- Rate limit resets after the window expires

---

### `tests/test_interview_session.py`
Tests interview session management:
- Session is created on valid token
- Invalid token returns 403
- Answers are correctly appended to the transcript
- Session ends and transcript is saved

---

### `tests/test_candidate_security.py`
Tests candidate-facing security:
- Cross-session access is blocked (candidate A cannot access session B)
- HMAC session key validation rejects tampered keys
- Tab switch events are recorded correctly
- Copy-paste events are logged

---

### `tests/test_csrf.py`
Tests Cross-Site Request Forgery protections:
- Rejection of unauthenticated state-changing methods lacking `X-CSRF-Token`
- Validation of valid tokens on POST/PUT/DELETE
- Exemption of tokenized candidate portal endpoints

---

### `tests/test_encryption_at_rest.py`
Tests encryption mechanisms:
- AES-Fernet encryption of sensitive keys (`ENC:...`)
- Encryption of candidate PII in database records
- Encryption of uploaded resume files on disk (`ARS_ENC:...`)
- Decryption in memory during extraction

---

### `tests/test_pdf_extraction.py`
Tests PDF parsing using `pypdf`:
- Direct digital text extraction from standard PDFs
- Scanned PDF fallback to OCR
- Decryption of encrypted resume bytes during reading

---

### `tests/test_prompt_injection.py`
Tests prompt sandboxing:
- Neutralization of instruction override strings in candidate answers
- Delimiter boundaries (`<candidate_answer>`) formatting

---

### `tests/test_data_minimization.py`
Tests PII redaction:
- Scrubbing of candidate phone numbers and email addresses before external AI prompt submission

---

### `tests/test_candidate_consent.py` and `tests/test_candidate_deletion.py`
Tests candidate rights and GDPR-style data deletion:
- Recording of candidate consent timestamp
- Complete purging of candidate records and associated artifacts upon request

---

### `tests/test_database.py`
Tests the database ORM layer:
- `init_db()` creates the schema correctly
- `get_setting()` and `set_setting()` work for plain values
- Encrypted values are stored with `ENC:` prefix and decrypted correctly
- Unknown keys return the provided default

---

### `tests/test_nlp_extractor.py`
Unit tests for `src/nlp_extractor.py`:
- Empty resume text returns `(False, "File is empty...")` without calling the AI
- Already-processed files are skipped correctly

---

### `tests/test_ranking_engine.py`
Unit tests for `src/ranking_engine.py`:
- Duplicate candidate detection via dedup hash works correctly
- Score totals add up to 100 max

---

### `tests/test_report_generator.py`
Tests Material Design 3 monochrome PDF report generation:
- PDF document generation with rubrics and candidate profile
- File output saving and JSON companion creation

---

### `tests/test_auto_pipeline.py`
End-to-end pipeline test with mocked AI calls:
- Upload → text extraction → NLP → ranking runs without errors
- Output files are created in the correct locations

---

### `tests/test_tls_cert.py`
Tests HTTPS setup:
- Verification of self-signed TLS certificates for port 5000 candidate server

---

### `tests/test_voice_interview.py`
Tests voice capabilities:
- Offline Vosk STT transcript handling and TTS verification

---

### `tests/test_open_output_folder.py`
Tests the output folder opener utility — verifies the folder path resolves correctly on the current OS.

---

## Writing New Tests

### File naming
- Test files must be named `test_*.py` for pytest to discover them
- Test functions must be named `test_*`

### Example test

```python
# tests/test_my_feature.py
import pytest

def test_something(client):
    """Test that the /api/something endpoint works."""
    response = client.get("/api/something")
    assert response.status_code == 200
    data = response.get_json()
    assert "result" in data

def test_requires_auth(client):
    """Test that /api/protected requires login."""
    response = client.get("/api/protected")
    assert response.status_code in (401, 302)
```

### Mocking AI calls

AI calls in tests should be mocked so tests don't require a live provider:

```python
from unittest.mock import patch

def test_nlp_extraction(client):
    mock_response = {"personal_info": {"name": "Test User"}, "domain": "IT"}
    with patch("src.nlp_extractor.extract_with_ai", return_value=mock_response):
        response = client.post("/api/nlp/run")
        assert response.status_code == 200
```

---

## CI / Continuous Integration

The test suite can be run in CI by:

```bash
pip install -r requirements.txt
pip install pytest pytest-cov
pytest --tb=short
```

Tests that require a display (webcam, pywebview) are designed to be skippable in headless environments via `pytest.mark.skip` or environment variable checks.
