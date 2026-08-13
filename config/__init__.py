"""
config package — Dynamic Database-Backed Configuration Module.
All settings are stored in SQLite (ars.db -> app_settings table).
Sensitive credentials (API keys, passwords) are stored encrypted at rest.
No static config.py file or .env file is used.
"""

import sys
from typing import Any

# Default configuration values
DEFAULT_SETTINGS = {
    "LOGIN_ENABLED": False,
    "HR_USERNAME": "hr",
    "HR_PASSWORD": "",
    "HR_PASSWORD_HASH": "",

    "FLASK_SECRET_KEY": "",
    "HR_DISPLAY_NAME": "HR Admin",
    "HR_EMAIL": "",
    "HR_COMPANY": "",
    "THEME": "light",
    "COLOR_PALETTE": "rose",
    "OLLAMA_MODEL": "llama3.2:3b",
    "OLLAMA_BASE_URL": "http://localhost:11434",
    "CLOUD_ENABLED": False,
    "CLOUD_MODEL": "claude-3-5-haiku-latest",
    "SMTP_HOST": "smtp.gmail.com",
    "SMTP_PORT": 587,
    "SMTP_EMAIL": "",
    "SMTP_PASSWORD": "",
    "EMAIL_TEMPLATE_SUBJECT": "",
    "EMAIL_TEMPLATE_BODY": "",
    "AI_RETRY_ATTEMPTS": 3,
    "AI_RETRY_BACKOFF": 2,
    "APP_MODE": "cloud",
    "ANTHROPIC_KEY": "",
    "GEMINI_KEY": "",
    "GROQ_KEY": "",
    "OPENAI_KEY": "",
    "NVIDIA_KEY": "",
    "OPENROUTER_KEY": "",
    "GITHUB_KEY": "",
    "OLLAMA_CLOUD_KEY": "",
    "PRIVACY_MODEL": "llama3.2:3b",
    "ANTHROPIC_MODEL": "claude-3-5-haiku-latest",
    "GEMINI_MODEL": "gemini-1.5-flash",
    "GROQ_MODEL": "llama3-8b-8192",
    "OPENAI_MODEL": "gpt-4o-mini",
    "NVIDIA_MODEL": "meta/llama-3.1-8b-instruct",
    "OPENROUTER_MODEL": "meta-llama/llama-3.1-8b-instruct:free",
    "GITHUB_MODEL": "gpt-4o-mini",
    "OLLAMA_CLOUD_MODEL": "llama3.2:3b",
    "ANTHROPIC_ENABLED": False,
    "GEMINI_ENABLED": False,
    "GROQ_ENABLED": False,
    "OPENAI_ENABLED": False,
    "NVIDIA_ENABLED": True,
    "OPENROUTER_ENABLED": False,
    "GITHUB_ENABLED": False,
    "OLLAMA_CLOUD_ENABLED": False,
}

_cache = {}
_initialized = False


def _init_db_defaults():
    global _initialized, _cache
    if _initialized:
        return
    try:
        from app.database import get_all_settings, init_db, save_settings_dict
        init_db()
        db_settings = get_all_settings()

        # Seed defaults for any missing keys
        missing = {}
        for k, default_val in DEFAULT_SETTINGS.items():
            if k not in db_settings:
                missing[k] = default_val
        if missing:
            save_settings_dict(missing)
            db_settings.update(missing)

        _cache = db_settings
        _initialized = True
    except Exception:
        # Fallback if DB not accessible during early setup
        _cache = dict(DEFAULT_SETTINGS)


def _cast_value(key: str, raw_val: Any) -> Any:
    default_val = DEFAULT_SETTINGS.get(key)
    if default_val is None:
        return raw_val
    if isinstance(default_val, bool):
        if isinstance(raw_val, str):
            return raw_val.lower() in ("true", "1", "yes", "on")
        return bool(raw_val)
    if isinstance(default_val, int):
        try:
            return int(raw_val)
        except (ValueError, TypeError):
            return default_val
    if isinstance(default_val, float):
        try:
            return float(raw_val)
        except (ValueError, TypeError):
            return default_val
    return str(raw_val) if raw_val is not None else ""


def get_setting(name: str) -> Any:
    _init_db_defaults()
    if name in _cache:
        return _cast_value(name, _cache[name])
    try:
        from app.database import get_setting as db_get_setting
        val = db_get_setting(name, DEFAULT_SETTINGS.get(name))
        _cache[name] = val
        return _cast_value(name, val)
    except Exception:
        return DEFAULT_SETTINGS.get(name)


def set_setting(name: str, value: Any):
    _init_db_defaults()
    from src.security import SENSITIVE_KEYS
    is_enc = name in SENSITIVE_KEYS
    typed_val = _cast_value(name, value)
    _cache[name] = typed_val
    try:
        from app.database import set_setting as db_set_setting
        db_set_setting(name, str(value), is_encrypted=is_enc)
    except Exception:
        pass


class _ConfigProxy:
    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        return get_setting(name)

    def __setattr__(self, name: str, value: Any):
        if name.startswith("_"):
            super().__setattr__(name, value)
        else:
            set_setting(name, value)


sys.modules[__name__] = _ConfigProxy()
