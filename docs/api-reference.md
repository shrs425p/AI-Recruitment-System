# API Reference

All routes are served by the Flask application:
- **HR Dashboard Server:** `http://127.0.0.1:5001`
- **Candidate Portal Server:** `https://<server-ip>:5000`

### Security & Header Conventions
- **[Auth Required]:** Requires an active HR session (`session["logged_in"] = True`).
- **[CSRF Required]:** State-changing requests (`POST`, `PUT`, `DELETE`, `PATCH`) require a valid token in the `X-CSRF-Token` header.
- **[Session Key Required]:** Candidate interview requests require a valid HMAC session key in the `X-Interview-Session-Key` header and JSON body.
- Candidate portal routes under `/candidate-interview/` validate tokens internally.

---

## 1. System Health & Diagnostics

### `GET /api/health`
Returns system health, database status, and operational metrics. No authentication required.

**Response:**
```json
{
  "status": "ok",
  "database": "ok",
  "success": true
}
```

### `GET /api/stats`
**[Auth Required]**  
Returns telemetry counters across pipeline stages.

**Response:**
```json
{
  "pdf_count": 14,
  "txt_count": 14,
  "nlp_count": 14,
  "pending_txt": 0,
  "pending_nlp": 0,
  "has_ranking": true,
  "has_schedule": true,
  "interview_count": 9,
  "report_count": 9,
  "tasks": {}
}
```

### `GET /api/task-status`
**[Auth Required]**  
Returns the execution state of asynchronous pipeline workers.

---

## 2. Authentication & Session Security

### `GET /desktop-bootstrap`
Renders the bootstrap view for embedded desktop webview authentication.

### `POST /api/desktop-login`
Validates a single-use desktop nonce and initializes an authenticated desktop session.

**Request body:**
```json
{ "nonce": "<cryptographic_nonce_string>" }
```

### `POST /login`
Authenticates HR credentials using scrypt-hashed passwords.

**Form fields:** `username`, `password`

### `GET /logout`
Clears session state and cookies.

---

## 3. Resume Upload & Document Extraction

### `POST /api/upload`
**[Auth Required] [CSRF Required]**  
Uploads resumes. Accepts Microsoft Word (`.docx`), PDF (`.pdf`), and image files (`.png`, `.jpg`).

**Payload:** `multipart/form-data` with `files[]`

**Response:**
```json
{
  "success": true,
  "uploaded": 3,
  "files": ["resume_001.docx", "resume_002.pdf"]
}
```

### `GET /resumes/<filename>`
**[Auth Required]**  
Safely streams the uploaded resume file for HR inspection.

---

## 4. Candidate Ranking & Shortlisting

### `POST /api/ranking/rank`
**[Auth Required] [CSRF Required]**  
Ranks candidates against a Job Description using customizable weights and knockout rules.

**Request body:**
```json
{
  "job_description": "We are seeking a Senior Python Engineer...",
  "weights": {
    "skills_match": 35,
    "experience_years": 20,
    "domain_match": 20,
    "education": 15,
    "certifications": 10
  },
  "knockout_rules": {
    "min_experience_years": 3.0,
    "required_skills": ["Python", "Docker"]
  }
}
```

### `GET /api/ranking/export/csv`
**[Auth Required]**  
Exports candidate rankings and rubric breakdowns as an RFC 4180 CSV spreadsheet.

**Response:** File stream (`Content-Type: text/csv; charset=utf-8`).

### `POST /api/candidate/<int:candidate_id>/notes`
**[Auth Required] [CSRF Required]**  
Attaches recruiter notes and status tags to a candidate record in SQLite.

**Request body:**
```json
{
  "notes": "Strong candidate with direct distributed caching experience.",
  "tags": "Shortlisted, Team Lead"
}
```

---

## 5. Candidate Deletion & GDPR Purge

### `DELETE /api/candidate/<int:candidate_id>`
**[Auth Required] [CSRF Required]**  
Permanently purges a candidate record from SQLite and unlinks all associated resumes, text extractions, NLP profiles, and interview transcripts from disk.

**Response:**
```json
{
  "success": true,
  "id": 42,
  "message": "Candidate and all associated data purged successfully."
}
```

---

## 6. Interview Scheduling

### `POST /api/schedule`
**[Auth Required] [CSRF Required]**  
Generates schedules for top-ranked candidates across specified datetime slots.

**Request body:**
```json
{
  "slots": ["2026-10-25 10:00", "2026-10-25 14:00", "2026-10-26 11:00"],
  "top_n": 5
}
```

### `POST /api/update-slot`
**[Auth Required] [CSRF Required]**  
Updates the scheduled interview slot for a specific candidate.

**Request body:**
```json
{
  "candidate_name": "Jane Doe",
  "selected_slot": "2026-10-26 14:00"
}
```

---

## 7. Candidate Interview (Port 5000)

### `POST /api/candidate/interview/start`
Validates interview token and initializes candidate session.

**Request body:**
```json
{
  "token": "<uuid_token>",
  "consent": true
}
```

**Response:**
```json
{
  "session_id": "sess_9182371",
  "session_key": "hmac_key_9182",
  "first_question": "Can you explain how you design distributed microservices?",
  "question_num": 1,
  "total_questions": 8
}
```

### `POST /api/candidate/interview/answer`
**[Session Key Required]**  
Submits candidate answer for rubric evaluation and adaptive probing.

**Headers:** `X-Interview-Session-Key: <hmac_key>`

**Request body:**
```json
{
  "session_id": "sess_9182371",
  "session_key": "hmac_key_9182",
  "question_num": 1,
  "answer": "We used Redis streams with independent consumer groups...",
  "time_taken": 42.5
}
```

**Response:**
```json
{
  "evaluation": {
    "total": 9,
    "relevance": 3,
    "depth": 2,
    "clarity": 2,
    "correctness": 2,
    "feedback": "Strong architecture explanation."
  },
  "next_question": "How did you handle consumer group rebalancing under high load?",
  "is_complete": false
}
```

---

## 8. Real-Time HR Notifications

### `GET /api/notifications`
**[Auth Required]**  
Lists recent HR notifications.

**Query Parameters:**
- `limit` (int, default: 20)
- `unread_only` (bool, default: false)

### `GET /api/notifications/unread-count`
**[Auth Required]**  
Returns the number of unread notifications.

**Response:**
```json
{ "unread_count": 2 }
```

### `POST /api/notifications/<int:notif_id>/read`
**[Auth Required] [CSRF Required]**  
Marks a single notification as read.

### `POST /api/notifications/read-all`
**[Auth Required] [CSRF Required]**  
Marks all notifications as read.

---

## 9. Talent Intelligence & Analytics

### `GET /api/intelligence/analytics`
**[Auth Required]**  
Returns pre-computed data for all 6 recruitment analytics widgets.

**Response:**
```json
{
  "success": true,
  "skill_gap": { "demand": ["Python", "Docker"], "supply": {"Python": 12, "Docker": 4} },
  "experience_matrix": { "points": [...] },
  "question_difficulty": [ {"topic": "Architecture", "avg_score": 5.4} ],
  "proctoring_risk": { "clean_percent": 80.0, "low_warning_percent": 15.0, "high_risk_percent": 5.0 },
  "hiring_velocity": { "avg_screen_hours": 0.25, "avg_turnaround_hours": 22.0 },
  "talent_mix": { "domains": {...}, "education": {...} }
}
```

### `POST /api/intelligence/search`
**[Auth Required] [CSRF Required]**  
Performs semantic vector search across candidate resumes.

**Request body:**
```json
{ "query": "Distributed caching with Redis and async worker queues" }
```

### `POST /api/intelligence/compare`
**[Auth Required] [CSRF Required]**  
Generates side-by-side comparison metrics and an executive deliberation brief.

**Request body:**
```json
{
  "candidates": ["Alice Smith", "Bob Jones"],
  "job_context": "Senior Infrastructure Architect"
}
```

### `POST /api/intelligence/feedback-letter`
**[Auth Required] [CSRF Required]**  
Generates a structured, constructive candidate feedback letter.

**Request body:**
```json
{
  "candidate_name": "Alice Smith",
  "job_title": "Senior Infrastructure Architect"
}
```

---

## 10. Pipeline Automation & Maintenance

### `POST /api/run-auto-pipeline`
**[Auth Required] [CSRF Required]**  
Starts the background pipeline job running text extraction, NLP, ranking, and scheduling sequentially.

**Response:**
```json
{
  "success": true,
  "started": true,
  "message": "Auto-pipeline started."
}
```

### `POST /api/reset-pipeline`
**[Auth Required] [CSRF Required]**  
Safely clears pipeline task states and deletes generated JSON/TXT output files while preserving database structure.

### `POST /api/open-output-folder`
**[Auth Required] [CSRF Required]**  
Opens the local output folder in the native Windows File Explorer.
