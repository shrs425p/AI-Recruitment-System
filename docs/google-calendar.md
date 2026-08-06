# Google Calendar

Google Calendar integration is optional. It imports available HR slots and creates interview events for confirmed candidates.

## Setup

1. Open Google Cloud Console.
2. Create or select a project.
3. Enable the Google Calendar API.
4. Create an OAuth 2.0 Client ID with application type `Desktop app`.
5. Download the JSON file as `credentials.json`.
6. Place it in the project root or runtime data directory.

## Authenticate

From the app:

1. Open Settings or Scheduling.
2. Start Google authentication.
3. Sign in with the HR calendar account.
4. Grant calendar access.

The app stores `token.json` in the runtime data folder for future runs.

## Free Slot Import

The free-slot endpoint scans the calendar, removes busy times, and returns available interview slots.

| Setting | Default |
|---|---|
| Calendar | `primary` |
| Lookahead | 14 days |
| Timezone | `Asia/Kolkata` |
| Workday | 09:00 to 18:00 |
| Slot size | 60 minutes |

## Event Creation

After scheduling candidates, create calendar events from the Scheduling page. Each event includes:

- Candidate name.
- Job title.
- Selected interview time.
- Interview duration.
- Reminder settings.

## Runtime Files

| File | Purpose |
|---|---|
| `credentials.json` | OAuth client credentials from Google Cloud |
| `token.json` | Generated access and refresh token |

Do not commit either file.

## Troubleshooting

| Problem | Fix |
|---|---|
| `credentials.json not found` | Download OAuth credentials and place them in the project root or runtime data folder |
| API not enabled | Enable Google Calendar API in Google Cloud Console |
| Token expired or revoked | Delete `token.json` and authenticate again |
| Browser does not open | Run from an interactive desktop session |
