# Documentation for `reports.py`

**Path:** `app/routes/reports.py`

## Module Docstring
No module-level docstring provided.

## Role
The `reports.py` module serves as an API controller or route handler within the Flask web framework.

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
- `re`
- `time`
- `flask.Response`
- `flask.jsonify`
- `flask.render_template`
- `app.core.OUTPUT_FOLDER`
- `app.core._save_tasks`
- `app.core.pipeline_tasks`
- `app.utils.login_required`
- `src.report_generator.calculate_combined_score`
- `src.report_generator.generate_ai_report`
- `src.report_generator.load_interview_transcripts`
- `src.report_generator.save_final_summary`
- `src.report_generator.save_report_json`
- `src.report_generator.save_report_txt`

### Global Variables
- `logger`

### Classes
No classes found.

### Functions
#### `register_reports_routes(app)`
**Docstring:** No function docstring provided.
