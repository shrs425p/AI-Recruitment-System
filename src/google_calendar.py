import json
import os
import re
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Optional
from app_paths import data_path, install_path, resource_path

# Google API libraries
try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False
    print("[CALENDAR] Google API libraries not installed.")
    print("  Run: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib")

# ─────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────

SCOPES             = ['https://www.googleapis.com/auth/calendar']  # Full read/write access to calendar
CALENDAR_ID        = 'primary'               # 'primary' = the signed-in user's main calendar
INTERVIEW_DURATION = 60                      # Duration (minutes) of each interview event created
TIMEZONE           = 'Asia/Kolkata'          # IST timezone — change to your local timezone
LOOKAHEAD_DAYS     = 14                      # How many days ahead to scan for free slots
WORK_HOUR_START    = 9                       # Work day starts at 9 AM
WORK_HOUR_END      = 18                      # Work day ends at 6 PM
SLOT_INTERVAL_MINS = 60                      # Check for free slots every 60 minutes within work hours


def _credentials_file() -> Path:
    user_copy = data_path("credentials.json")
    if user_copy.exists():
        return user_copy

    installed_copy = install_path("credentials.json")
    if installed_copy.exists():
        return installed_copy

    return resource_path("credentials.json")


def _token_file() -> Path:
    return data_path("token.json")

# ─────────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────────

def _get_credentials():
    """
    Obtain valid Google OAuth2 credentials.

    Flow:
      1. If token.json exists, load cached credentials.
      2. If cached credentials are expired but have a refresh token, refresh silently.
      3. If no valid credentials exist, start the OAuth2 browser flow:
           - Opens the user's default browser for Google sign-in.
           - Saves the resulting token to token.json for future use.
      4. Raises FileNotFoundError if credentials.json is missing (one-time setup needed).

    After the first successful browser login, subsequent runs reuse token.json
    and never open the browser again (unless the token is revoked).
    """
    if not GOOGLE_AVAILABLE:
        raise RuntimeError("Google API libraries not installed")

    creds = None
    token_file = _token_file()
    credentials_file = _credentials_file()

    # Step 1: Try to load previously saved token
    if token_file.exists():
        creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                # Step 2: Token expired but we have a refresh token — renew silently
                creds.refresh(Request())
            except Exception:
                creds = None  # Refresh failed — need full browser re-auth

        if not creds:
            # Step 3: No valid token — must do full OAuth2 browser flow
            if not credentials_file.exists():
                raise FileNotFoundError(
                    "'credentials.json' not found.\n"
                    "Download it from Google Cloud Console:\n"
                    "  APIs & Services → Credentials → OAuth 2.0 Client IDs → Download JSON\n"
                    "  Save as 'credentials.json' in the app install folder or app data folder."
                )
            # Opens browser for user to grant calendar access
            flow = InstalledAppFlow.from_client_secrets_file(str(credentials_file), SCOPES)
            creds = flow.run_local_server(port=0)  # port=0 = pick any free port

        # Step 4: Save token so the next run doesn't need the browser
        with open(token_file, 'w') as f:
            f.write(creds.to_json())

    return creds


def _build_service():
    """Build and return a Google Calendar API service object used for all API calls."""
    creds = _get_credentials()
    return build('calendar', 'v3', credentials=creds)


# ─────────────────────────────────────────────
# READ FREE SLOTS
# ─────────────────────────────────────────────

def get_free_slots(days_ahead: int = LOOKAHEAD_DAYS,
                   slot_duration_mins: int = INTERVIEW_DURATION) -> dict:
    """
    Scan HR's Google Calendar for free slots over the next `days_ahead` days.
    Returns:
    {
        'success': bool,
        'slots': ['2026-03-01 10:00', '2026-03-12 14:00', ...],
        'error': str or None,
        'calendar_name': str
    }
    """
    if not GOOGLE_AVAILABLE:
        return {'success': False, 'slots': [], 'error': 'Google API not installed', 'calendar_name': ''}

    try:
        service = _build_service()

        # Get calendar info
        calendar = service.calendars().get(calendarId=CALENDAR_ID).execute()
        cal_name = calendar.get('summary', 'Primary Calendar')

        # Time range
        now   = datetime.now(timezone.utc)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end   = start + timedelta(days=days_ahead)

        # Fetch existing events
        events_result = service.events().list(
            calendarId=CALENDAR_ID,
            timeMin=start.isoformat(),
            timeMax=end.isoformat(),
            singleEvents=True,
            orderBy='startTime',
            maxResults=500
        ).execute()

        events = events_result.get('items', [])

        # Build busy intervals
        busy = []
        for ev in events:
            ev_start = ev.get('start', {}).get('dateTime')
            ev_end   = ev.get('end',   {}).get('dateTime')
            if ev_start and ev_end:
                try:
                    s = datetime.fromisoformat(ev_start)
                    e = datetime.fromisoformat(ev_end)
                    busy.append((s, e))
                except Exception:
                    pass

        # Generate candidate slots (working hours only)
        free_slots = []
        current    = start + timedelta(hours=WORK_HOUR_START)  # start scanning from 9 AM today

        while current < end:
            # Skip weekends (weekday() returns 0=Mon ... 6=Sun)
            if current.weekday() < 5:  # Mon–Fri only
                slot_end = current + timedelta(minutes=slot_duration_mins)

                # Only consider slots fully within working hours
                if current.hour >= WORK_HOUR_START and slot_end.hour <= WORK_HOUR_END:
                    # Skip slots that are in the past or too close (< 1 hour from now)
                    if current > now + timedelta(hours=1):
                        # Check if this slot overlaps with any existing calendar event
                        is_free = True
                        for (b_start, b_end) in busy:
                            # Strip timezone info for comparison (both sides normalised to naive datetime)
                            bs = b_start.replace(tzinfo=None)
                            be = b_end.replace(tzinfo=None)
                            cs = current.replace(tzinfo=None)
                            ce = slot_end.replace(tzinfo=None)
                            # Overlap condition: slot starts before busy ends AND slot ends after busy starts
                            if cs < be and ce > bs:
                                is_free = False
                                break

                        if is_free:
                            free_slots.append(current.strftime('%Y-%m-%d %H:%M'))

            # Advance by one slot interval (default 60 min)
            current += timedelta(minutes=SLOT_INTERVAL_MINS)

            # If we've gone past the end of the work day, jump to next morning
            if current.hour >= WORK_HOUR_END:
                current = (current + timedelta(days=1)).replace(
                    hour=WORK_HOUR_START, minute=0, second=0, microsecond=0)

        return {
            'success':       True,
            'slots':         free_slots,
            'error':         None,
            'calendar_name': cal_name,
            'total_found':   len(free_slots)
        }

    except FileNotFoundError as e:
        return {'success': False, 'slots': [], 'error': str(e), 'calendar_name': ''}
    except Exception as e:
        return {'success': False, 'slots': [], 'error': str(e), 'calendar_name': ''}


# ─────────────────────────────────────────────
# CREATE INTERVIEW EVENTS
# ─────────────────────────────────────────────

def create_interview_event(candidate_name: str,
                           source_file: str,
                           rank: int,
                           score: float,
                           slot: str,
                           job_title: str,
                           hr_name: str,
                           hr_email: str = '') -> dict:
    """
    Create a Google Calendar event for an interview.
    Returns: {'success': bool, 'event_id': str, 'event_link': str, 'error': str or None}
    """
    if not GOOGLE_AVAILABLE:
        return {'success': False, 'event_id': '', 'event_link': '', 'error': 'Google API not installed'}

    try:
        service  = _build_service()
        slot_dt  = datetime.strptime(slot, '%Y-%m-%d %H:%M')
        end_dt   = slot_dt + timedelta(minutes=INTERVIEW_DURATION)

        event_body = {
            'summary': f'AI Interview — {candidate_name} for {job_title}',
            'description': (
                f'AI Recruitment System — Automated Interview\n\n'
                f'Candidate   : {candidate_name}\n'
                f'File        : {source_file}\n'
                f'Rank        : #{rank}\n'
                f'Score       : {score}/100\n'
                f'Job Title   : {job_title}\n'
                f'Duration    : {INTERVIEW_DURATION} minutes\n'
                f'Interviewer : {hr_name}\n\n'
                f'This event was created automatically by the AI Recruitment System.'
            ),
            'start': {
                'dateTime': slot_dt.strftime('%Y-%m-%dT%H:%M:00'),
                'timeZone': TIMEZONE,
            },
            'end': {
                'dateTime': end_dt.strftime('%Y-%m-%dT%H:%M:00'),
                'timeZone': TIMEZONE,
            },
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'email',  'minutes': 60},
                    {'method': 'popup',  'minutes': 15},
                ],
            },
            'colorId': '9',  # Blueberry color for interview events
        }

        # Add HR as a calendar attendee if an email was provided
        if hr_email:
            event_body['attendees'] = [{'email': hr_email, 'displayName': hr_name}]

        # Insert the event into the HR's calendar
        # sendUpdates='none' — don't email invitations automatically
        created = service.events().insert(
            calendarId=CALENDAR_ID,
            body=event_body,
            sendUpdates='none'
        ).execute()

        return {
            'success':    True,
            'event_id':   created.get('id', ''),
            'event_link': created.get('htmlLink', ''),
            'error':      None
        }

    except Exception as e:
        return {'success': False, 'event_id': '', 'event_link': '', 'error': str(e)}


def create_bulk_interview_events(scheduled: list, job_title: str, hr_name: str, hr_email: str = '') -> dict:
    """
    Iterate through all CONFIRMED candidates in the schedule and create
    a Google Calendar event for each one.

    Skips candidates with status != CONFIRMED or no selected_slot.

    Returns:
      {
        'created': [{'candidate', 'slot', 'link'}, ...],
        'failed':  [{'candidate', 'error'}, ...],
        'total':   int  — number of CONFIRMED candidates attempted
      }
    """
    results  = {'created': [], 'failed': [], 'total': 0}

    for entry in scheduled:
        if entry.get('status') != 'CONFIRMED' or not entry.get('selected_slot'):
            continue

        result = create_interview_event(
            candidate_name=entry.get('candidate_name', 'Unknown'),
            source_file=entry.get('source_file', ''),
            rank=entry.get('rank', 0),
            score=entry.get('score', 0),
            slot=entry['selected_slot'],
            job_title=job_title,
            hr_name=hr_name,
            hr_email=hr_email
        )

        results['total'] += 1
        if result['success']:
            results['created'].append({
                'candidate': entry.get('candidate_name'),
                'slot':      entry['selected_slot'],
                'link':      result['event_link']
            })
        else:
            results['failed'].append({
                'candidate': entry.get('candidate_name'),
                'error':     result['error']
            })

    return results


# ─────────────────────────────────────────────
# STATUS CHECK
# ─────────────────────────────────────────────

def check_calendar_auth() -> dict:
    """
    Check whether Google Calendar authentication is set up and working.

    Returns a dict that the GUI uses to display the calendar integration status:
      authenticated     — True only if credentials are valid AND an API test call succeeds
      error             — Human-readable error message (None if authenticated)
      has_credentials   — True if credentials.json file exists
      has_token         — True if token.json file exists
      api_not_enabled   — True if the Calendar API needs to be enabled in Google Cloud Console
      enable_url        — Direct URL to enable the API (only present when api_not_enabled=True)
    """
    if not GOOGLE_AVAILABLE:
        return {
            'authenticated': False,
            'error': 'Google API libraries not installed. Run: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib',
            'has_credentials': False,
            'has_token': False
        }

    credentials_file = _credentials_file()
    token_file = _token_file()
    has_creds = credentials_file.exists()
    has_token = token_file.exists()

    if not has_creds:
        return {
            'authenticated': False,
            'error': "'credentials.json' not found. Download from Google Cloud Console.",
            'has_credentials': False,
            'has_token': has_token
        }

    try:
        creds = None
        if has_token:
            creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)
        if creds and creds.valid:
            # Quick test call
            service  = build('calendar', 'v3', credentials=creds)
            try:
                calendar = service.calendars().get(calendarId=CALENDAR_ID).execute()
            except HttpError as http_err:
                err_body = http_err.error_details if hasattr(http_err, 'error_details') else str(http_err)
                err_str  = str(http_err)
                if 'accessNotConfigured' in err_str or 'Calendar API has not been used' in err_str or 'disabled' in err_str:
                    # Extract project ID from error message if present
                    import re as _re
                    proj_match = _re.search(r'project[s]?\s+(\d+)', err_str)
                    proj_id    = proj_match.group(1) if proj_match else ''
                    enable_url = (
                        f'https://console.developers.google.com/apis/api/calendar-json.googleapis.com/overview?project={proj_id}'
                        if proj_id else
                        'https://console.cloud.google.com/apis/library/calendar-json.googleapis.com'
                    )
                    return {
                        'authenticated': False,
                        'error': (
                            f'Google Calendar API is not enabled for this project. '
                            f'Go to Google Cloud Console → APIs & Services → Enable "Google Calendar API". '
                            f'Direct link: {enable_url}'
                        ),
                        'enable_url': enable_url,
                        'has_credentials': True,
                        'has_token': True,
                        'api_not_enabled': True
                    }
                raise  # re-raise other HttpErrors
            return {
                'authenticated': True,
                'error': None,
                'calendar_name': calendar.get('summary', ''),
                'has_credentials': True,
                'has_token': True
            }
        else:
            return {
                'authenticated': False,
                'error': 'Token expired or invalid. Re-authentication needed.',
                'has_credentials': True,
                'has_token': has_token
            }
    except HttpError as e:
        err_str = str(e)
        if 'accessNotConfigured' in err_str or 'Calendar API has not been used' in err_str or 'disabled' in err_str:
            import re as _re
            proj_match = _re.search(r'project[s]?\s+(\d+)', err_str)
            proj_id    = proj_match.group(1) if proj_match else ''
            enable_url = (
                f'https://console.developers.google.com/apis/api/calendar-json.googleapis.com/overview?project={proj_id}'
                if proj_id else
                'https://console.cloud.google.com/apis/library/calendar-json.googleapis.com'
            )
            return {
                'authenticated': False,
                'error': (
                    f'Google Calendar API is not enabled for this project. '
                    f'Go to Google Cloud Console → APIs & Services → Enable "Google Calendar API". '
                    f'Direct link: {enable_url}'
                ),
                'enable_url': enable_url,
                'has_credentials': has_creds,
                'has_token': has_token,
                'api_not_enabled': True
            }
        return {
            'authenticated': False,
            'error': str(e),
            'has_credentials': has_creds,
            'has_token': has_token
        }
    except Exception as e:
        return {
            'authenticated': False,
            'error': str(e),
            'has_credentials': has_creds,
            'has_token': has_token
        }


def trigger_auth_flow() -> dict:
    """
    Launch the OAuth2 browser authentication flow for Google Calendar.

    Opens the user's default browser for Google sign-in.
    On success, saves the token to token.json so future calls are automatic.

    Returns:
      {'success': True, 'error': None} on success
      {'success': False, 'error': str} on failure
    """
    if not GOOGLE_AVAILABLE:
        return {'success': False, 'error': 'Google API libraries not installed'}

    credentials_file = _credentials_file()
    token_file = _token_file()

    if not credentials_file.exists():
        return {
            'success': False,
            'error': "'credentials.json' not found. Download OAuth2 credentials from Google Cloud Console first."
        }

    try:
        flow  = InstalledAppFlow.from_client_secrets_file(str(credentials_file), SCOPES)
        creds = flow.run_local_server(port=0)
        with open(token_file, 'w') as f:
            f.write(creds.to_json())
        return {'success': True, 'error': None}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def create_event_from_dict(entry: dict, job_title: str) -> dict:
    """Wrapper to create calendar event from a schedule entry dict using config HR settings."""
    import config
    hr_name = getattr(config, 'HR_DISPLAY_NAME', 'HR Admin')
    hr_email = getattr(config, 'HR_EMAIL', '')
    
    return create_interview_event(
        candidate_name=entry.get('candidate_name', 'Unknown'),
        source_file=entry.get('source_file', ''),
        rank=entry.get('rank', 0),
        score=entry.get('score', 0.0),
        slot=entry.get('selected_slot', ''),
        job_title=job_title,
        hr_name=hr_name,
        hr_email=hr_email
    )