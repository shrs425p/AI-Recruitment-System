# Documentation for `main.py`

**Path:** `main.py`

## Module Docstring
No module-level docstring provided.

## Role
The `main.py` module acts as a foundational component for the AI Recruitment System.

## Working
It provides necessary utilities, classes, or application entry points for the broader system.

## How it works
It defines key structures (like 1 classes and 10 functions) that other modules rely upon for execution.

## Why it works
By providing these standardized utilities, the module reduces code duplication and ensures consistent behavior across the repository.

## Detailed Components

### Imports
- `logging`
- `os`
- `socket`
- `sys`
- `threading`
- `time`
- `traceback`
- `pathlib.Path`
- `webview`
- `app.create_app`
- `app.core.add_log_line`
- `app.core.log_queue`
- `src.common.APP_DATA_DIR`

### Global Variables
- `ROOT_DIR`
- `APP_NAME`
- `CRASH_LOG`
- `DESKTOP_PORT`
- `CANDIDATE_PORT`
- `app`
- `logger`
- `formatter`
- `qh`
- `sh`

### Classes
#### `QueueHandler`
**Docstring:** No class docstring provided.

**Methods:**
- `__init__(self, log_queue)`
  - **Docstring:** No method docstring provided.
- `emit(self, record)`
  - **Docstring:** No method docstring provided.


### Functions
#### `_write_crash_log(exc_type, exc_value, exc_tb)`
**Docstring:** No function docstring provided.

#### `_handle_unhandled_exception(exc_type, exc_value, exc_tb)`
**Docstring:** No function docstring provided.

#### `_save_config(cfg)`
**Docstring:** Persist all config attributes directly to the SQLite database.
No plain text config.py file or .env file is written to disk.

#### `_ensure_ssl_cert()`
**Docstring:** No function docstring provided.

#### `_env_port(name, default)`
**Docstring:** No function docstring provided.

#### `_pick_port(host, preferred_port)`
**Docstring:** No function docstring provided.

#### `_debug_mode()`
**Docstring:** Keep Flask's debugger off unless a developer explicitly enables it.

#### `run_flask_https()`
**Docstring:** No function docstring provided.

#### `run_flask_http_local()`
**Docstring:** No function docstring provided.

#### `main()`
**Docstring:** No function docstring provided.
