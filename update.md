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
