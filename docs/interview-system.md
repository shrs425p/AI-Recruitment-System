# Interview System

This document explains the candidate interview portal architecture, including token authentication, configurable interview lengths, adaptive conversational follow-up probing, proctoring integrity, and real-time completion notifications.

---

## Architecture

The interview system runs as a dedicated HTTPS service (port 5000) that candidates access from their own browsers. It is completely isolated from the administrative HR server (`127.0.0.1:5001`).

```
Candidate Browser                          Candidate Server (Port 5000)
       │                                                │
       │─── 1. Access https://<host-ip>:5000/candidate-interview/<token> ──►
       │                                                │ Validate Token
       │                                                │ Check Candidate Consent
       │◄── 2. Render Interview UI + Web Speech / Cam ──│
       │                                                │
       │─── 3. Request Start (POST /start) ─────────────► Create Session ID & Key
       │                                                │ Generate Question Plan
       │◄── 4. Deliver Q1 ──────────────────────────────│
       │                                                │
       │─── 5. Submit Answer A1 ────────────────────────► Server Records Monotonic Time
       │                                                │ Score Answer (4-Part Rubric)
       │                                                │ Check should_probe_further()
       │◄── 6. Adaptive Probe or Next Question ─────────│
       │                                                │
       │─── 7. Final Question Completed ────────────────► Save Transcript (JSON + TXT)
       │                                                │ Emit HR Desktop Notification
       │◄── 8. Completion Confirmation ─────────────────│ Update Session in DB
```

---

## 1. Interview Tokens & Security Isolation

Each shortlisted candidate receives a unique, cryptographically random interview token generated during the scheduling stage.

### Candidate Access URL
```
https://<server-ip>:5000/candidate-interview/<token>
```

### Access Control Rules
1. **Candidate Consent:** Candidates must explicitly check a privacy consent acknowledgment agreeing to webcam monitoring and answer processing before the session commences.
2. **Session Key Validation:** Upon starting, the server returns an HMAC session key (`session_key`). All subsequent answer submissions must provide this key via the `X-Interview-Session-Key` header and request body.
3. **HR Route Protection:** The candidate application explicitly rejects all administrative HR endpoints (`/dashboard`, `/ranking`, `/reports`, etc.), returning HTTP 404.

---

## 2. Configurable Interview Length & Limits

Recruiters can adjust interview duration and difficulty directly from the Settings page without modifying source code:

| Setting Parameter | Configuration Key | Default Value | Configurable Range |
|---|---|---|---|
| Technical Questions Count | `INTERVIEW_TECH_QUESTIONS` | 5 | 3 to 10 questions |
| Behavioral Questions Count | `INTERVIEW_BEHAVIORAL_QUESTIONS` | 3 | 1 to 5 STAR questions |
| Per-Question Time Limit | `INTERVIEW_TIME_LIMIT` | 120 seconds | 60s, 90s, 120s, 180s |

These settings are stored dynamically in the `app_settings` SQLite table and immediately apply to new interview sessions.

---

## 3. Adaptive Question Generation & Blueprints

Questions are generated dynamically based on the verified job title, domain, and extracted technical skills from the candidate's NLP profile.

### Role-Adaptive Blueprints (`is_tech_role`)
The engine dynamically analyzes job title and domain keywords to determine role type:
- **Technical Roles:** Emphasizes architecture, algorithmic problem solving, concurrency, data structures, and concrete framework implementations.
- **Non-Technical Roles (e.g. Marketing, Sales, Operations, HR):** Bypasses software questions and dynamically structures topics around strategic planning, ROI metrics, stakeholder negotiations, conflict resolution, and operational crisis management.

### Adaptive Conversational Probing (`should_probe_further`)
If a candidate submits a shallow, high-level, or textbook-definition answer, the interview bot dynamically interjects with a follow-up probing question:
- **Trigger Conditions:** Depth score $\le 1$ or total rubric score $< 7$ with at least 5 words provided. Blank answers or explicit skips are not probed.
- **Probe Construction (`generate_adaptive_followup`):** Extracts technologies or concepts mentioned in the candidate's answer and asks for practical implementation specifics, real-world edge cases, or trade-offs.

---

## 4. Multi-Dimensional Answer Evaluation

Each candidate answer is evaluated across four rubric dimensions using deterministic AI evaluation (`temperature=0.0`):

| Rubric Dimension | Max Score | Evaluation Criteria |
|---|---|---|
| **Relevance** | 3 pts | Did the candidate directly answer the specific question asked? |
| **Depth** | 3 pts | Did they provide practical implementation details, edge cases, and trade-offs rather than generic definitions? |
| **Clarity** | 2 pts | Is the answer articulate, structured, and easy to follow? |
| **Correctness** | 2 pts | Is the technical explanation accurate according to domain standards? |
| **Total** | **10 pts** | Sum of component dimensions. |

The evaluation returns a JSON payload including numerical breakdown, constructive feedback, identified strengths, and technical gaps.

---

## 5. Proctoring & Anti-Tampering Safeguards

A background thread monitors integrity continuously during the interview:

### Face Absence and Multi-Face Detection
- Uses `MediaPipe` face detection with `OpenCV` Haar cascade fallback.
- **No Face Detected:** Flagged if no face is detected for 5 consecutive frames.
- **Multiple Faces Detected:** Flagged if more than 1 face appears in the webcam frame for 3 consecutive frames.

### Copy-Paste & Speed Ingestion
- If a candidate submits an answer longer than 100 characters in less than 2.0 seconds, the system logs a `SUSPICIOUSLY_FAST_ANSWER` / `COPY_PASTE_DETECTED` violation.

### Anti-Tamper Elapsed Time Calculation
- Client-submitted timestamps are not trusted for duration calculations.
- The server records high-resolution monotonic timestamps (`time.monotonic()`) when a question is issued and when the answer is received.
- If duration exceeds the configured `INTERVIEW_TIME_LIMIT`, a `TIME_LIMIT_EXCEEDED` flag is raised.

---

## 6. Voice Synthesis and Transcription

Candidates can conduct the interview via text or interactive voice mode:
- **Speech Synthesis (TTS):** Browser-native `window.speechSynthesis` speaks questions aloud. Markdown headers, asterisks, and code backticks are stripped server-side prior to synthesis to produce natural speech.
- **Speech Recognition (STT):** Browser-native `window.webkitSpeechRecognition` transcribes speech into text in real time. Backend Vosk or Google speech fallback is available if browser STT is unsupported.

---

## 7. Automated Real-Time HR Completion Notification

When the final question is answered, the session finalizes:
1. Complete transcripts and evaluation metrics are written to `data/output/interviews/interview_<name>.json` and `.txt`.
2. The server calls `app.database.create_hr_notification`:
   - Title: *"Candidate Interview Completed"*
   - Message: *"Jane Doe has completed the interview for Senior Python Developer. Report is ready."*
3. The HR manager's desktop interface displays an immediate notification and increments the unread notification badge.
