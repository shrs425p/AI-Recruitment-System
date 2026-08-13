# Documentation for `test_auth.py`

**Path:** `tests/test_auth.py`

## Module Docstring
No module-level docstring provided.

## Role
The `test_auth.py` module is a test suite ensuring the reliability and correctness of specific application features.

## Working
It uses the `pytest` testing framework to execute various test cases against the application codebase.

## How it works
It works by defining test functions (e.g., _app, test_login_accepts_hashed_password, test_login_rejects_wrong_password...) that simulate inputs and assert expected outcomes.

## Why it works
This automated testing approach guarantees that regressions are caught early. Using fixtures and mocking, it tests components in isolation without affecting the real database or external services.

## Detailed Components

### Imports
- `flask.Flask`
- `werkzeug.security.generate_password_hash`
- `config`
- `app.create_app`
- `app.routes.auth.register_auth_routes`
- `app.routes.settings.register_settings_routes`
- `src.common.APP_RESOURCE_DIR`

### Global Variables
No global variables found.

### Classes
No classes found.

### Functions
#### `_app()`
**Docstring:** No function docstring provided.

#### `test_login_accepts_hashed_password(monkeypatch)`
**Docstring:** No function docstring provided.

#### `test_login_rejects_wrong_password(monkeypatch)`
**Docstring:** No function docstring provided.

#### `test_remote_user_cannot_open_hr_screen_when_login_disabled(monkeypatch)`
**Docstring:** No function docstring provided.

#### `test_remote_candidate_api_stays_public_when_login_disabled(monkeypatch)`
**Docstring:** No function docstring provided.

#### `test_remote_user_cannot_test_smtp_when_login_disabled(monkeypatch)`
**Docstring:** No function docstring provided.
