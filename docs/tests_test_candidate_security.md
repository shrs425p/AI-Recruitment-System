# Documentation for `test_candidate_security.py`

**Path:** `tests/test_candidate_security.py`

## Module Docstring
No module-level docstring provided.

## Role
The `test_candidate_security.py` module is a test suite ensuring the reliability and correctness of specific application features.

## Working
It uses the `pytest` testing framework to execute various test cases against the application codebase.

## How it works
It works by defining test functions (e.g., _token_data, _app, test_candidate_answer_requires_session_key...) that simulate inputs and assert expected outcomes.

## Why it works
This automated testing approach guarantees that regressions are caught early. Using fixtures and mocking, it tests components in isolation without affecting the real database or external services.

## Detailed Components

### Imports
- `app.routes.interview`
- `app.create_app`

### Global Variables
No global variables found.

### Classes
No classes found.

### Functions
#### `_token_data()`
**Docstring:** No function docstring provided.

#### `_app(monkeypatch)`
**Docstring:** No function docstring provided.

#### `test_candidate_answer_requires_session_key(monkeypatch)`
**Docstring:** No function docstring provided.

#### `test_candidate_answer_accepts_matching_session_key(monkeypatch)`
**Docstring:** No function docstring provided.

#### `test_candidate_session_is_bound_to_remote_client(monkeypatch)`
**Docstring:** No function docstring provided.

#### `test_candidate_answer_uses_server_issued_question(monkeypatch)`
**Docstring:** No function docstring provided.
