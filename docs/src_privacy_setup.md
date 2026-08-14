# Documentation for `privacy_setup.py`

**Path:** `src/privacy_setup.py`

## Module Docstring
No module-level docstring provided.

## Role
The `privacy_setup.py` module is part of the core business logic or service layer of the application.

## Working
It provides specialized functionality—such as interacting with AI models, processing data, or managing external integrations—that is utilized by the route handlers.

## How it works
It exposes a set of classes or functions (_validate_download_url, is_ollama_installed, is_model_pulled) that encapsulate complex operations. It often imports domain-specific libraries to accomplish these tasks.

## Why it works
This module follows the Single Responsibility Principle. By keeping business logic out of the web layer, the code is highly reusable and easier to unit test independently of HTTP requests.

## Detailed Components

### Imports
- `logging`
- `subprocess`
- `time`
- `urllib.request`
- `pathlib.Path`
- `urllib.parse.urlparse`
- `ai_mode`

### Global Variables
- `logger`
- `_cancelled`

### Classes
No classes found.

### Functions
#### `_validate_download_url(url)`
**Docstring:** No function docstring provided.

#### `is_ollama_installed()`
**Docstring:** Check if Ollama is already installed and running in the path or local folder.

#### `is_model_pulled(model)`
**Docstring:** Check if the required model is already downloaded.

#### `download_ollama(progress_callback)`
**Docstring:** Download Ollama installer with progress updates.
progress_callback(percent, message) — update UI progress bar.

#### `install_ollama(installer_path, progress_callback)`
**Docstring:** Run Ollama installer silently.

#### `run_setup_process(progress_callback)`
**Docstring:** Run the entire local Ollama install and model pull process.

#### `cancel_setup()`
**Docstring:** Cancel the ongoing setup process.
