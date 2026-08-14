# Documentation for `report_generator.py`

**Path:** `src/report_generator.py`

## Module Docstring
No module-level docstring provided.

## Role
The `report_generator.py` module is part of the core business logic or service layer of the application.

## Working
It provides specialized functionality—such as interacting with AI models, processing data, or managing external integrations—that is utilized by the route handlers.

## How it works
It exposes a set of classes or functions (call_ai, load_interview_transcripts, generate_ai_report) that encapsulate complex operations. It often imports domain-specific libraries to accomplish these tasks.

## Why it works
This module follows the Single Responsibility Principle. By keeping business logic out of the web layer, the code is highly reusable and easier to unit test independently of HTTP requests.

## Detailed Components

### Imports
- `logging`
- `json`
- `re`
- `datetime.datetime`
- `pathlib.Path`
- `src.common.call_ollama`
- `src.common.data_path`
- `src.common.clean_json_response`

### Global Variables
- `logger`
- `INTERVIEWS_FOLDER`
- `OUTPUT_FOLDER`

### Classes
No classes found.

### Functions
#### `call_ai(system_msg, user_msg)`
**Docstring:** Wrapper that calls the Ollama model with temperature=0.0 (deterministic)
and a 4096-token budget to allow detailed reports.

#### `load_interview_transcripts(interviews_folder)`
**Docstring:** Scan the interviews/ folder and load all interview_*.json files.

Each file is a complete interview transcript saved by interview_bot.py.
A '_source_file' key (the filename) is added to each dict so the report
can reference back to the original interview file.

Returns [] if no transcripts are found (reports stage cannot proceed).

#### `generate_ai_report(transcript)`
**Docstring:** Send the interview transcript to the AI model and return a structured
HR assessment report.

The prompt includes:
  - Candidate name, job title, domain
  - All scores (ranking, interview, technical, behavioural)
  - Proctoring status and flag count
  - Full Q&A with per-question feedback

The AI returns a JSON with:
  overall_summary, technical_assessment, behavioral_assessment,
  key_strengths, key_gaps, proctoring_remarks, risk_level,
  combined_score, hire_recommendation, hire_justification,
  suggested_next_steps

Returns {} if the AI call fails (caller should skip that candidate).

#### `calculate_combined_score(transcript)`
**Docstring:** Compute the final combined score used to rank candidates after interviews.

Formula:
  combined = (ranking_score × 0.40) + (interview_percentage × 0.60)

Rationale:
  - Resume ranking (40%) rewards candidates with strong backgrounds.
  - Interview performance (60%) is weighted higher because it reflects
    how the candidate actually thinks, communicates, and solves problems.

#### `save_report_txt(transcript, ai_report, combined_score, output_path)`
**Docstring:** Save comprehensive HR report as human-readable TXT.

#### `save_report_json(transcript, ai_report, combined_score, output_path)`
**Docstring:** Save full report as JSON for downstream use or GUI display.

#### `save_final_summary(all_reports, output_path)`
**Docstring:** Save a final summary of all candidates ranked by combined score.

#### `run_report_generator()`
**Docstring:** No function docstring provided.
