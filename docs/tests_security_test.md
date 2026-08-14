# Documentation for `security_test.py`

**Path:** `tests/security_test.py`

## Module Docstring
security_test.py - Hard security tests for the AI Recruitment System.

Tests:
 1. HR routes return 401 with no session (no browser access)
 2. /desktop-bootstrap refuses to authenticate without a valid nonce
 3. /api/desktop-login returns 403 with a bogus nonce
 4. /api/desktop-login returns 403 with an empty body
 5. /api/desktop-login returns 403 with a replayed (already used) nonce
 6. /api/desktop-login is rate-limit resistant (does not leak timing info)
 7. Candidate routes are publicly accessible (no session needed)
 8. /login page returns 403 in browser mode (LOGIN_ENABLED=False)
 9. HR API routes return 401, not a redirect, for API clients
10. No HR route is accidentally public (enumeration check)
11. Session fixation: session.clear() happens before granting access

## Role
The `security_test.py` module is a test suite ensuring the reliability and correctness of specific application features.

## Working
It uses the `pytest` testing framework to execute various test cases against the application codebase.

## How it works
It works by defining test functions (e.g., check, get, post...) that simulate inputs and assert expected outcomes.

## Why it works
This automated testing approach guarantees that regressions are caught early. Using fixtures and mocking, it tests components in isolation without affecting the real database or external services.

## Detailed Components

### Imports
- `os`
- `secrets`
- `sys`
- `time`
- `requests`

### Global Variables
- `BASE`
- `PASS`
- `FAIL`
- `results`

### Classes
No classes found.

### Functions
#### `check(name, condition, details)`
**Docstring:** No function docstring provided.

#### `get(path)`
**Docstring:** No function docstring provided.

#### `post(path)`
**Docstring:** No function docstring provided.
