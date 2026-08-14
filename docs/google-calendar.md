# Google Calendar Integration

This document explains how to set up and use the Google Calendar integration for scheduling interview invites directly into Google Calendar.

---

## What It Does

When Google Calendar is configured, the scheduling stage can:
- Create calendar events in HR's Google Calendar for each interview slot
- Send Google Calendar invites to candidates via email (through Google's API)
- Scan HR's calendar for free/busy slots to suggest availability automatically

This is optional — the system works fine without it. The basic scheduling (`.ics` files + email) does not require Google Calendar.

---

## Prerequisites

### 1. Install Google API Libraries

```bash
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

Verify they are installed:
```bash
python -c "from googleapiclient.discovery import build; print('OK')"
```

### 2. Create a Google Cloud Project

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Click **Select a project** → **New Project**
3. Give it a name (e.g. `ARS-Calendar`) and click **Create**

### 3. Enable the Google Calendar API

1. In your project, go to **APIs & Services** → **Library**
2. Search for **Google Calendar API**
3. Click it → click **Enable**

### 4. Create OAuth 2.0 Credentials

1. Go to **APIs & Services** → **Credentials**
2. Click **Create Credentials** → **OAuth client ID**
3. If prompted, configure the **OAuth consent screen** first:
   - User type: **External**
   - App name: anything (e.g. `AI Recruitment System`)
   - Support email: your email
   - Developer contact: your email
   - Save and continue through the remaining screens
4. Back on Create OAuth client ID:
   - Application type: **Desktop app**
   - Name: anything (e.g. `ARS Desktop`)
   - Click **Create**
5. Click **Download JSON** on the created credential
6. Rename the downloaded file to `credentials.json`

### 5. Place `credentials.json`

Place the file in one of these locations (checked in order):
```
%LOCALAPPDATA%\AI Recruitment System\data\credentials.json   ← preferred
<project root>\credentials.json
```

---

## First-Time Authentication

On the first time the calendar integration is used, the app will open your default browser to complete the Google OAuth flow:

1. A browser window opens asking you to sign in to your Google account
2. Sign in with the Google account whose calendar you want to use
3. Google shows a consent screen — click **Allow** (or **Advanced → Go to ARS** if using External app type)
4. The browser redirects and shows a success message
5. A `token.json` file is saved to `%LOCALAPPDATA%\AI Recruitment System\data\token.json`

From this point, the app reuses `token.json` and never opens the browser again (until the token is revoked or expires).

> **Note:** If you see a "This app isn't verified" warning from Google, click **Advanced** → **Go to [app name] (unsafe)**. This is expected for apps not submitted for Google verification — it's safe for your own use.

---

## Token File

After authentication, `token.json` is stored at:
```
%LOCALAPPDATA%\AI Recruitment System\data\token.json
```

This file contains your OAuth access and refresh tokens. Keep it private — anyone with this file can access your calendar.

If you need to re-authenticate (e.g. revoked access or switched accounts):
```bash
del "%LOCALAPPDATA%\AI Recruitment System\data\token.json"
```
The next calendar operation will trigger the browser flow again.

---

## Configuration

The following values in `src/google_calendar.py` can be changed if needed:

| Setting | Default | Description |
|---|---|---|
| `CALENDAR_ID` | `'primary'` | Which calendar to use. `'primary'` = your main calendar. Use a calendar ID for a specific shared calendar. |
| `INTERVIEW_DURATION` | `60` | Duration of each interview event in minutes |
| `TIMEZONE` | `'Asia/Kolkata'` | IANA timezone string — change to match your location |
| `LOOKAHEAD_DAYS` | `14` | How many days ahead to scan for free slots |
| `WORK_HOUR_START` | `9` | Work day starts at (24-hour) |
| `WORK_HOUR_END` | `18` | Work day ends at (24-hour) |
| `SLOT_INTERVAL_MINS` | `60` | Slot granularity — check for free slots every N minutes |

**Finding your Calendar ID:**
1. Open [calendar.google.com](https://calendar.google.com)
2. Hover over a calendar in the left sidebar → click the three-dot menu → **Settings and sharing**
3. Scroll down to **Integrate calendar** → copy the **Calendar ID**

---

## How Scheduling Uses the Calendar

When Google Calendar is available and authenticated:

1. The scheduling module calls `get_free_slots()` to fetch HR's actual calendar availability
2. Free slots within working hours (9 AM – 6 PM, next 14 days) that don't conflict with existing events are returned
3. These slots are offered to candidates instead of manually entered times
4. When a candidate confirms a slot, `create_interview_event()` creates the event in Google Calendar with:
   - Title: `Interview — {candidate_name} — {job_title}`
   - Start and end times (60 minutes)
   - Description: candidate profile summary
   - Attendees: candidate email (receives a Google Calendar invite)

---

## Scopes

The app requests this OAuth scope:

```
https://www.googleapis.com/auth/calendar
```

This grants full read/write access to the calendar. The app uses it to:
- Read free/busy information (`freebusy.query`)
- Create events (`events.insert`)

If you prefer read-only free/busy checks and no event creation, you can change to:
```
https://www.googleapis.com/auth/calendar.readonly
```
But then event creation will fail.

---

## Troubleshooting Google Calendar

### `FileNotFoundError: 'credentials.json' not found`
→ Follow the setup steps above to download `credentials.json` from Google Cloud Console and place it in the correct location.

### `Token has been expired or revoked`
→ Delete `token.json` and re-authenticate:
```bash
del "%LOCALAPPDATA%\AI Recruitment System\data\token.json"
```

### `Access blocked: This app's request is invalid`
→ The OAuth consent screen is not configured correctly. Go back to Google Cloud Console → APIs & Services → OAuth consent screen and complete all required fields.

### Calendar events not showing up
→ Check that `CALENDAR_ID` is set correctly. `'primary'` works for most accounts. If you use a workspace account, the primary calendar ID may be your email address (e.g. `you@company.com`).

### `HttpError 403: The caller does not have permission`
→ The Google Calendar API is not enabled for your project. Go to APIs & Services → Library → Google Calendar API → Enable.
