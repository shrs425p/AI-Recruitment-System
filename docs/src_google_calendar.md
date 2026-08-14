# Documentation for `google_calendar.py`

**Path:** `src/google_calendar.py`

## Module Docstring
No module-level docstring provided.

## Role
The `google_calendar.py` module is part of the core business logic or service layer of the application.

## Working
It provides specialized functionality—such as interacting with AI models, processing data, or managing external integrations—that is utilized by the route handlers.

## How it works
It exposes a set of classes or functions (_credentials_file, _token_file, _get_credentials) that encapsulate complex operations. It often imports domain-specific libraries to accomplish these tasks.

## Why it works
This module follows the Single Responsibility Principle. By keeping business logic out of the web layer, the code is highly reusable and easier to unit test independently of HTTP requests.

## Detailed Components

### Imports
- `logging`
- `datetime.datetime`
- `datetime.timedelta`
- `datetime.timezone`
- `pathlib.Path`
- `typing.Any`
- `src.common.data_path`
- `src.common.install_path`
- `src.common.resource_path`

### Global Variables
- `logger`
- `SCOPES`
- `CALENDAR_ID`
- `INTERVIEW_DURATION`
- `TIMEZONE`
- `LOOKAHEAD_DAYS`
- `WORK_HOUR_START`
- `WORK_HOUR_END`
- `SLOT_INTERVAL_MINS`

### Classes
No classes found.

### Functions
#### `_credentials_file()`
**Docstring:** No function docstring provided.

#### `_token_file()`
**Docstring:** No function docstring provided.

#### `_get_credentials()`
**Docstring:** Obtain valid Google OAuth2 credentials.

Flow:
  1. If token.json exists, load cached credentials.
  2. If cached credentials are expired but have a refresh token, refresh silently.
  3. If no valid credentials exist, start the OAuth2 browser flow:
       - Opens the user's default browser for Google sign-in.
       - Saves the resulting token to token.json for future use.
  4. Raises FileNotFoundError if credentials.json is missing (one-time setup needed).

After the first successful browser login, subsequent runs reuse token.json
and never open the browser again (unless the token is revoked).

#### `_build_service()`
**Docstring:** Build and return a Google Calendar API service object used for all API calls.

#### `get_free_slots(days_ahead, slot_duration_mins)`
**Docstring:** Scan HR's Google Calendar for free slots over the next `days_ahead` days.
Returns:
{
    'success': bool,
    'slots': ['2026-03-01 10:00', '2026-03-12 14:00', ...],
    'error': str or None,
    'calendar_name': str
}

#### `create_interview_event(candidate_name, source_file, rank, score, slot, job_title, hr_name, hr_email)`
**Docstring:** Create a Google Calendar event for an interview.
Returns: {'success': bool, 'event_id': str, 'event_link': str, 'error': str or None}

#### `create_bulk_interview_events(scheduled, job_title, hr_name, hr_email)`
**Docstring:** Iterate through all CONFIRMED candidates in the schedule and create
a Google Calendar event for each one.

Skips candidates with status != CONFIRMED or no selected_slot.

Returns:
  {
    'created': [{'candidate', 'slot', 'link'}, ...],
    'failed':  [{'candidate', 'error'}, ...],
    'total':   int  — number of CONFIRMED candidates attempted
  }

#### `check_calendar_auth()`
**Docstring:** Check whether Google Calendar authentication is set up and working.

Returns a dict that the GUI uses to display the calendar integration status:
  authenticated     — True only if credentials are valid AND an API test call succeeds
  error             — Human-readable error message (None if authenticated)
  has_credentials   — True if credentials.json file exists
  has_token         — True if token.json file exists
  api_not_enabled   — True if the Calendar API needs to be enabled in Google Cloud Console
  enable_url        — Direct URL to enable the API (only present when api_not_enabled=True)

#### `trigger_auth_flow()`
**Docstring:** Launch the OAuth2 browser authentication flow for Google Calendar.

Opens the user's default browser for Google sign-in.
On success, saves the token to token.json so future calls are automatic.

Returns:
  {'success': True, 'error': None} on success
  {'success': False, 'error': str} on failure

#### `create_event_from_dict(entry, job_title)`
**Docstring:** Wrapper to create calendar event from a schedule entry dict using config HR settings.
