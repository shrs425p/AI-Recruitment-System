# API Reference

All routes are served by the same Flask application on both servers:
- HR Dashboard: `http://127.0.0.1:5001`
- Candidate Portal: `https://<server-ip>:5000`

Routes marked **[Auth Required]** require an active HR session (`session["logged_in"] = True`).  
Routes marked **[Token]** require a valid interview token.  
Routes under `/candidate-interview/` are public (token-validated internally).

---

## Health

### `GET /health`
Returns a simple health check. No authentication required.

**Response:**
```json
{ "status": "ok" }
```

---

## Authentication

### `GET /desktop-bootstrap`
Serves the pywebview bootstrap page that initiates nonce-based auto-login.  
Only meaningful when accessed from the embedded pywebview window.

---

### `POST /api/desktop-login`
Validates a nonce token and creates an authenticated desktop session.

**Request body:**
```json
{ "nonce": "<token_urlsafe_32>" }
```

**Response (success):**
```json
{ "success": true }
```

**Response (failure):**
```json
{ "error": "Unauthorized" }
```
HTTP 403

---

### `GET /login`
Shows the HR login form (only relevant when `LOGIN_ENABLED = True`).

---

### `POST /login`
Validates username + password and creates a session.

**Form fields:** `username`, `password`

**Response:** Redirect to dashboard on success, re-render login form on failure.

---

### `GET /logout`
Clears the session and redirects to login.

---

## Dashboard

### `GET /` → `GET /dashboard`
**[Auth Required]**  
Returns the HR dashboard HTML page.

---

### `GET /api/dashboard-stats`
**[Auth Required]**  
Returns aggregate statistics for the dashboard widgets.

**Response:**
```json
{
  "resumes_uploaded": 24,
  "nlp_processed": 22,
  "candidates_ranked": 18,
  "interviews_scheduled": 10,
  "interviews_completed": 7
}
```

---

## Upload

### `GET /upload`
**[Auth Required]**  
Returns the upload page.

---

### `POST /api/upload`
**[Auth Required]**  
Upload one or more resume files.

**Content-Type:** `multipart/form-data`  
**Field:** `files[]` — one or more files (PDF, PNG, JPG)

**Response:**
```json
{
  "success": true,
  "uploaded": ["resume1.pdf", "resume2.pdf"],
  "failed": []
}
```

---

## NLP Extraction

### `GET /nlp`
**[Auth Required]**  
Returns the NLP extraction page.

---

### `POST /api/nlp/run`
**[Auth Required]**  
Triggers NLP extraction on all unprocessed `.txt` files in `data/output/txt/`.  
Runs asynchronously — returns immediately, progress visible in the live log.

**Response:**
```json
{ "success": true, "message": "NLP extraction started" }
```

---

### `GET /api/nlp/status`
**[Auth Required]**  
Returns the current NLP processing status.

**Response:**
```json
{
  "total_txt": 24,
  "processed": 22,
  "pending": 2,
  "candidates": [
    {
      "name": "John Doe",
      "domain": "Software Engineering",
      "experience_years": 4,
      "source_file": "john_doe"
    }
  ]
}
```

---

## Ranking

### `GET /ranking`
**[Auth Required]**  
Returns the ranking page.

---

### `POST /api/ranking/run`
**[Auth Required]**  
Triggers candidate ranking against a provided job description.

**Request body:**
```json
{ "job_description": "We are looking for a Python developer..." }
```

**Response:**
```json
{
  "success": true,
  "ranked_candidates": [
    {
      "candidate_name": "John Doe",
      "total_score": 84,
      "percentage": 84,
      "hire_recommendation": "Strongly Recommend",
      "scores": {
        "domain_match": { "score": 18, "max": 20, "reason": "..." },
        "skills_match": { "score": 30, "max": 35, "reason": "..." },
        "experience_years": { "score": 18, "max": 20, "reason": "..." },
        "education": { "score": 12, "max": 15, "reason": "..." },
        "certifications": { "score": 6, "max": 10, "reason": "..." }
      },
      "strengths": ["Strong Python skills", "Relevant ML experience"],
      "gaps": ["No AWS certification"],
      "overall_verdict": "Strong candidate with directly relevant skills"
    }
  ]
}
```

---

## Scheduling

### `GET /scheduling`
**[Auth Required]**  
Returns the scheduling page.

---

### `POST /api/scheduling/create`
**[Auth Required]**  
Creates interview schedule for the top N candidates.

**Request body:**
```json
{
  "slots": ["2026-08-20 10:00", "2026-08-20 14:00", "2026-08-21 09:00"],
  "top_n": 10
}
```

**Response:**
```json
{
  "success": true,
  "scheduled": 10,
  "tokens_generated": 10
}
```

---

### `POST /api/scheduling/send-emails`
**[Auth Required]**  
Sends scheduling emails to all candidates with confirmed slots.

**Response:**
```json
{ "success": true, "sent": 10, "failed": 0 }
```

---

### `GET /api/scheduling/tokens`
**[Auth Required]**  
Returns all active interview tokens and their associated candidates.

**Response:**
```json
{
  "tokens": [
    {
      "token": "uuid-...",
      "candidate_name": "John Doe",
      "job_title": "Python Developer",
      "interview_url": "https://192.168.1.100:5000/candidate-interview/uuid-..."
    }
  ]
}
```

---

## Interview (HR Side)

### `GET /interview`
**[Auth Required]**  
Returns the interview management page for HR.

---

### `GET /api/interview/sessions`
**[Auth Required]**  
Returns all active interview sessions.

**Response:**
```json
{
  "sessions": [
    {
      "session_id": "...",
      "candidate_name": "John Doe",
      "current_question": 4,
      "total_questions": 8,
      "proctor_flags": 1,
      "status": "in_progress"
    }
  ]
}
```

---

### `GET /api/interview/proctor-frame/<session_id>`
**[Auth Required]**  
Returns the latest webcam frame for a session as a base64 JPEG string.

**Response:**
```json
{ "frame": "data:image/jpeg;base64,/9j/4AAQ..." }
```

---

## Interview (Candidate Side)

### `GET /candidate-interview/<token>`
Public — token validated internally.  
Returns the candidate interview portal page.

---

### `POST /api/candidate/start-session`
**[Token]**  
Validates the interview token and initialises the session.

**Request body:**
```json
{ "token": "<uuid>" }
```

**Response:**
```json
{
  "success": true,
  "session_id": "...",
  "session_key": "...",
  "first_q": "Tell me about your experience with Python.",
  "questions": [
    { "number": 1, "type": "technical", "topic": "Python", "text": "..." }
  ]
}
```

---

### `POST /api/candidate/submit-answer`
**[Token + Session Key]**  
Submits an answer to the current question.

**Request body:**
```json
{
  "token": "<uuid>",
  "session_id": "...",
  "session_key": "...",
  "answer": "I have 3 years of Python experience..."
}
```

**Response:**
```json
{
  "success": true,
  "score": 7,
  "feedback": "Good answer covering the key concepts...",
  "next_question": "Describe a situation where you had to debug a complex issue.",
  "is_complete": false
}
```

---

### `POST /api/candidate/end-session`
**[Token + Session Key]**  
Ends the interview session and saves the transcript.

**Response:**
```json
{ "success": true, "message": "Interview completed. Thank you." }
```

---

### `GET /api/candidate/proctor-status/<session_id>`
**[Token]**  
Returns the current proctoring status for the candidate's session.

**Response:**
```json
{
  "face_count": 1,
  "flags": 0,
  "status": "ok"
}
```

---

## Reports

### `GET /reports`
**[Auth Required]**  
Returns the reports page listing all completed interviews.

---

### `POST /api/reports/generate`
**[Auth Required]**  
Generates a PDF report for a completed interview.

**Request body:**
```json
{ "session_id": "..." }
```

**Response:**  
PDF file download (Content-Type: `application/pdf`)

---

## Settings

### `GET /settings`
**[Auth Required]**  
Returns the settings page.

---

### `POST /api/settings/save`
**[Auth Required]**  
Saves updated settings to the database.

**Request body:** JSON object with any subset of setting keys and their new values.

**Response:**
```json
{ "success": true }
```

---

### `POST /api/settings/change-password`
**[Auth Required]**  
Changes the HR dashboard password.

**Request body:**
```json
{
  "current_password": "...",
  "new_password": "..."
}
```

**Response:**
```json
{ "success": true }
```

---

## Logs

### `GET /logs`
**[Auth Required]**  
Returns the live log viewer page.

---

### `GET /api/logs/stream`
**[Auth Required]**  
Server-Sent Events (SSE) stream of application log lines.

**Content-Type:** `text/event-stream`

Each event is a plain-text log line from the application's log queue.

---

## Error Responses

All API endpoints return consistent error responses:

```json
{ "error": "<message>", "code": <http_status_code> }
```

| Status | Meaning |
|---|---|
| 400 | Bad request — missing or invalid parameters |
| 401 | Unauthorised — not logged in |
| 403 | Forbidden — nonce invalid or access denied |
| 404 | Not found — resource does not exist |
| 413 | Upload too large — file exceeds `ARS_MAX_UPLOAD_BYTES` |
| 429 | Too many requests — rate limit exceeded |
| 500 | Internal server error |
