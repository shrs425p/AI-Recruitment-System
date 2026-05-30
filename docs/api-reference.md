# API Reference

This document catalogues all HTTP endpoints exposed by the Flask application. All JSON endpoints consume and produce `application/json` unless noted otherwise. Pages that render HTML templates are marked as **[Page]**.

The application runs two servers:

| Server | Address | Audience |
|---|---|---|
| HTTP | `http://127.0.0.1:5001` | HR desktop (pywebview) |
| HTTPS | `https://0.0.0.0:5000` | Candidate interview portal (LAN) |

---

## Authentication

### Login

```
POST /login
```

Form data: `username`, `password`  
Redirects to `/` on success. Sets session cookie.  
Only active when `LOGIN_ENABLED = True` in config.

### Logout

```
GET /logout
```

Clears the session. Redirects to `/login`.

---

## Pages

| Route | Method | Description |
|---|---|---|
| `/` | GET | Dashboard home (pipeline status, stats) |
| `/upload` | GET | Resume upload page |
| `/nlp` | GET | NLP extraction status page |
| `/ranking` | GET | Ranking results page |
| `/scheduling` | GET | Interview scheduling page |
| `/interview` | GET | Interview management page |
| `/reports` | GET | Report download page |
| `/settings` | GET | Application settings page |
| `/logs` | GET | Live log stream page |
| `/rules` | GET | Interview rules page |

---

## Upload

### Upload Resumes

```
POST /api/upload
```

**Content-Type:** `multipart/form-data`  
**Field:** `files` (multiple file inputs)  
**Accepted types:** `.pdf`, `.png`, `.jpg`, `.jpeg`

**Response:**

```json
{
  "success": true,
  "uploaded": 5,
  "files": ["resume1.pdf", "resume2.pdf"]
}
```

---

## PDF to Text

### Trigger Conversion

```
POST /api/run-pdf
```

Converts all files in `data/resumes/` to `data/output/txt/`. Already-converted files are skipped.

**Response (streaming SSE):** Progress events  
**Final response:**

```json
{ "success": true, "processed": 5, "skipped": 2 }
```

---

## NLP Extraction

### Trigger Extraction

```
POST /api/run-nlp
```

Runs NLP extraction on all `.txt` files in `data/output/txt/`.

**Response (streaming SSE):** Progress events per file

### Get Extraction Status

```
GET /api/nlp/status
```

**Response:**

```json
{
  "total_txt": 10,
  "total_nlp": 8,
  "pending": 2,
  "files": [...]
}
```

---

## Ranking

### Trigger Ranking

```
POST /api/run-ranking
```

**Body:**

```json
{
  "job_title": "Senior Python Developer",
  "job_description": "We are looking for..."
}
```

**Response:**

```json
{
  "success": true,
  "ranked": 8,
  "output_file": "ranking_scores_20260530_1430.json"
}
```

### Get Latest Ranking

```
GET /api/ranking/latest
```

Returns the contents of the most recent `ranking_scores_*.json` file.

---

## Scheduling

### Generate Schedule

```
POST /api/schedule
```

**Body:**

```json
{
  "job_title": "Senior Python Developer",
  "hr_name": "HR Admin",
  "slots": ["2026-06-10 10:00", "2026-06-10 11:00", "2026-06-11 14:00"]
}
```

**Response:**

```json
{
  "success": true,
  "scheduled": [
    {
      "candidate_name": "Jane Smith",
      "rank": 1,
      "score": 92.5,
      "offered_slots": ["2026-06-10 10:00", "2026-06-10 11:00", "2026-06-11 14:00"],
      "selected_slot": "2026-06-10 10:00",
      "status": "CONFIRMED"
    }
  ]
}
```

### Update Slot

```
POST /api/update-slot
```

**Body:**

```json
{
  "candidate_name": "Jane Smith",
  "selected_slot": "2026-06-11 14:00"
}
```

---

## Google Calendar

### Check Auth Status

```
GET /api/calendar/status
```

**Response:**

```json
{
  "authenticated": true,
  "calendar_name": "Primary Calendar",
  "has_credentials": true,
  "has_token": true,
  "error": null
}
```

### Trigger Auth Flow

```
POST /api/calendar/auth
```

Opens OAuth2 browser flow. Returns `{ "success": true }` or `{ "success": false, "error": "..." }`.

### Get Free Slots

```
GET /api/calendar/free-slots?days=14
```

**Response:**

```json
{
  "success": true,
  "slots": ["2026-06-10 09:00", "2026-06-10 10:00"],
  "total_found": 28,
  "calendar_name": "Primary Calendar"
}
```

### Create Events

```
POST /api/calendar/create-events
```

Creates calendar events for all `CONFIRMED` candidates in the latest schedule.

**Response:**

```json
{
  "success": true,
  "created": ["Jane Smith", "John Doe"],
  "errors": []
}
```

---

## Interview

### Generate Interview Tokens

```
POST /api/generate-interview-links
```

Creates tokens for all confirmed candidates. Deletes previous tokens first.

**Response:**

```json
{ "success": true, "created": ["Jane Smith", "John Doe"] }
```

### List Interview Tokens

```
GET /api/interview-links
```

Returns all tokens with their candidate metadata and `used` status.

### Candidate — Start Interview

```
POST /api/candidate/interview/start
```

**Body:** `{ "token": "T_1748519432_a3f9c1" }`

**Response:**

```json
{
  "success": true,
  "session_id": "S_1748519432_b2e4f1",
  "first_q": "Tell me about yourself and your interest in this role."
}
```

### Candidate — Submit Answer

```
POST /api/candidate/interview/answer
```

**Body:**

```json
{
  "session_id": "S_...",
  "answer": "I have 5 years of experience in...",
  "question": "Tell me about yourself...",
  "topic": "Introduction",
  "type": "TECHNICAL",
  "question_num": 1,
  "time_taken": 45
}
```

**Response:**

```json
{
  "success": true,
  "done": false,
  "next_q": "Can you explain a complex problem you have solved?",
  "q_num": 2,
  "q_type": "TECHNICAL",
  "topic": "Problem Solving"
}
```

### Candidate — Finish Interview

```
POST /api/candidate/interview/finish
```

**Body:** `{ "session_id": "S_..." }`

Saves transcript, marks token as used, stops proctoring.

### Log Browser Proctoring Flag

```
POST /api/candidate/proctor/browser_flag
```

Records a client-side integrity event (tab switch, copy-paste, etc.).

### Analyze Webcam Frame

```
POST /api/candidate/proctor/analyze-frame
```

**Body:** `{ "session_id": "...", "frame": "<base64-encoded-jpeg>" }`

**Response:** `{ "success": true, "faces": 1, "flagged": false }`

---

## Reports

### Generate Report

```
POST /api/generate-report
```

**Body:** `{ "interview_file": "interview_Jane_Smith_20260610.json" }`

Generates a PDF report using `src/report_generator.py`.

### List Reports

```
GET /api/reports/list
```

Returns a list of all report files in `data/output/reports/`.

### Download Report

```
GET /api/reports/download/<filename>
```

Streams the PDF file.

---

## Settings

### Save General Settings

```
POST /api/settings/save
```

**Body:** All modified config keys as JSON.

### Save API Keys

```
POST /api/settings/api-keys
```

### Get AI Status

```
GET /api/ai/status
```

Returns whether Ollama is reachable and which model is loaded.

---

## Logs

### Live Log Stream

```
GET /api/logs/stream
```

**Content-Type:** `text/event-stream` (Server-Sent Events)  
Streams log entries from the `log_queue` in real time.

### Get Recent Logs

```
GET /api/logs
```

Returns the last N log lines from the queue.

---

## Pipeline Status

### Get Pipeline Task Status

```
GET /api/pipeline-status
```

**Response:**

```json
{
  "pdf":        { "status": "done" },
  "nlp":        { "status": "running", "started": 1748519432.0 },
  "ranking":    { "status": "idle" },
  "scheduling": { "status": "idle" },
  "interview":  { "status": "idle" }
}
```
