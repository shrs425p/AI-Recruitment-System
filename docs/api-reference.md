# API Reference

This reference lists the main Flask routes used by the desktop UI and candidate portal. HTML routes render pages; API routes return JSON unless noted.

## Health and Status

| Method | Route | Purpose |
|---|---|---|
| GET | `/api/health` | Check database and runtime data directory |
| GET | `/api/stats` | Dashboard counts for pipeline stages |
| GET | `/api/task-status` | Current background task state |

## Pages

| Method | Route | Page |
|---|---|---|
| GET | `/` | Redirects to dashboard |
| GET | `/dashboard` | Pipeline dashboard |
| GET | `/upload` | Resume upload |
| GET | `/nlp` | NLP extraction |
| GET | `/ranking` | Candidate ranking |
| GET | `/scheduling` | Interview scheduling |
| GET | `/interview` | Interview management |
| GET | `/reports` | Reports |
| GET | `/settings` | Settings |
| GET | `/logs` | Live logs |

## Authentication

| Method | Route | Purpose |
|---|---|---|
| GET/POST | `/login` | HR login when enabled |
| GET | `/logout` | Clear HR session |

## Pipeline

| Method | Route | Purpose |
|---|---|---|
| POST | `/api/upload` | Upload resume files |
| POST | `/api/run-pdf` | Convert resumes to text |
| POST | `/api/run-nlp` | Extract NLP profiles |
| POST | `/api/run-ranking` | Rank candidates against a job description |
| POST | `/api/schedule` | Generate interview schedule |
| POST | `/api/run-auto-pipeline` | Start one-click background pipeline |
| POST | `/api/reset-pipeline` | Clear generated pipeline outputs |
| POST | `/api/open-output-folder` | Open output folder on Windows |

## Auto-Pipeline Response

`POST /api/run-auto-pipeline`

```json
{
  "success": true,
  "started": true,
  "message": "Auto-pipeline started.",
  "task": {
    "status": "running",
    "step": "queued"
  }
}
```

Poll `GET /api/task-status` for completion:

```json
{
  "auto_pipeline": {
    "status": "done",
    "step": "complete",
    "result": {
      "txt": {},
      "nlp": {},
      "ranking": {},
      "scheduling": {},
      "reports": {}
    }
  }
}
```

## Google Calendar

| Method | Route | Purpose |
|---|---|---|
| GET | `/api/calendar/status` | Check OAuth status |
| POST | `/api/calendar/auth` | Start OAuth flow |
| GET | `/api/calendar/free-slots` | Load available slots |
| POST | `/api/calendar/create-events` | Create events for confirmed interviews |

## Candidate Interviews

| Method | Route | Purpose |
|---|---|---|
| POST | `/api/generate-interview-links` | Create candidate tokens |
| GET | `/api/interview-links` | List generated tokens |
| GET | `/candidate-interview/<token>` | Candidate interview page |
| POST | `/api/candidate/interview/start` | Start candidate session |
| POST | `/api/candidate/interview/answer` | Submit answer and receive next question |
| POST | `/api/candidate/interview/finish` | Save transcript and mark token used |
| POST | `/api/candidate/proctor/browser_flag` | Record browser integrity flag |
| POST | `/api/candidate/proctor/analyze-frame` | Analyze webcam frame |

## Reports

| Method | Route | Purpose |
|---|---|---|
| POST | `/api/generate-reports` | Generate reports from transcripts |
| GET | `/api/report-pdf/<filename>` | Download report as PDF |
| GET | `/api/save-report-pdf/<filename>` | Save generated PDF into reports folder |

## Logs

| Method | Route | Purpose |
|---|---|---|
| GET | `/stream-logs` | Server-Sent Events log stream |

## Error Responses & Rate Limiting

Centralized Flask error middleware returns structured JSON responses for `/api/*` routes:

```json
{
  "error": "Rate limit exceeded. Please wait before retrying.",
  "code": 429
}
```

- **Candidate API Rate Limiting**: `/api/candidate/*` endpoints enforce an IP-based rate limit (default 30 requests/minute). Requests exceeding this limit return `429 Too Many Requests`.
- **Session Keys**: Candidate interview answers require `X-Interview-Session-Key` header matching the active candidate session.

## Notes

- Login-protected endpoints use the `login_required` decorator when `LOGIN_ENABLED` is true.
- Long-running work should return quickly and update `pipeline_tasks`.
- Candidate portal endpoints are served over HTTPS for browser camera access.
