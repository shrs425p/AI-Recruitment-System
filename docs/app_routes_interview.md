# Documentation for `interview.py`

**Path:** `app/routes/interview.py`

## Module Docstring
No module-level docstring provided.

## Role
The `interview.py` module serves as an API controller or route handler within the Flask web framework.

## Working
It listens to HTTP requests on defined routes, processes incoming data, and delegates business logic to internal services.

## How it works
It defines route functions (like various endpoints) mapped to specific URLs. It validates request payloads, interacts with the database or AI engines, and returns JSON responses.

## Why it works
By separating route definitions from core business logic (in `src/`), the architecture remains modular. It leverages Flask Blueprints to logically group related endpoints.

## Detailed Components

### Imports
- `logging`
- `hmac`
- `json`
- `re`
- `secrets`
- `time`
- `uuid`
- `flask.jsonify`
- `flask.render_template`
- `flask.request`
- `app.core.OUTPUT_FOLDER`
- `app.database.create_interview_token`
- `app.database.get_all_tokens`
- `app.database.get_interview_token`
- `app.rate_limiter.SimpleRateLimiter`
- `app.utils.login_required`
- `src.interview_bot.evaluate_answer`
- `src.interview_bot.generate_interview_question`
- `src.interview_bot.proctor_check`
- `src.webcam_proctor.start_proctoring`
- `src.webcam_proctor.stop_proctoring`

### Global Variables
- `logger`
- `rate_limiter`
- `INTERVIEW_PLAN`
- `SESSION_TTL_SECONDS`

### Classes
No classes found.

### Functions
#### `_cleanup_expired_sessions()`
**Docstring:** Remove expired interview sessions from memory.

#### `_save_sessions()`
**Docstring:** No function docstring provided.

#### `_client_fingerprint()`
**Docstring:** No function docstring provided.

#### `_session_key_from_request(data)`
**Docstring:** No function docstring provided.

#### `_get_candidate_session(data)`
**Docstring:** No function docstring provided.

#### `_question_payload(question_text, q_num)`
**Docstring:** No function docstring provided.

#### `register_interview_routes(app)`
**Docstring:** No function docstring provided.
