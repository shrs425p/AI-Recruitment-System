# Documentation for `database.py`

**Path:** `app/database.py`

## Module Docstring
No module-level docstring provided.

## Role
The `database.py` module acts as a foundational component for the AI Recruitment System.

## Working
It provides necessary utilities, classes, or application entry points for the broader system.

## How it works
It defines key structures (like 0 classes and 27 functions) that other modules rely upon for execution.

## Why it works
By providing these standardized utilities, the module reduces code duplication and ensures consistent behavior across the repository.

## Detailed Components

### Imports
- `json`
- `sqlite3`
- `contextlib.contextmanager`

### Global Variables
- `DB_PATH`

### Classes
No classes found.

### Functions
#### `get_connection()`
**Docstring:** Return a new SQLite connection with row_factory for dict-like access.

#### `db_session()`
**Docstring:** Context manager for SQLite database transactions with auto-commit/rollback and automatic cleanup.

#### `init_db()`
**Docstring:** Create tables and indexes if they don't already exist. Safe to call on every app start.

#### `get_setting(key, default)`
**Docstring:** Fetch a single setting from the database by key.

#### `set_setting(key, value, is_encrypted)`
**Docstring:** Save or update a setting in the database.

#### `get_all_settings()`
**Docstring:** Return all database settings as a dictionary of key-value pairs (decrypting sensitive keys).

#### `save_settings_dict(settings_dict)`
**Docstring:** Bulk save dictionary of configuration key-values to the database.

#### `create_run(run_type, metadata)`
**Docstring:** Create a new pipeline run and return its id. run_type: 'nlp', 'ranking', 'scheduling', 'email'.

#### `finish_run(run_id, status, metadata)`
**Docstring:** Mark a pipeline run as completed/failed and optionally update metadata.

#### `get_runs(run_type, limit)`
**Docstring:** Return recent pipeline runs, optionally filtered by type.

#### `upsert_candidate(run_id, name, email, source_file, score, skills)`
**Docstring:** Insert or update a candidate within a run. Returns the candidate id.

#### `get_candidate_by_name(name, run_id)`
**Docstring:** Return candidate row or None. If run_id given, scoped to that run.

#### `get_all_candidates(run_id)`
**Docstring:** Return candidates as a list of dicts. If run_id given, scoped to that run.

#### `save_schedule(run_id, entries, job_title)`
**Docstring:** Bulk-save a list of scheduled entries under a run. Returns list of schedule ids.

#### `get_latest_schedule(run_id)`
**Docstring:** Return the most recent batch of scheduled entries.

#### `get_confirmed_not_emailed(run_id)`
**Docstring:** Return confirmed schedule entries that haven't been emailed yet.

#### `mark_email_sent(schedule_id)`
**Docstring:** Mark a schedule entry as emailed.

#### `log_email(run_id, schedule_id, recipient, subject, status, error)`
**Docstring:** Log an email send attempt.

#### `update_schedule_slot(candidate_name, selected_slot)`
**Docstring:** Update the selected slot for the most recent schedule entry matching this candidate.

#### `create_interview_token(token, candidate_name, source_file, job_title, rank, score)`
**Docstring:** Create a unique interview token for a candidate. Returns the token string.

#### `get_interview_token(token)`
**Docstring:** Look up a token. Returns dict or None.

#### `mark_token_used(token)`
**Docstring:** Mark a token as used after the interview finishes.

#### `get_all_tokens()`
**Docstring:** Return all interview tokens as list of dicts.

#### `delete_all_tokens()`
**Docstring:** Delete all interview tokens (for regeneration).

#### `save_job_template(title, jd_text)`
**Docstring:** Save a new job description template. Returns the template ID.

#### `get_all_job_templates()`
**Docstring:** Return all job templates as a list of dicts ordered by newest first.

#### `delete_job_template(template_id)`
**Docstring:** Delete a job template by ID.
