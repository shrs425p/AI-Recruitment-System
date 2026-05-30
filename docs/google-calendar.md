# Google Calendar Integration

The scheduling module integrates with Google Calendar to create interview events automatically. This document explains how to set up OAuth2 credentials, authenticate, and use the calendar features.

---

## Prerequisites

- A Google account with Google Calendar enabled.
- A Google Cloud project with the **Google Calendar API** enabled.
- Python packages: `google-api-python-client`, `google-auth-httplib2`, `google-auth-oauthlib` (included in `requirements.txt`).

---

## Step 1 — Create Google Cloud Credentials

1. Open [https://console.cloud.google.com](https://console.cloud.google.com) and select or create a project.
2. Navigate to **APIs and Services > Library**.
3. Search for **Google Calendar API** and click **Enable**.
4. Navigate to **APIs and Services > Credentials**.
5. Click **Create Credentials > OAuth 2.0 Client ID**.
6. Set the application type to **Desktop app**.
7. Download the JSON file and rename it to `credentials.json`.
8. Place `credentials.json` in the project root directory (`AI-Recruitment-System/`).

---

## Step 2 — Authenticate

### Via the Settings UI

1. Open the application.
2. Navigate to **Settings > Google Calendar**.
3. Click **Authenticate with Google**.
4. A browser window opens — sign in and grant calendar access.
5. The access token is saved to `data/token.json` automatically.

### Via API

```
POST /api/calendar/auth
```

This triggers the same OAuth2 browser flow programmatically.

---

## Step 3 — Verify Authentication

```
GET /api/calendar/status
```

Response:

```json
{
  "authenticated": true,
  "calendar_name": "My Calendar",
  "has_credentials": true,
  "has_token": true,
  "error": null
}
```

If `authenticated` is `false`, check the `error` field for a diagnostic message.

---

## Creating Interview Events

### Automatic (from Scheduling Page)

After generating a schedule, click **Create Calendar Events** on the Scheduling page. This calls:

```
POST /api/calendar/create-events
```

The system reads the latest schedule file and creates one calendar event for each `CONFIRMED` candidate with a `selected_slot`.

### Programmatic

```python
from google_calendar import create_interview_event

result = create_interview_event(
    candidate_name="Jane Smith",
    source_file="jane_smith_resume",
    rank=1,
    score=92.5,
    slot="2026-06-10 10:00",
    job_title="Senior Python Developer",
    hr_name="HR Admin",
    hr_email="hr@company.com"
)
```

Returns:

```json
{
  "success": true,
  "event_id": "abc123xyz",
  "event_link": "https://calendar.google.com/calendar/event?eid=...",
  "error": null
}
```

---

## Calendar Event Format

Each created event contains:

| Field | Value |
|---|---|
| Title | `AI Interview — <candidate_name> for <job_title>` |
| Duration | 60 minutes (configurable via `INTERVIEW_DURATION`) |
| Timezone | `Asia/Kolkata` (configurable via `TIMEZONE`) |
| Color | Blueberry (Google Calendar color ID 9) |
| Reminders | Email 60 minutes before, popup 15 minutes before |

---

## Fetching Free Slots

The scheduling page can load HR's free calendar slots automatically:

```
GET /api/calendar/free-slots?days=14
```

Parameters:

| Parameter | Default | Description |
|---|---|---|
| `days` | `14` | Number of days ahead to scan |

The engine:
1. Fetches all existing events from the primary calendar.
2. Generates candidate slots at 60-minute intervals within working hours (9:00–18:00, Monday–Friday).
3. Eliminates slots that overlap with existing events.
4. Returns available slots as a list of datetime strings.

---

## Configuration Constants

These are defined at the top of `src/google_calendar.py` and can be edited directly:

| Constant | Default | Description |
|---|---|---|
| `CALENDAR_ID` | `'primary'` | Which calendar to use |
| `INTERVIEW_DURATION` | `60` | Event duration in minutes |
| `TIMEZONE` | `'Asia/Kolkata'` | IANA timezone string |
| `LOOKAHEAD_DAYS` | `14` | Days ahead to scan for free slots |
| `WORK_HOUR_START` | `9` | Start of working day (hour, 24h) |
| `WORK_HOUR_END` | `18` | End of working day (hour, 24h) |
| `SLOT_INTERVAL_MINS` | `60` | Interval between candidate slots |

---

## Token and Credential Files

| File | Location | Description |
|---|---|---|
| `credentials.json` | Project root or `data/` | OAuth2 client credentials (from Google Cloud Console) |
| `token.json` | `data/token.json` | Access and refresh token (auto-generated after first login) |

The application checks `data/credentials.json` first, then the project root. On first login, `data/token.json` is created automatically. Subsequent runs reuse the cached token without opening a browser.

---

## Revoking Access

To revoke calendar access:

1. Go to [https://myaccount.google.com/permissions](https://myaccount.google.com/permissions).
2. Revoke the application.
3. Delete `data/token.json` from the project.

The next calendar operation will trigger a fresh login prompt.

---

## Troubleshooting

| Error | Cause | Resolution |
|---|---|---|
| `'credentials.json' not found` | File missing from root and `data/` | Download from Google Cloud Console and place in project root |
| `Calendar API has not been used` | API not enabled for the project | Enable Google Calendar API in Google Cloud Console |
| `Token expired or invalid` | Refresh token revoked | Delete `data/token.json` and re-authenticate |
| `accessNotConfigured` | API disabled | See the `enable_url` in the error response to enable it |
