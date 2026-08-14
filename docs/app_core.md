# Documentation for `core.py`

**Path:** `app/core.py`

## Module Docstring
No module-level docstring provided.

## Role
The `core.py` module acts as a foundational component for the AI Recruitment System.

## Working
It provides necessary utilities, classes, or application entry points for the broader system.

## How it works
It defines key structures (like 0 classes and 5 functions) that other modules rely upon for execution.

## Why it works
By providing these standardized utilities, the module reduces code duplication and ensures consistent behavior across the repository.

## Detailed Components

### Imports
- `collections`
- `json`
- `logging`
- `queue`
- `threading`
- `src.common.data_dir`
- `src.common.data_path`

### Global Variables
- `logger`
- `log_file_path`
- `logger`
- `RESUMES_FOLDER`
- `OUTPUT_FOLDER`
- `TASK_STATE_FILE`
- `_log_lock`
- `pipeline_tasks`

### Classes
No classes found.

### Functions
#### `ensure_app_directories()`
**Docstring:** Ensure all critical runtime directories exist on disk.

#### `add_log_line(line)`
**Docstring:** Store log line in history and queue for streaming clients.

#### `get_log_history()`
**Docstring:** Return a list of recent log lines.

#### `_load_tasks()`
**Docstring:** No function docstring provided.

#### `_save_tasks()`
**Docstring:** No function docstring provided.
