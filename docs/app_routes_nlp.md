# Documentation for `nlp.py`

**Path:** `app/routes/nlp.py`

## Module Docstring
No module-level docstring provided.

## Role
The `nlp.py` module serves as an API controller or route handler within the Flask web framework.

## Working
It listens to HTTP requests on defined routes, processes incoming data, and delegates business logic to internal services.

## How it works
It defines route functions (like various endpoints) mapped to specific URLs. It validates request payloads, interacts with the database or AI engines, and returns JSON responses.

## Why it works
By separating route definitions from core business logic (in `src/`), the architecture remains modular. It leverages Flask Blueprints to logically group related endpoints.

## Detailed Components

### Imports
- `logging`
- `json`
- `threading`
- `time`
- `flask.jsonify`
- `flask.render_template`
- `app.core.OUTPUT_FOLDER`
- `app.core._save_tasks`
- `app.core.pipeline_tasks`
- `app.database.create_run`
- `app.database.finish_run`
- `app.database.upsert_candidate`
- `app.utils.login_required`
- `src.privacy_setup`

### Global Variables
- `logger`
- `privacy_setup_status`
- `privacy_setup_thread`

### Classes
No classes found.

### Functions
#### `register_nlp_routes(app)`
**Docstring:** No function docstring provided.
