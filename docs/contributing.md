# Contributing

This document describes how the codebase is structured, coding conventions used, and how to add new features.

---

## Project Layout Recap

```
AI-Recruitment-System/
├── main.py              ← Entry point: starts Flask servers + pywebview
├── app/
│   ├── __init__.py      ← Flask app factory (create_app)
│   ├── core.py          ← Log queue and SSE streaming
│   ├── database.py      ← SQLite ORM (settings read/write, encryption)
│   ├── rate_limiter.py  ← Per-IP rate limiting middleware
│   ├── utils.py         ← login_required decorator, IP helpers
│   ├── folder_opener.py ← Cross-platform folder open utility
│   ├── routes/          ← One file per feature area
│   ├── templates/       ← Jinja2 HTML templates
│   └── static/          ← CSS, JS, icon files
├── src/
│   ├── common.py        ← Paths, AI dispatcher, JSON utils
│   ├── ai_mode.py       ← Provider list + mode selector
│   ├── security.py      ← AES-Fernet encrypt/decrypt
│   └── ...              ← One file per pipeline stage
├── config/
│   └── __init__.py      ← Dynamic database-backed config
├── tests/               ← pytest test suite
├── scripts/             ← Utility and build scripts
├── build/               ← PyInstaller spec + Inno Setup script
├── docs/                ← This documentation
└── models/              ← Bundled Tesseract + Vosk models
```

---

## Coding Conventions

### Python Style
- PEP 8 style — 4-space indentation, no tabs
- Type hints used in function signatures where practical
- Docstrings on public functions and classes
- `logger = logging.getLogger(__name__)` at the top of each module (not `print()`)

### Imports
- Standard library imports first
- Third-party imports second
- Local imports third (`from src.x import y`, `from app.y import z`)
- Each group separated by a blank line

### AI Calls
- Always go through `call_ollama()` in `src/common.py` — never call provider APIs directly from route handlers
- Use `temperature=0.0` for extraction/scoring tasks (deterministic output)
- Use `temperature=0.2–0.4` for generation tasks (questions, report narratives)
- Always handle the case where the AI returns an empty string or unparseable JSON

### Error Handling
- Routes should return JSON errors for `/api/` paths and HTML errors for browser paths
- Use the registered error handlers (400, 403, 404, 413, 429, 500) — don't write custom error responses
- Log errors with `logger.error()` before returning error responses

### File Writes
- Use atomic writes for important output files: write to `.tmp` first, rename on success
- Always use `encoding="utf-8"` when opening text files
- Use `Path` objects from `pathlib`, not string concatenation for paths

---

## Adding a New Route

1. **Create or edit a route file** in `app/routes/`

```python
# app/routes/myfeature.py
import logging
from flask import jsonify, render_template, request
from app.utils import login_required

logger = logging.getLogger(__name__)

def register_myfeature_routes(app):

    @app.route("/myfeature")
    @login_required
    def myfeature_page():
        return render_template("myfeature.html")

    @app.route("/api/myfeature/do-something", methods=["POST"])
    @login_required
    def myfeature_action():
        data = request.get_json(silent=True) or {}
        result = do_something(data)
        return jsonify({"success": True, "result": result})
```

2. **Register it in `app/__init__.py`**

```python
# In create_app(), after the other imports:
from app.routes.myfeature import register_myfeature_routes
register_myfeature_routes(app)
```

3. **Add a template** to `app/templates/myfeature.html` if it's a page route

4. **Write a test** in `tests/test_myfeature.py`

---

## Adding a New AI Pipeline Stage

If adding a new processing step (e.g. sentiment analysis of interview answers):

1. Create `src/my_stage.py`
2. Use `from src.common import call_ollama, data_path` for AI calls and paths
3. Write input/output clearly (what folder it reads from, what folder it writes to)
4. Add a route in `app/routes/` to trigger it from the UI
5. Add tests that mock the AI call

---

## Adding a New AI Provider

1. Open `src/ai_mode.py` and add a new entry to the `get_providers()` list:

```python
{
    "name":     "myprovider",
    "enabled":  getattr(config, 'MYPROVIDER_ENABLED', False),
    "key":      getattr(config, 'MYPROVIDER_KEY', ''),
    "model":    getattr(config, 'MYPROVIDER_MODEL', 'default-model'),
    "base_url": "https://api.myprovider.com/v1",
    "rpm":      30,
},
```

2. Add the config keys to `config/__init__.py` `DEFAULT_SETTINGS`:

```python
"MYPROVIDER_KEY":     "",
"MYPROVIDER_MODEL":   "default-model",
"MYPROVIDER_ENABLED": False,
```

3. Add the key to `SENSITIVE_KEYS` in `src/security.py`:

```python
SENSITIVE_KEYS = {
    ...
    "MYPROVIDER_KEY",
}
```

4. Add API call handling in `src/provider_router.py` in the `call_provider_sync()` function:

```python
elif name == "myprovider":
    # implement the API call for this provider
    url = f"{base_url}/chat/completions"
    ...
```

5. Add the provider UI to `app/templates/settings.html` and `app/routes/settings.py`

---

## Adding a New Config Setting

1. Add the key and default to `config/__init__.py` `DEFAULT_SETTINGS`:

```python
DEFAULT_SETTINGS = {
    ...
    "MY_NEW_SETTING": "default_value",
}
```

2. If it's sensitive, add it to `SENSITIVE_KEYS` in `src/security.py`

3. Access it anywhere in the app:
```python
import config
value = getattr(config, "MY_NEW_SETTING", "default_value")
```

4. Expose it in the Settings UI if users need to configure it

---

## Running Tests

```bash
pytest                          # run all tests
pytest -v                       # verbose
pytest tests/test_myfeature.py  # specific file
pytest -k "test_login"          # specific test by name
```

---

## Common Mistakes to Avoid

- **Don't call AI providers directly from routes.** Always go through `call_ollama()` in `src/common.py`.
- **Don't use `print()` for logging.** Use `logger.info()`, `logger.error()` etc.
- **Don't hardcode paths.** Use `data_path()` and `resource_path()` from `src/common.py`.
- **Don't write sensitive values unencrypted.** Use `app.database.set_setting(key, value, is_encrypted=True)` for keys in `SENSITIVE_KEYS`.
- **Don't forget `@login_required`** on new HR-only routes.
- **Don't write to the project directory at runtime.** Write to `data_path()` locations in `APP_DATA_DIR` — the project directory may be read-only in installed builds.
