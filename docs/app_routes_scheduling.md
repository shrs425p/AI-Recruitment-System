# Documentation for `scheduling.py`

**Path:** `app/routes/scheduling.py`

## Module Docstring
No module-level docstring provided.

## Role
The `scheduling.py` module serves as an API controller or route handler within the Flask web framework.

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
- `time`
- `datetime.datetime`
- `flask.jsonify`
- `flask.render_template`
- `flask.request`
- `app.core.OUTPUT_FOLDER`
- `app.core._save_tasks`
- `app.core.pipeline_tasks`
- `app.database.create_run`
- `app.database.finish_run`
- `app.database.save_schedule`
- `app.utils.login_required`
- `src.google_calendar.check_calendar_auth`
- `src.google_calendar.create_event_from_dict`
- `src.google_calendar.get_free_slots`
- `src.google_calendar.trigger_auth_flow`
- `src.scheduling.SLOTS_TO_OFFER`
- `src.scheduling.assign_slots_to_candidates`
- `src.scheduling.generate_ics`
- `src.scheduling.load_top_candidates`
- `src.scheduling.save_schedule_summary`

### Global Variables
- `logger`

### Classes
No classes found.

### Functions
#### `_parse_schedule_slots(raw_slots)`
**Docstring:** No function docstring provided.

#### `register_scheduling_routes(app)`
**Docstring:** No function docstring provided.
