# Documentation for `interview_bot.py`

**Path:** `src/interview_bot.py`

## Module Docstring
No module-level docstring provided.

## Role
The `interview_bot.py` module is part of the core business logic or service layer of the application.

## Working
It provides specialized functionality—such as interacting with AI models, processing data, or managing external integrations—that is utilized by the route handlers.

## How it works
It exposes a set of classes or functions (call_ai, load_scheduled_candidates, load_candidate_nlp) that encapsulate complex operations. It often imports domain-specific libraries to accomplish these tasks.

## Why it works
This module follows the Single Responsibility Principle. By keeping business logic out of the web layer, the code is highly reusable and easier to unit test independently of HTTP requests.

## Detailed Components

### Imports
- `logging`
- `json`
- `re`
- `time`
- `datetime.datetime`
- `pathlib.Path`
- `src.common.call_ollama`
- `src.common.data_path`
- `src.common.clean_json_response`

### Global Variables
- `logger`
- `SCHEDULING_FOLDER`
- `NLP_FOLDER`
- `OUTPUT_FOLDER`
- `TECHNICAL_QUESTIONS`
- `BEHAVIORAL_QUESTIONS`
- `ANSWER_TIME_LIMIT`

### Classes
No classes found.

### Functions
#### `call_ai(system_msg, user_msg, temperature)`
**Docstring:** Thin wrapper around call_ollama with a fixed token budget of 2048.
Used internally by all question/evaluation functions in this module.

#### `load_scheduled_candidates(scheduling_folder)`
**Docstring:** Load latest schedule and return only CONFIRMED candidates.

#### `load_candidate_nlp(source_file, nlp_folder)`
**Docstring:** Load the NLP JSON for one candidate so the question generator can
create personalised, domain-specific questions based on that candidate's
actual skills, experience, and project history.

Returns {} if the file does not exist (interview can still continue
with generic questions).

#### `generate_questions(candidate_data, job_title)`
**Docstring:** Generate personalized technical + behavioral questions using AI.

#### `evaluate_answer(question, answer, job_title, domain)`
**Docstring:** Evaluate candidate answer using AI and return score + feedback.

#### `proctor_check(question_num, answer, time_taken)`
**Docstring:** Apply basic rule-based proctoring checks on a single answer.

Flags raised:
  VERY_SHORT_ANSWER          — fewer than 10 characters (likely skipped)
  SUSPICIOUSLY_FAST_ANSWER   — >100 chars typed in under 5 seconds (copy-paste?)
  EXCESSIVELY_LONG_ANSWER    — more than 2000 characters (unlikely genuine)
  SKIPPED_QUESTION           — answer is blank, 'skip', or 's'
  TIME_LIMIT_EXCEEDED        — took longer than ANSWER_TIME_LIMIT seconds

For full webcam-based proctoring, see webcam_proctor.py which runs
face detection in a background thread during GUI interviews.

Returns:
  dict with 'flagged' bool and 'flags' list for the interview transcript.

#### `conduct_interview(candidate, questions, job_title, candidate_data)`
**Docstring:** Conduct interview via terminal input/output.
GUI VERSION: Replace input/print with voice/video interface.

#### `save_interview_result(result, output_path)`
**Docstring:** Persist the completed interview in two formats:
  JSON — used by report_generator.py to produce AI-written reports
  TXT  — human-readable transcript that HR can open in any text editor

Both filenames include a timestamp so multiple interviews for the same
candidate (re-takes) don't overwrite each other.

#### `run_interview_bot()`
**Docstring:** No function docstring provided.

#### `generate_interview_question(candidate_name, job_title, topic, q_num, q_type, transcript)`
**Docstring:** Generate a single personalized interview question based on candidate, job title, topic, and transcript history.
