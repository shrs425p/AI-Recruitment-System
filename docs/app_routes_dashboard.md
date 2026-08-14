# Documentation for `dashboard.py`

**Path:** `app/routes/dashboard.py`

## Module Docstring
No module-level docstring provided.

## Role
The `dashboard.py` module serves as an API controller or route handler within the Flask web framework.

## Working
It listens to HTTP requests on defined routes, processes incoming data, and delegates business logic to internal services.

## How it works
It defines route functions (like various endpoints) mapped to specific URLs. It validates request payloads, interacts with the database or AI engines, and returns JSON responses.

## Why it works
By separating route definitions from core business logic (in `src/`), the architecture remains modular. It leverages Flask Blueprints to logically group related endpoints.

## Detailed Components

### Imports
- `json`
- `logging`
- `shutil`
- `threading`
- `time`
- `uuid`
- `concurrent.futures.ThreadPoolExecutor`
- `concurrent.futures.as_completed`
- `datetime.datetime`
- `datetime.timedelta`
- `flask.jsonify`
- `flask.redirect`
- `flask.render_template`
- `flask.url_for`
- `app.core.OUTPUT_FOLDER`
- `app.core.RESUMES_FOLDER`
- `app.core._save_tasks`
- `app.core.pipeline_tasks`
- `app.database.create_interview_token`
- `app.database.create_run`
- `app.database.finish_run`
- `app.database.upsert_candidate`
- `app.database.save_schedule`
- `app.folder_opener.open_folder`
- `app.utils.login_required`
- `src.nlp_extractor.process_file_async`
- `src.pdf_to_txt.process_file`
- `src.ranking_engine.load_candidates`
- `src.ranking_engine.save_leaderboard_txt`
- `src.ranking_engine.save_scores_json`
- `src.ranking_engine.score_candidate`
- `src.report_generator.calculate_combined_score`
- `src.report_generator.generate_ai_report`
- `src.report_generator.load_interview_transcripts`
- `src.report_generator.save_final_summary`
- `src.report_generator.save_report_json`
- `src.report_generator.save_report_txt`
- `src.scheduling.SLOTS_TO_OFFER`
- `src.scheduling.generate_ics`
- `src.scheduling.load_top_candidates`
- `src.scheduling.save_schedule_summary`
- `src.shortlist_report.save_shortlist_report`

### Global Variables
- `logger`
- `AUTO_PIPELINE_STEPS`
- `_pipeline_lock`

### Classes
No classes found.

### Functions
#### `_set_auto_pipeline_status(status, message)`
**Docstring:** No function docstring provided.

#### `_run_txt_stage(results)`
**Docstring:** No function docstring provided.

#### `_run_nlp_stage(results)`
**Docstring:** No function docstring provided.

#### `_run_ranking_stage(results)`
**Docstring:** No function docstring provided.

#### `_run_scheduling_stage(results)`
**Docstring:** No function docstring provided.

#### `_run_reports_stage(results)`
**Docstring:** No function docstring provided.

#### `_run_auto_pipeline_job()`
**Docstring:** No function docstring provided.

#### `register_dashboard_routes(app)`
**Docstring:** No function docstring provided.
