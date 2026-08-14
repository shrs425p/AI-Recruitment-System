# Documentation for `ranking_engine.py`

**Path:** `src/ranking_engine.py`

## Module Docstring
No module-level docstring provided.

## Role
The `ranking_engine.py` module is part of the core business logic or service layer of the application.

## Working
It provides specialized functionality—such as interacting with AI models, processing data, or managing external integrations—that is utilized by the route handlers.

## How it works
It exposes a set of classes or functions (build_jd_prompt, build_scoring_prompt, call_ai) that encapsulate complex operations. It often imports domain-specific libraries to accomplish these tasks.

## Why it works
This module follows the Single Responsibility Principle. By keeping business logic out of the web layer, the code is highly reusable and easier to unit test independently of HTTP requests.

## Detailed Components

### Imports
- `logging`
- `hashlib`
- `json`
- `concurrent.futures.ThreadPoolExecutor`
- `concurrent.futures.as_completed`
- `datetime.datetime`
- `pathlib.Path`
- `src.common.call_ollama`
- `src.common.clean_json_response`
- `src.common.data_path`

### Global Variables
- `logger`
- `NLP_FOLDER`
- `OUTPUT_FOLDER`
- `MAX_WORKERS`
- `WEIGHTS`

### Classes
No classes found.

### Functions
#### `build_jd_prompt(jd_text)`
**Docstring:** No function docstring provided.

#### `build_scoring_prompt(candidate, jd)`
**Docstring:** No function docstring provided.

#### `call_ai(prompt)`
**Docstring:** Wrapper that sends a single-string prompt to the AI and returns parsed JSON.
Uses a strict system message to minimise non-JSON output from the model.

#### `load_candidates(nlp_folder)`
**Docstring:** Load all *_nlp.json files from the NLP folder, deduplicating by
name+domain hash to prevent the same resume being scored twice.

Returns a list of unique candidate dicts, or [] if the folder is empty.

#### `score_candidate(candidate, jd)`
**Docstring:** Score a single candidate against the parsed Job Description.

Post-processing applied after AI response:
  - Sub-scores are clamped to their defined max weight.
  - Total is recalculated from clamped sub-scores.
  - hire_recommendation is overridden when the AI verdict disagrees
    with the numeric score by more than one tier — the score wins.
  - Domain and confidence are carried forward from the NLP data.

#### `_score_to_recommendation(total)`
**Docstring:** Map a numeric score to a consistent recommendation label.

#### `save_leaderboard_txt(ranked, jd, output_path)`
**Docstring:** No function docstring provided.

#### `save_scores_json(ranked, jd, output_path)`
**Docstring:** No function docstring provided.

#### `run_ranking()`
**Docstring:** Main entry point when running ranking_engine.py directly from the terminal.

Steps:
  1. Prompt user to paste the Job Description.
  2. Parse JD into structured requirements via AI.
  3. Load all candidate NLP JSON files.
  4. Score candidates IN PARALLEL for speed.
  5. Sort by total score descending.
  6. Save leaderboard.txt and ranking_scores.json.
  7. Print a ranked summary table.
