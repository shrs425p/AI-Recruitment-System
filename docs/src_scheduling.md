# Documentation for `scheduling.py`

**Path:** `src/scheduling.py`

## Module Docstring
No module-level docstring provided.

## Role
The `scheduling.py` module is part of the core business logic or service layer of the application.

## Working
It provides specialized functionality—such as interacting with AI models, processing data, or managing external integrations—that is utilized by the route handlers.

## How it works
It exposes a set of classes or functions (load_top_candidates, get_hr_availability_terminal, assign_slots_to_candidates) that encapsulate complex operations. It often imports domain-specific libraries to accomplish these tasks.

## Why it works
This module follows the Single Responsibility Principle. By keeping business logic out of the web layer, the code is highly reusable and easier to unit test independently of HTTP requests.

## Detailed Components

### Imports
- `logging`
- `json`
- `re`
- `uuid`
- `datetime.datetime`
- `datetime.timedelta`
- `pathlib.Path`
- `icalendar.Calendar`
- `icalendar.Event`
- `src.common.data_path`

### Global Variables
- `logger`
- `RANKING_FOLDER`
- `OUTPUT_FOLDER`
- `TOP_N_CANDIDATES`
- `SLOTS_TO_OFFER`
- `INTERVIEW_MINUTES`

### Classes
No classes found.

### Functions
#### `load_top_candidates(ranking_folder, top_n)`
**Docstring:** Read the most recent ranking JSON file and return the top N candidates.

The file is identified by globbing for 'ranking_scores*.json' and sorting
reverse-alphabetically so the newest timestamp comes first.

Returns [] if no ranking file exists or the ranking is empty.

#### `get_hr_availability_terminal()`
**Docstring:** Collect HR available slots via terminal.
GUI VERSION: Replace this function with a calendar picker widget.
Returns list of datetime objects.

#### `assign_slots_to_candidates(candidates, hr_slots, slots_per_candidate)`
**Docstring:** Assign multiple interview slot options to each candidate.

Uses a rotation strategy so consecutive candidates receive different primary
slot options rather than all being offered the same first slot.
Example with 3 candidates and slots [A, B, C]:
  Candidate 1: [A, B, C]
  Candidate 2: [B, C, A]
  Candidate 3: [C, A, B]

The slots are then sorted chronologically so the earliest option is always
presented first.

Returns:
  List of dicts — one per candidate, with 'offered_slots', 'selected_slot'
  (starts as None), and 'status' (starts as PENDING).

#### `collect_candidate_selections_terminal(scheduled)`
**Docstring:** Simulate candidate picking a slot via terminal.
GUI VERSION: Replace with candidate-facing web form or email link.

#### `generate_ics(entry, output_path, hr_name, job_title, stamp, hr_email)`
**Docstring:** Create a .ics calendar invite file for one confirmed interview.

.ics is the standard iCalendar format supported by:
  - Google Calendar (import or email attachment)
  - Microsoft Outlook (double-click to add)
  - Apple Calendar (double-click to add)

A unique UUID is generated for each event so importing the same file
twice does not create duplicate calendar entries.

Returns the Path of the created .ics file, or None if the entry was
not CONFIRMED or had no selected slot.

#### `save_schedule_summary(scheduled, output_path, job_title, metadata)`
**Docstring:** Save schedule as JSON and human-readable TXT.

#### `run_scheduling()`
**Docstring:** No function docstring provided.
