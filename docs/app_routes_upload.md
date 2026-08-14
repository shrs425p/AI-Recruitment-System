# Documentation for `upload.py`

**Path:** `app/routes/upload.py`

## Module Docstring
No module-level docstring provided.

## Role
The `upload.py` module serves as an API controller or route handler within the Flask web framework.

## Working
It listens to HTTP requests on defined routes, processes incoming data, and delegates business logic to internal services.

## How it works
It defines route functions (like various endpoints) mapped to specific URLs. It validates request payloads, interacts with the database or AI engines, and returns JSON responses.

## Why it works
By separating route definitions from core business logic (in `src/`), the architecture remains modular. It leverages Flask Blueprints to logically group related endpoints.

## Detailed Components

### Imports
- `pathlib.Path`
- `flask.jsonify`
- `flask.render_template`
- `flask.request`
- `flask.send_from_directory`
- `werkzeug.utils.secure_filename`
- `app.core.OUTPUT_FOLDER`
- `app.core.RESUMES_FOLDER`
- `app.utils.login_required`
- `src.pdf_to_txt.process_file`

### Global Variables
- `ALLOWED_UPLOAD_EXTENSIONS`

### Classes
No classes found.

### Functions
#### `_available_filename(folder, filename)`
**Docstring:** Return a collision-free filename without trusting client path input.

#### `register_upload_routes(app)`
**Docstring:** No function docstring provided.
