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

import ollama   # Ollama Python client — talks to the local Ollama server
import json     # Standard JSON parsing
import re       # Regular expressions used to strip markdown from LLM output
import time     # Used for sleep() during retry back-off
import sys
from pathlib import Path

# Import project-wide settings from config.py
from config import OLLAMA_MODEL, AI_RETRY_ATTEMPTS, AI_RETRY_BACKOFF

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

# ─────────────────────────────────────────────
# SHARED: Call Ollama
# ─────────────────────────────────────────────

def call_ollama(system_msg: str, user_msg: str,
                temperature: float = 0.0,
                num_predict: int = 4096) -> str:
    """
    Send a chat request to the local Ollama server and return the text response.

    Retry logic:
      Retries up to AI_RETRY_ATTEMPTS times with increasing sleep between each
      attempt (attempt x AI_RETRY_BACKOFF seconds).
    """
    import config  # re-import to pick up runtime changes from Settings page

    for attempt in range(1, AI_RETRY_ATTEMPTS + 1):
        try:
            response = ollama.chat(
                model=config.OLLAMA_MODEL,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user",   "content": user_msg},
                ],
                options={
                    "temperature": temperature,
                    "num_predict": num_predict,
                },
            )
            return response["message"]["content"]

        except Exception as e:
            print(f"  [ERROR] Ollama call failed (attempt {attempt}/{AI_RETRY_ATTEMPTS}): {e}")

            if attempt < AI_RETRY_ATTEMPTS:
                wait = AI_RETRY_BACKOFF * attempt
                time.sleep(wait)
            else:
                print(f"  Ollama is unreachable after {AI_RETRY_ATTEMPTS} attempts.")

    return ""
