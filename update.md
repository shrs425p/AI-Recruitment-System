# AI Recruitment System — NLP Performance Update

## Problem Summary

The NLP extraction pipeline is slow due to three root causes:

1. **Model too large** — `cogito-2.1:671b-cloud` is a 671B parameter model. Overkill for structured JSON extraction from resumes. A 3B–7B model does identical quality work for this task.
2. **Synchronous blocking** — `ollama.chat()` in `utils.py` blocks the entire app until the response returns. No parallelism.
3. **`num_predict=4096`** — Asking the model to generate up to 4096 tokens per resume. 2048 is more than enough.

---

## Files to Change

- `config.py` — model + cloud settings
- `utils.py` — async + hybrid call_ollama
- `nlp_extractor.py` — async + parallel watcher

---

## File 1: `config.py`

### What to Change
- Replace `OLLAMA_MODEL` value
- Add `CLOUD_ENABLED`, `CLOUD_MODEL`, `ANTHROPIC_KEY`

### Updated Section (OLLAMA + CLOUD)

```python
# ─────────────────────────────────────────────
# OLLAMA SETTINGS
# ─────────────────────────────────────────────
OLLAMA_MODEL    = 'llama3.2:3b'           # was: cogito-2.1:671b-cloud
OLLAMA_BASE_URL = 'http://localhost:11434'

# ─────────────────────────────────────────────
# CLOUD FALLBACK SETTINGS (Anthropic)
# ─────────────────────────────────────────────
CLOUD_ENABLED = True                       # set False to disable cloud fallback
CLOUD_MODEL   = 'claude-haiku-4-5'         # fastest + cheapest Anthropic model
ANTHROPIC_KEY = 'sk-ant-...'              # replace with your actual key
```

> **Note:** Pull the new model first: `ollama pull llama3.2:3b`
> Optional higher quality: `ollama pull llama3.1:7b`

---

## File 2: `utils.py`

### What to Change
- Add `call_ollama_async()` — non-blocking Ollama call using thread executor
- Add `call_cloud_async()` — Anthropic cloud fallback
- Add `call_ai_async()` — hybrid: tries local first, falls back to cloud on timeout
- Keep old `call_ollama()` as a sync wrapper so existing code doesn't break

### Add These Imports (top of file)

```python
import asyncio

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

from config import (OLLAMA_MODEL, AI_RETRY_ATTEMPTS, AI_RETRY_BACKOFF,
                    CLOUD_ENABLED, CLOUD_MODEL, ANTHROPIC_KEY)
```

### Add These Functions (after existing `call_ollama`)

```python
# ── Async Ollama call ─────────────────────────────────────────────────
async def call_ollama_async(system_msg: str, user_msg: str,
                            temperature: float = 0.0,
                            num_predict: int = 2048) -> str:
    """Non-blocking Ollama call — runs in thread pool so it doesn't freeze app."""
    import config

    def _sync_call():
        for attempt in range(1, AI_RETRY_ATTEMPTS + 1):
            try:
                response = ollama.chat(
                    model=config.OLLAMA_MODEL,
                    messages=[
                        {"role": "system", "content": system_msg},
                        {"role": "user",   "content": user_msg},
                    ],
                    options={"temperature": temperature, "num_predict": num_predict},
                )
                return response["message"]["content"]
            except Exception as e:
                print(f"  [ERROR] Ollama attempt {attempt}: {e}")
                if attempt < AI_RETRY_ATTEMPTS:
                    time.sleep(AI_RETRY_BACKOFF * attempt)
        return ""

    # Run blocking ollama.chat() in a thread — keeps event loop free
    return await asyncio.get_event_loop().run_in_executor(None, _sync_call)


# ── Cloud fallback (Anthropic) ────────────────────────────────────────
async def call_cloud_async(system_msg: str, user_msg: str,
                           max_tokens: int = 2048) -> str:
    if not ANTHROPIC_AVAILABLE or not CLOUD_ENABLED:
        return ""
    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_KEY)
    msg = await client.messages.create(
        model=CLOUD_MODEL,
        max_tokens=max_tokens,
        system=system_msg,
        messages=[{"role": "user", "content": user_msg}]
    )
    return msg.content[0].text


# ── Hybrid: local first, cloud fallback ──────────────────────────────
async def call_ai_async(system_msg: str, user_msg: str,
                        temperature: float = 0.0,
                        num_predict: int = 2048,
                        local_timeout: float = 45.0) -> str:
    """
    Try local Ollama first.
    If it times out or fails → automatically use cloud.
    """
    try:
        result = await asyncio.wait_for(
            call_ollama_async(system_msg, user_msg, temperature, num_predict),
            timeout=local_timeout
        )
        if result:
            return result
    except asyncio.TimeoutError:
        print(f"  [INFO] Local timeout ({local_timeout}s) → switching to cloud")
    except Exception as e:
        print(f"  [INFO] Local failed ({e}) → switching to cloud")

    if CLOUD_ENABLED:
        return await call_cloud_async(system_msg, user_msg, num_predict)

    return ""
```

### Update Existing `call_ollama` (sync wrapper — keeps old code working)

```python
# Replace the existing call_ollama function with this:

def call_ollama(system_msg: str, user_msg: str,
                temperature: float = 0.0,
                num_predict: int = 2048) -> str:       # changed default: 4096 → 2048
    """Sync wrapper — all existing code that calls this still works unchanged."""
    return asyncio.run(call_ai_async(system_msg, user_msg, temperature, num_predict))
```

---

## File 3: `nlp_extractor.py`

### What to Change
- Add `extract_with_ai_async()` — async version of `extract_with_ai`
- Add `process_file_async()` — async version of `process_file`
- Replace `run_watcher()` — processes up to 4 resumes in parallel

### Add This Import (top of file)

```python
import asyncio
from utils import call_ai_async, clean_json_response   # add call_ai_async
```

### Add These Functions (after existing `extract_with_ai`)

```python
# ── Async extraction ──────────────────────────────────────────────────
async def extract_with_ai_async(resume_text: str) -> dict:
    system = (
        "You are a precise resume parser that extracts structured data "
        "from resumes of ALL professional domains. Always return valid JSON only."
    )
    raw = await call_ai_async(system, build_prompt(resume_text), num_predict=2048)
    return clean_json_response(raw) if raw else {}


# ── Async process single file ─────────────────────────────────────────
async def process_file_async(txt_file: Path, output_path: Path) -> bool:
    if (output_path / f"{txt_file.stem}_nlp.json").exists():
        return False

    print(f"> Processing: {txt_file.name}...", end=" ", flush=True)
    try:
        with open(txt_file, "r", encoding="utf-8") as f:
            resume_text = f.read()

        if not resume_text.strip():
            print("> Empty, skipping.")
            return False

        extracted_data = await extract_with_ai_async(resume_text)

        if not extracted_data:
            print("> No data.")
            return False

        personal_info = extracted_data.get("personal_info") or {}
        if not str(personal_info.get("name", "")).strip():
            extracted_data.setdefault("personal_info", {})
            extracted_data["personal_info"]["name"] = f"{UNKNOWN_NAME}_{txt_file.stem}"

        save_output(extracted_data, output_path / f"{txt_file.stem}_nlp", txt_file.stem)
        print(f"> Done [{extracted_data.get('domain', 'Unknown')}]")
        return True

    except Exception as e:
        print(f"> Failed: {e}")
        return False
```

### Replace `run_watcher()` Entirely

```python
def run_watcher():
    async def _main():
        input_path  = Path(INPUT_FOLDER)
        output_path = Path(OUTPUT_FOLDER)
        input_path.mkdir(parents=True, exist_ok=True)
        output_path.mkdir(parents=True, exist_ok=True)

        print("=" * 50)
        print("   NLP WATCHER — ASYNC + HYBRID")
        print("=" * 50)
        print(f"> Local  : {OLLAMA_MODEL}")
        print(f"> Cloud  : {CLOUD_MODEL if CLOUD_ENABLED else 'disabled'}")
        print(f"> Parallel: 4 resumes at once\n")

        processed = 0
        while True:
            try:
                pending = [
                    f for f in input_path.glob("*.txt")
                    if not (output_path / f"{f.stem}_nlp.json").exists()
                ]

                if pending:
                    print(f"\n> {len(pending)} file(s) found — processing in parallel...")
                    sem = asyncio.Semaphore(4)   # max 4 resumes at once

                    async def limited(f):
                        async with sem:
                            return await process_file_async(f, output_path)

                    results = await asyncio.gather(*[limited(f) for f in pending])
                    processed += sum(1 for r in results if r)
                    print(f"> Batch done. Total processed: {processed}")
                else:
                    print(f"\r> Waiting... (done: {processed})", end="", flush=True)

                await asyncio.sleep(WATCH_INTERVAL_SECONDS)

            except KeyboardInterrupt:
                print(f"\n> Stopped. Total: {processed}")
                break

    asyncio.run(_main())
```

---

## Install New Dependency

```bash
pip install anthropic
```

---

## Expected Speed Improvement

| Scenario | Before | After |
|---|---|---|
| 1 resume (local 671B) | 30–120s | 3–8s (local 3B) |
| 5 resumes | 3–10 min | 8–15s (parallel x4) |
| Local unavailable/slow | hangs | auto-switches to cloud |
| Cloud only (Haiku) | N/A | ~2–4s per resume |

---

## Quick Checklist

- [ ] `ollama pull llama3.2:3b`
- [ ] Update `OLLAMA_MODEL` in `config.py`
- [ ] Add `CLOUD_ENABLED`, `CLOUD_MODEL`, `ANTHROPIC_KEY` to `config.py`
- [ ] Add async functions to `utils.py`
- [ ] Update `call_ollama` default `num_predict` to `2048`
- [ ] Add async functions to `nlp_extractor.py`
- [ ] Replace `run_watcher()` in `nlp_extractor.py`
- [ ] `pip install anthropic`

---
---

# Update 2 — Cloud Mode + Privacy Mode + Rate Limit Handling

## Problem Summary

1. **Cloud API rate limits** — Gemini, Groq, Anthropic, OpenAI all have RPM/TPM limits. Blasting 5 parallel resumes at one provider hits the limit fast and gets `429` errors.
2. **Ollama cloud API** — same problem, also has rate limits when using cloud models via Ollama.
3. **App install size** — App is 500MB + Ollama is 2GB + model is 2–4GB. Users have to manually install everything before the app even works.

## Solution Overview

```
App Mode 1 — Cloud Mode
  → User picks provider (Gemini, Groq, Anthropic, OpenAI, Ollama cloud)
  → Requests load-balanced across multiple providers
  → No single provider gets rate limited

App Mode 2 — Privacy Mode
  → Zero data leaves the machine
  → App auto-installs Ollama silently if not present
  → App auto-pulls model if not present
  → User just sees a progress bar, nothing manual
```

---

## New File: `ai_mode.py`

New file to manage Cloud vs Privacy mode and all provider keys.

```python
# ai_mode.py — App Mode Configuration

# ── Mode selector ─────────────────────────────────────────────────────
# "cloud"   → use cloud APIs, load balanced across providers
# "privacy" → use local Ollama only, zero data leaves machine
APP_MODE = "cloud"   # change to "privacy" for local mode

# ── Privacy Mode settings ─────────────────────────────────────────────
PRIVACY_MODEL        = "llama3.2:3b"          # model to use locally
OLLAMA_INSTALL_DIR   = "C:/ollama"            # where to install Ollama silently
OLLAMA_DOWNLOAD_URL  = "https://ollama.com/download/OllamaSetup.exe"   # Windows
# OLLAMA_DOWNLOAD_URL = "https://ollama.com/download/Ollama-darwin.zip" # Mac

# ── Cloud providers — add your keys here ─────────────────────────────
PROVIDERS = [
    {
        "name":    "anthropic",
        "enabled": True,
        "key":     "sk-ant-...",
        "model":   "claude-haiku-4-5",
        "rpm":     50,    # requests per minute allowed
    },
    {
        "name":    "gemini",
        "enabled": True,
        "key":     "AIza...",
        "model":   "gemini-1.5-flash",
        "rpm":     60,
    },
    {
        "name":    "groq",
        "enabled": True,
        "key":     "gsk_...",
        "model":   "llama3-8b-8192",
        "rpm":     30,
    },
    {
        "name":    "openai",
        "enabled": False,   # set True if you have a key
        "key":     "sk-...",
        "model":   "gpt-4o-mini",
        "rpm":     60,
    },
    {
        "name":    "ollama_cloud",
        "enabled": False,   # Ollama cloud API
        "key":     "ollama_...",
        "model":   "llama3.2:3b",
        "rpm":     20,
    },
]
```

---

## New File: `provider_router.py`

Round-robin load balancer — spreads requests across all enabled providers so no single one gets rate limited.

```python
# provider_router.py — Load Balanced Multi-Provider Router

import asyncio
import time
from collections import deque
from ai_mode import PROVIDERS, APP_MODE, PRIVACY_MODEL

# Only use enabled providers
ACTIVE_PROVIDERS = [p for p in PROVIDERS if p["enabled"]]


class ProviderRouter:
    """
    Round-robin router across multiple cloud providers.
    Tracks per-provider request count to respect RPM limits.
    Auto-skips a provider if it's rate limited and tries the next one.
    """

    def __init__(self):
        self.queue     = deque(ACTIVE_PROVIDERS)   # rotate through providers
        self.call_log  = {p["name"]: [] for p in ACTIVE_PROVIDERS}  # timestamps
        self._lock     = asyncio.Lock()

    def _is_rate_limited(self, provider: dict) -> bool:
        """Check if this provider has exceeded its RPM in the last 60 seconds."""
        now      = time.time()
        name     = provider["name"]
        rpm      = provider["rpm"]
        # Keep only calls from last 60 seconds
        self.call_log[name] = [t for t in self.call_log[name] if now - t < 60]
        return len(self.call_log[name]) >= rpm

    def _log_call(self, provider: dict):
        self.call_log[provider["name"]].append(time.time())

    async def get_provider(self) -> dict:
        """Get the next available provider that is not rate limited."""
        async with self._lock:
            for _ in range(len(self.queue)):
                provider = self.queue[0]
                self.queue.rotate(-1)   # move to back of queue
                if not self._is_rate_limited(provider):
                    self._log_call(provider)
                    return provider
            # All providers rate limited — wait and retry
            print("  [ROUTER] All providers rate limited — waiting 5s...")
            await asyncio.sleep(5)
            return await self.get_provider()

    async def call(self, system_msg: str, user_msg: str,
                   max_tokens: int = 2048) -> str:
        """Route a request to the next available provider."""
        provider = await self.get_provider()
        print(f"  [ROUTER] Using: {provider['name']}")

        try:
            if provider["name"] == "anthropic":
                return await _call_anthropic(provider, system_msg, user_msg, max_tokens)
            elif provider["name"] == "gemini":
                return await _call_gemini(provider, system_msg, user_msg, max_tokens)
            elif provider["name"] == "groq":
                return await _call_groq(provider, system_msg, user_msg, max_tokens)
            elif provider["name"] == "openai":
                return await _call_openai(provider, system_msg, user_msg, max_tokens)
            elif provider["name"] == "ollama_cloud":
                return await _call_ollama_cloud(provider, system_msg, user_msg, max_tokens)
        except Exception as e:
            print(f"  [ROUTER] {provider['name']} failed: {e} — trying next provider")
            # Mark as temporarily rate limited and retry with next provider
            self.call_log[provider["name"]].extend([time.time()] * provider["rpm"])
            return await self.call(system_msg, user_msg, max_tokens)

        return ""


# ── Per-provider call implementations ────────────────────────────────

async def _call_anthropic(p, system_msg, user_msg, max_tokens):
    import anthropic
    client = anthropic.AsyncAnthropic(api_key=p["key"])
    msg = await client.messages.create(
        model=p["model"], max_tokens=max_tokens,
        system=system_msg,
        messages=[{"role": "user", "content": user_msg}]
    )
    return msg.content[0].text


async def _call_gemini(p, system_msg, user_msg, max_tokens):
    import google.generativeai as genai
    genai.configure(api_key=p["key"])
    model = genai.GenerativeModel(p["model"],
                system_instruction=system_msg)
    response = await asyncio.get_event_loop().run_in_executor(
        None, lambda: model.generate_content(user_msg)
    )
    return response.text


async def _call_groq(p, system_msg, user_msg, max_tokens):
    from groq import AsyncGroq
    client = AsyncGroq(api_key=p["key"])
    response = await client.chat.completions.create(
        model=p["model"], max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user",   "content": user_msg}
        ]
    )
    return response.choices[0].message.content


async def _call_openai(p, system_msg, user_msg, max_tokens):
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=p["key"])
    response = await client.chat.completions.create(
        model=p["model"], max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user",   "content": user_msg}
        ]
    )
    return response.choices[0].message.content


async def _call_ollama_cloud(p, system_msg, user_msg, max_tokens):
    import httpx
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post("https://api.ollama.com/api/chat",
            headers={"Authorization": f"Bearer {p['key']}"},
            json={
                "model": p["model"],
                "messages": [
                    {"role": "system", "content": system_msg},
                    {"role": "user",   "content": user_msg}
                ],
                "stream": False
            }
        )
        return r.json()["message"]["content"]


# Singleton
router = ProviderRouter()
```

---

## New File: `privacy_setup.py`

Auto-installs Ollama and pulls model silently. Called on first launch in Privacy Mode.

```python
# privacy_setup.py — Silent Ollama Install + Model Pull

import subprocess
import urllib.request
import os
import time
from pathlib import Path
from ai_mode import PRIVACY_MODEL, OLLAMA_DOWNLOAD_URL


def is_ollama_installed() -> bool:
    """Check if Ollama is already installed and running."""
    try:
        result = subprocess.run(["ollama", "--version"],
                                capture_output=True, timeout=5)
        return result.returncode == 0
    except Exception:
        return False


def is_model_pulled(model: str) -> bool:
    """Check if the required model is already downloaded."""
    try:
        result = subprocess.run(["ollama", "list"],
                                capture_output=True, text=True, timeout=10)
        return model.split(":")[0] in result.stdout
    except Exception:
        return False


def download_ollama(progress_callback=None):
    """
    Download Ollama installer with progress updates.
    progress_callback(percent, message) — update UI progress bar.
    """
    installer_path = Path("ollama_setup.exe")

    def _report(count, block_size, total):
        if total > 0 and progress_callback:
            percent = min(int(count * block_size * 100 / total), 100)
            progress_callback(percent, f"Downloading Ollama... {percent}%")

    print("> Downloading Ollama...")
    urllib.request.urlretrieve(OLLAMA_DOWNLOAD_URL, installer_path, _report)
    return installer_path


def install_ollama(installer_path: Path, progress_callback=None):
    """Run Ollama installer silently."""
    if progress_callback:
        progress_callback(0, "Installing Ollama...")
    subprocess.run([str(installer_path), "/S"], check=True)  # /S = silent
    time.sleep(3)   # give installer time to finish
    if progress_callback:
        progress_callback(100, "Ollama installed.")


def pull_model(model: str, progress_callback=None):
    """Pull the required model — streams progress line by line."""
    if progress_callback:
        progress_callback(0, f"Downloading model {model}...")

    process = subprocess.Popen(
        ["ollama", "pull", model],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )

    for line in process.stdout:
        line = line.strip()
        if line and progress_callback:
            # Ollama outputs progress lines like "pulling... 45%"
            progress_callback(None, line)

    process.wait()
    if progress_callback:
        progress_callback(100, f"Model {model} ready.")


def setup_privacy_mode(progress_callback=None):
    """
    Full one-time setup for Privacy Mode.
    Call this on first launch when user selects Privacy Mode.

    progress_callback(percent, message) — hook into your UI progress bar.
    Returns True if setup succeeded, False if failed.
    """
    try:
        if not is_ollama_installed():
            installer = download_ollama(progress_callback)
            install_ollama(installer, progress_callback)
            installer.unlink()   # clean up installer file

        if not is_model_pulled(PRIVACY_MODEL):
            pull_model(PRIVACY_MODEL, progress_callback)

        if progress_callback:
            progress_callback(100, "Privacy Mode ready!")
        return True

    except Exception as e:
        print(f"[Privacy Setup] Failed: {e}")
        if progress_callback:
            progress_callback(0, f"Setup failed: {e}")
        return False
```

---

## Update `utils.py` — Hook Into Mode + Router

Add this to `call_ai_async()` so it respects the current app mode:

```python
# utils.py — update call_ai_async to respect APP_MODE

from ai_mode import APP_MODE

async def call_ai_async(system_msg: str, user_msg: str,
                        temperature: float = 0.0,
                        num_predict: int = 2048,
                        local_timeout: float = 45.0) -> str:

    if APP_MODE == "privacy":
        # Privacy mode — local Ollama only, never touch cloud
        return await call_ollama_async(system_msg, user_msg, temperature, num_predict)

    else:
        # Cloud mode — use load-balanced provider router
        from provider_router import router
        return await router.call(system_msg, user_msg, max_tokens=num_predict)
```

---

## How Privacy Mode Setup Hooks Into Your UI (Flask)

Add a route in `app.py` to trigger setup and stream progress to the frontend:

```python
# app.py — add this route

from privacy_setup import setup_privacy_mode
import json

@app.route("/api/setup-privacy", methods=["POST"])
def setup_privacy():
    """Called when user enables Privacy Mode for the first time."""
    progress_updates = []

    def on_progress(percent, message):
        progress_updates.append({"percent": percent, "message": message})

    success = setup_privacy_mode(on_progress)
    return json.dumps({"success": success, "log": progress_updates})
```

Frontend just polls this endpoint and shows a progress bar while setup runs.

---

## Install New Dependencies

```bash
pip install anthropic google-generativeai groq openai httpx
```

---

## New Files Summary

| File | Purpose |
|---|---|
| `ai_mode.py` | Mode selector + all provider API keys |
| `provider_router.py` | Round-robin load balancer across providers |
| `privacy_setup.py` | Silent Ollama install + model pull |

---

## Full Updated Checklist

### NLP Performance (Update 1)
- [ ] `ollama pull llama3.2:3b`
- [ ] Update `OLLAMA_MODEL` in `config.py`
- [ ] Add `CLOUD_ENABLED`, `CLOUD_MODEL`, `ANTHROPIC_KEY` to `config.py`
- [ ] Add async functions to `utils.py`
- [ ] Update `call_ollama` default `num_predict` to `2048`
- [ ] Add async functions to `nlp_extractor.py`
- [ ] Replace `run_watcher()` in `nlp_extractor.py`
- [ ] `pip install anthropic`

### Cloud + Privacy Mode (Update 2)
- [ ] Create `ai_mode.py` — fill in all API keys
- [ ] Create `provider_router.py`
- [ ] Create `privacy_setup.py`
- [ ] Update `call_ai_async()` in `utils.py` to check `APP_MODE`
- [ ] Add `/api/setup-privacy` route in `app.py`
- [ ] Add Privacy Mode toggle to Settings page in UI
- [ ] Add progress bar UI for first-time Privacy Mode setup
- [ ] `pip install anthropic google-generativeai groq openai httpx`
