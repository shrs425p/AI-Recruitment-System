# Documentation for `nlp_extractor.py`

**Path:** `src/nlp_extractor.py`

## Module Docstring
No module-level docstring provided.

## Role
The `nlp_extractor.py` module is part of the core business logic or service layer of the application.

## Working
It provides specialized functionality—such as interacting with AI models, processing data, or managing external integrations—that is utilized by the route handlers.

## How it works
It exposes a set of classes or functions (build_prompt, extract_with_ai, save_output) that encapsulate complex operations. It often imports domain-specific libraries to accomplish these tasks.

## Why it works
This module follows the Single Responsibility Principle. By keeping business logic out of the web layer, the code is highly reusable and easier to unit test independently of HTTP requests.

## Detailed Components

### Imports
- `logging`
- `json`
- `time`
- `pathlib.Path`
- `src.common.call_ollama`
- `src.common.clean_json_response`
- `src.common.data_path`

### Global Variables
- `logger`
- `INPUT_FOLDER`
- `OUTPUT_FOLDER`
- `UNKNOWN_NAME`
- `WATCH_INTERVAL_SECONDS`

### Classes
No classes found.

### Functions
#### `build_prompt(resume_text)`
**Docstring:** No function docstring provided.

#### `extract_with_ai(resume_text)`
**Docstring:** Send the resume text to the AI model and parse the returned JSON.

temperature=0.0 — deterministic output so extraction is consistent
num_predict=4096 — allow enough tokens for detailed resume JSON

Returns an empty dict {} if the AI call fails or JSON is unparseable.
Raises RuntimeError with provider error details if the AI call itself fails.

#### `save_output(data, output_file, stem)`
**Docstring:** Persist the AI-extracted candidate data in two formats:
  1. JSON  — machine-readable, used by ranking_engine.py
  2. TXT   — human-readable summary for recruiter review

Uses a temp-file strategy for atomic writes:
  - Writes to .tmp_json / .tmp_txt first.
  - Only renames to the final names after BOTH writes succeed.
  - If anything fails, temp files are deleted so no partial output exists.

#### `process_file(txt_file, output_path)`
**Docstring:** Run one .txt resume through the full NLP extraction pipeline.

Returns:
  (True, None)         — file was newly processed successfully.
  (False, None)        — skipped (already done).
  (False, error_str)   — processing failed; error_str explains why.

#### `run_watcher()`
**Docstring:** Poll the output/txt/ folder continuously and run AI extraction on
any new .txt files found.  Runs forever until Ctrl+C is pressed.

#### `process_file_async(txt_file, output_path)`
**Docstring:** Asynchronous wrapper for process_file to run without blocking the event loop.
