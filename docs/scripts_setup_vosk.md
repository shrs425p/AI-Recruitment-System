# Documentation for `setup_vosk.py`

**Path:** `scripts/setup_vosk.py`

## Module Docstring
setup_vosk.py — Download the Vosk Indian-English speech model (Apache 2.0, offline)

Run once:   python scripts/setup_vosk.py
Optional:   python scripts/setup_vosk.py --large    (downloads 1 GB high-accuracy model)

Models downloaded from https://alphacephei.com/vosk/models (Apache 2.0 licence).

## Role
The `setup_vosk.py` script is a standalone utility designed for operational, maintenance, or setup tasks.

## Working
It is typically executed from the command line independent of the main application server.

## How it works
The script performs a sequential execution of tasks, such as interacting with external APIs, seeding data, or configuring environments, utilizing the defined functions like _progress, download_model.

## Why it works
Isolating these tasks into a separate script ensures they do not bloat the main application startup logic. It allows system administrators and developers to run specific procedures on demand.

## Detailed Components

### Imports
- `sys`
- `urllib.request`
- `zipfile`
- `pathlib.Path`

### Global Variables
- `BASE_DIR`
- `MODELS`

### Classes
No classes found.

### Functions
#### `_progress(count, block_size, total)`
**Docstring:** No function docstring provided.

#### `download_model(which)`
**Docstring:** No function docstring provided.
