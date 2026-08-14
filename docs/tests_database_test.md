# Documentation for `database_test.py`

**Path:** `tests/database_test.py`

## Module Docstring
database_test.py - Hard tests for the AI Recruitment System database layer.

Tests cover:
  1.  Schema integrity    — all tables and indexes exist with correct columns
  2.  Pipeline runs       — create_run, finish_run, get_runs, status transitions
  3.  Candidate CRUD      — insert, upsert (update), get by name, get all, score ordering
  4.  Cascade safety      — FK enforcement: no orphan candidates, schedules, tokens
  5.  Schedule CRUD       — save_schedule, get_latest_schedule, update_schedule_slot
  6.  Email log           — log_email, mark_email_sent, get_confirmed_not_emailed
  7.  Interview tokens    — create, get, mark_used, delete_all, duplicate rejection
  8.  Job templates       — save, get_all, delete
  9.  Concurrency         — 20 threads writing simultaneously with no data corruption
 10.  Rollback on error   — db_session rolls back on exception, no dirty data
 11.  SQL injection       — parameterized queries block injection strings
 12.  Large payloads      — 1000 candidates bulk insert + query performance

## Role
The `database_test.py` module is a test suite ensuring the reliability and correctness of specific application features.

## Working
It uses the `pytest` testing framework to execute various test cases against the application codebase.

## How it works
It works by defining test functions (e.g., _test_data_path, check, expect_exception...) that simulate inputs and assert expected outcomes.

## Why it works
This automated testing approach guarantees that regressions are caught early. Using fixtures and mocking, it tests components in isolation without affecting the real database or external services.

## Detailed Components

### Imports
- `json`
- `os`
- `sqlite3`
- `sys`
- `tempfile`
- `threading`
- `time`
- `pathlib.Path`
- `src.common`
- `importlib`
- `app.database`
- `secrets`
- `shutil`

### Global Variables
- `_tmp`
- `_TEST_DB`
- `_original_data_path`
- `PASS`
- `FAIL`
- `results`
- `run_id`
- `runs`
- `runs`
- `runs`
- `run_id2`
- `filtered`
- `run_id`
- `cid`
- `cand`
- `cid2`
- `cand2`
- `all_cands`
- `cand_latest`
- `sched_run`
- `entries`
- `ids`
- `sched`
- `updated`
- `alice`
- `confirmed`
- `confirmed2`
- `failed_log`
- `tok`
- `fetched`
- `fetched2`
- `all_toks`
- `tid`
- `templates`
- `templates2`
- `conc_run`
- `errors`
- `threads`
- `start`
- `elapsed`
- `all_conc`
- `rollback_run`
- `after`
- `inj_run`
- `injection_strings`
- `survivors`
- `bulk_run`
- `start`
- `bulk_insert_time`
- `start`
- `all_bulk`
- `bulk_query_time`
- `total`
- `passed`
- `failed`

### Classes
No classes found.

### Functions
#### `_test_data_path(relative)`
**Docstring:** No function docstring provided.

#### `check(name, condition, details)`
**Docstring:** No function docstring provided.

#### `expect_exception(name, exc_type, fn)`
**Docstring:** No function docstring provided.

#### `_insert_orphan_candidate()`
**Docstring:** No function docstring provided.

#### `_insert_orphan_schedule()`
**Docstring:** No function docstring provided.

#### `_insert_duplicate_token()`
**Docstring:** No function docstring provided.

#### `_worker(i)`
**Docstring:** No function docstring provided.
