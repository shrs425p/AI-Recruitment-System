# Documentation for `common.py`

**Path:** `src/common.py`

## Module Docstring
src/common.py — Common Utilities & Paths

## Role
The `common.py` module is part of the core business logic or service layer of the application.

## Working
It provides specialized functionality—such as interacting with AI models, processing data, or managing external integrations—that is utilized by the route handlers.

## How it works
It exposes a set of classes or functions (_get_app_data_dir, resource_path, install_path) that encapsulate complex operations. It often imports domain-specific libraries to accomplish these tasks.

## Why it works
This module follows the Single Responsibility Principle. By keeping business logic out of the web layer, the code is highly reusable and easier to unit test independently of HTTP requests.

## Detailed Components

### Imports
- `os`
- `sys`
- `pathlib.Path`
- `asyncio`
- `json`
- `re`
- `sys`
- `time`
- `pathlib.Path`
- `src.ai_mode.get_app_mode`

### Global Variables
- `APP_NAME`
- `APP_DATA_DIR`
- `_ollama_client`
- `clean_json`

### Classes
No classes found.

### Functions
#### `_get_app_data_dir()`
**Docstring:** No function docstring provided.

#### `resource_path(relative)`
**Docstring:** No function docstring provided.

#### `install_path(relative)`
**Docstring:** No function docstring provided.

#### `data_path(relative)`
**Docstring:** Return a path to a *file* inside the app data directory, creating parent dirs.

#### `data_dir(relative)`
**Docstring:** Return a path to a *directory* inside the app data directory, creating it if needed.

#### `_ollama()`
**Docstring:** No function docstring provided.

#### `_repair_json_string(s)`
**Docstring:** No function docstring provided.

#### `clean_json_response(text)`
**Docstring:** No function docstring provided.

#### `call_ollama_async(system_msg, user_msg, temperature, num_predict)`
**Docstring:** No function docstring provided.

#### `call_cloud_async(system_msg, user_msg, max_tokens)`
**Docstring:** No function docstring provided.

#### `call_ai_async(system_msg, user_msg, temperature, num_predict, local_timeout)`
**Docstring:** No function docstring provided.

#### `call_ollama(system_msg, user_msg, temperature, num_predict)`
**Docstring:** No function docstring provided.
