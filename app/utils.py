"""
utils.py — Shared Utilities for AI Recruitment System
=======================================================
Every pipeline module (nlp_extractor, ranking_engine, etc.) imports
from here so that JSON cleaning and AI calling logic is defined once.

Key exports:
  clean_json_response(text)  — parse JSON from an LLM output string
  clean_json                 — alias for the function above
  call_ollama(...)           — call the local Ollama model with auto-retry
"""

import asyncio
import ipaddress
import json  # Standard JSON parsing
import re  # Regular expressions used to strip markdown from LLM output
import sys
import time  # Used for sleep() during retry back-off
from functools import wraps
from pathlib import Path

from flask import jsonify, redirect, request, session, url_for

from ai_mode import get_app_mode

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

# All project configurations are imported dynamically inside functions
# to prevent startup-time config caching, enabling instant hot-reloads.

_ollama_client = None

def _ollama():
    """Import the Ollama client lazily so startup does not fail in packaged builds."""
    global _ollama_client
    if _ollama_client is None:
        import ollama
        _ollama_client = ollama
    return _ollama_client

# ─────────────────────────────────────────────
# SHARED: App root path (works in both dev and frozen .exe)
# ─────────────────────────────────────────────
# When frozen by PyInstaller, __file__ points inside _internal/ (read-only).
# Mutable data (output/, resumes/, ars.db, Tesseract-OCR/) lives next to the exe.
if getattr(sys, "frozen", False):
    APP_ROOT = Path(sys.executable).parent
else:
    APP_ROOT = Path(__file__).parent

# ─────────────────────────────────────────────
# SHARED: Clean JSON from LLM response
# ─────────────────────────────────────────────

def clean_json_response(text: str) -> dict:
    """
    Strip markdown code-fences from an LLM response and return parsed JSON.

    LLMs often wrap JSON in ```json ... ``` blocks.  This function:
      1. Removes ```json and ``` markers.
      2. Tries json.loads() on the cleaned string.
      3. If that fails, finds the first '{' and last '}' and retries — this
         handles cases where the model added extra text before/after the JSON.
      4. Returns {} on any unrecoverable parse error (never crashes the pipeline).
    """
    # Step 1: Remove markdown code fences that some models add
    text = re.sub(r"```json", "", text)  # remove opening ```json
    text = re.sub(r"```", "", text)      # remove closing ```
    text = text.strip()

    try:
        # Step 2: Direct parse — works when output is clean JSON
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            # Step 3: Fallback — slice out just the JSON object if extra text surrounds it
            start = text.index("{")      # first opening brace
            end   = text.rindex("}") + 1 # last closing brace (inclusive)
            return json.loads(text[start:end])
        except Exception as e:
            # Step 4: Give up gracefully so the pipeline continues for other candidates
            print(f"  [WARNING] JSON parse failed: {e}")
            return {}

# Convenience alias — some modules import it as `clean_json`
clean_json = clean_json_response

async def call_ollama_async(system_msg: str, user_msg: str,
                            temperature: float = 0.0,
                            num_predict: int = 2048) -> str:
    """Non-blocking Ollama call — runs in thread pool so it doesn't freeze app."""
    import config
    attempts = getattr(config, "AI_RETRY_ATTEMPTS", 3)
    backoff  = getattr(config, "AI_RETRY_BACKOFF", 2)
    model    = getattr(config, "OLLAMA_MODEL", "llama3.2:3b")

    def _sync_call():
        for attempt in range(1, attempts + 1):
            try:
                response = _ollama().chat(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_msg},
                        {"role": "user",   "content": user_msg},
                    ],
                    options={"temperature": temperature, "num_predict": num_predict},
                )
                return response["message"]["content"]
            except Exception as e:
                print(f"  [ERROR] Ollama attempt {attempt}: {e}")
                if attempt < attempts:
                    time.sleep(backoff * attempt)
        return ""

    # Run blocking ollama.chat() in a thread — keeps event loop free
    return await asyncio.get_event_loop().run_in_executor(None, _sync_call)


async def call_cloud_async(system_msg: str, user_msg: str,
                           max_tokens: int = 2048) -> str:
    import config
    cloud_enabled = getattr(config, "CLOUD_ENABLED", False)
    cloud_model   = getattr(config, "CLOUD_MODEL", "claude-3-5-haiku-latest")
    anthropic_key = getattr(config, "ANTHROPIC_KEY", "")

    if not ANTHROPIC_AVAILABLE or not cloud_enabled:
        return ""
    client = anthropic.AsyncAnthropic(api_key=anthropic_key)
    msg = await client.messages.create(
        model=cloud_model,
        max_tokens=max_tokens,
        system=system_msg,
        messages=[{"role": "user", "content": user_msg}]
    )
    return msg.content[0].text


async def call_ai_async(system_msg: str, user_msg: str,
                        temperature: float = 0.0,
                        num_predict: int = 2048,
                        local_timeout: float = 45.0) -> str:
    """
    Core AI routing engine.
    If APP_MODE is privacy, execute local Ollama call.
    Otherwise, route through the load-balanced Multi-Provider Router.
    """
    mode = get_app_mode()

    if mode == "privacy":
        try:
            return await asyncio.wait_for(
                call_ollama_async(system_msg, user_msg, temperature, num_predict),
                timeout=local_timeout
            )
        except asyncio.TimeoutError:
            print(f"  [WARNING] Local Ollama call timed out ({local_timeout}s).")
            import config
            cloud_enabled = getattr(config, "CLOUD_ENABLED", False)
            anthropic_key = getattr(config, "ANTHROPIC_KEY", "")
            if cloud_enabled and ANTHROPIC_AVAILABLE and anthropic_key and anthropic_key != 'sk-ant-...':
                print("  [INFO] Attempting Cloud Fallback (Anthropic) because local Ollama timed out...")
                try:
                    return await call_cloud_async(system_msg, user_msg, num_predict)
                except Exception as ce:
                    print(f"  [ERROR] Cloud fallback failed: {ce}")
            return ""
        except Exception as e:
            print(f"  [ERROR] Local Ollama call failed: {e}")
            import config
            cloud_enabled = getattr(config, "CLOUD_ENABLED", False)
            anthropic_key = getattr(config, "ANTHROPIC_KEY", "")
            if cloud_enabled and ANTHROPIC_AVAILABLE and anthropic_key and anthropic_key != 'sk-ant-...':
                print("  [INFO] Attempting Cloud Fallback (Anthropic) due to local failure...")
                try:
                    return await call_cloud_async(system_msg, user_msg, num_predict)
                except Exception as ce:
                    print(f"  [ERROR] Cloud fallback failed: {ce}")
            return ""

    else:
        # Cloud mode — use load-balanced provider router
        from provider_router import router
        return await router.call(system_msg, user_msg, max_tokens=num_predict)


def call_ollama(system_msg: str, user_msg: str,
                temperature: float = 0.0,
                num_predict: int = 2048) -> str:
    """Sync wrapper — all existing code that calls this still works unchanged."""
    # asyncio.run() creates, runs, and closes a fresh event loop each call.
    # This is correct for non-async callers and works in any thread.
    try:
        return asyncio.run(call_ai_async(system_msg, user_msg, temperature, num_predict))
    except RuntimeError as e:
        err_str = str(e)

        # asyncio.run() cannot be called inside an already-running event loop
        # (e.g. called from inside an async context). Fall back to direct sync.
        if "cannot be called when another event loop is running" in err_str:
            import config as _cfg
            attempts = getattr(_cfg, "AI_RETRY_ATTEMPTS", 3)
            backoff  = getattr(_cfg, "AI_RETRY_BACKOFF", 2)
            model    = getattr(_cfg, "OLLAMA_MODEL", "llama3.2:3b")
            for attempt in range(1, attempts + 1):
                try:
                    response = _ollama().chat(
                        model=model,
                        messages=[
                            {"role": "system", "content": system_msg},
                            {"role": "user",   "content": user_msg},
                        ],
                        options={"temperature": temperature, "num_predict": num_predict},
                    )
                    return response["message"]["content"]
                except Exception as se:
                    print(f"  [ERROR] Ollama attempt {attempt}: {se}")
                    if attempt < attempts:
                        time.sleep(backoff * attempt)
            return ""

        # Any other RuntimeError (e.g. "No cloud providers enabled") is a
        # configuration problem — do NOT silently retry with Ollama.
        print(f"  [ERROR] AI call failed: {err_str}")
        return ""
    except Exception as e:
        print(f"  [ERROR] call_ollama unexpected error: {e}")
        return ""
PUBLIC_PATH_PREFIXES = (
    "/candidate-interview/",
    "/api/candidate/",
    "/api/health",
    "/static/",
)


def is_local_request() -> bool:
    """Return True only for loopback requests from the desktop app."""
    remote_addr = request.remote_addr or ""
    try:
        return ipaddress.ip_address(remote_addr).is_loopback
    except ValueError:
        return remote_addr in {"localhost", "127.0.0.1", "::1"}


def is_public_candidate_path(path: str) -> bool:
    return path in {"/login", "/logout"} or path.startswith(PUBLIC_PATH_PREFIXES)


def _auth_failure_response():
    if request.path.startswith("/api/"):
        return jsonify({"error": "HR authentication required"}), 401
    return redirect(url_for("login"))


def hr_access_allowed() -> bool:
    import config
    if session.get("logged_in"):
        return True
    if not getattr(config, "LOGIN_ENABLED", False) and is_local_request():
        return True
    return False


def protect_hr_routes(app):
    """Block HR screens/APIs from candidate-facing network access."""
    @app.before_request
    def _protect_hr_routes():
        if is_public_candidate_path(request.path):
            return None
        if hr_access_allowed():
            return None
        return _auth_failure_response()


def login_required(f):
    """Decorator to protect routes requiring authentication."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not hr_access_allowed():
            return _auth_failure_response()
        return f(*args, **kwargs)
    return decorated_function

