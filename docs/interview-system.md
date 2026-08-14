# Interview System

This document covers how the candidate interview portal works — token authentication, question generation, voice mode, proctoring, and how sessions are stored.

---

## Overview

The interview system runs as a separate HTTPS server (port 5000) that candidates access from their own browsers. Each candidate gets a unique one-time URL. The HR manager monitors sessions from the dashboard.

The flow for each candidate:
```
Candidate opens their URL
        │
Token validated
        │
Interview session created
        │
8 questions generated (AI, personalised)
        │
Candidate answers each question
(text input or voice via Vosk)
        │
Each answer evaluated by AI
        │
Webcam proctor runs throughout
        │
Session ends → transcript saved
        │
HR generates PDF report
```

---

## Interview Tokens

Each candidate gets a unique interview token generated during the scheduling stage. The token is a UUID stored in the database.

**Candidate URL format:**
```
https://<server-ip>:5000/candidate-interview/<token>
```

**How token validation works:**
1. Candidate opens the URL
2. Server looks up the token in the database
3. If valid: session is created, interview starts
4. If invalid/expired: candidate sees an error page

The token is associated with:
- Candidate name
- Job title
- NLP source file (used to load their profile for personalised questions)

---

## Question Generation

Questions are generated once at the start of the interview using the candidate's NLP profile.

### Question Plan
- **5 technical questions** — specific to the candidate's domain, skills, and past experience
- **3 behavioral questions** — STAR format (Situation, Task, Action, Result)

The AI is given the candidate's full NLP JSON (skills, experience, projects, certifications) and the job title, then asked to generate questions that:
- Match the candidate's actual domain and technology stack
- Vary in difficulty (easy → medium → hard)
- Are personalised — not generic

For example, a candidate with Python and FastAPI experience will get Python/API-specific technical questions, not generic "tell me about yourself" style questions.

If the NLP profile is not available (the NLP stage was skipped), the system falls back to generic questions based on the job title.

### Temperature
Question generation uses `temperature=0.3` (slightly creative) compared to `0.0` for extraction tasks, so questions are varied rather than identical across candidates.

---

## The Interview Session (INTERVIEW_PLAN)

The questions are presented in a fixed order defined by `INTERVIEW_PLAN` in `app/routes/interview.py`. Each entry specifies the question type (technical/behavioral) and topic.

A session contains:
- `session_id` — UUID for this interview session
- `session_key` — HMAC-signed key used to authenticate API calls during the session
- `transcript` — list of Q&A pairs built up as the interview progresses
- `pending_question` — the current question stored server-side (the client cannot modify it)
- `proctor_data` — running proctor summary

> **Security note:** Questions are stored server-side. The client sends answers but cannot modify or skip questions. The server issues each question and validates answers against its own record — not what the client claims.

---

## Answer Evaluation

After each answer is submitted, the AI evaluates it and returns:

| Field | Description |
|---|---|
| `score` | 0–10 integer score |
| `feedback` | 2–3 sentence constructive feedback |
| `follow_up` | Optional follow-up question if the answer was incomplete |

Evaluation uses `temperature=0.0` for consistent, deterministic scoring.

The answer and evaluation are appended to the transcript immediately. If AI evaluation fails (provider error, timeout), the answer is still saved — just without a score.

---

## Answer Time Limit

Each answer has a soft time limit of **120 seconds**. If a candidate takes longer:
- The proctoring system records an "answer time exceeded" flag
- The interview is not automatically stopped — the candidate can still finish

---

## Voice Mode

Voice mode uses two libraries:
- **Vosk** — offline speech-to-text (STT)
- **pyttsx3** — offline text-to-speech (TTS)

Both work entirely offline — no internet required.

### How Voice Mode Works

1. The candidate enables Voice Mode in their interview session
2. Questions are read aloud by pyttsx3 (TTS)
3. The candidate speaks their answer
4. Vosk records and transcribes the speech in real time
5. The transcribed text is shown to the candidate for review before submission
6. Candidate submits (or re-records)

### Requirements for Voice Mode

| Component | Requirement |
|---|---|
| Vosk model | Must be present at `models/vosk-model-small-en-in-0.4/` |
| Microphone | Any working system microphone |
| pyttsx3 | Installed (included in `requirements.txt`) |

**Check if voice mode is available:**
```bash
python -c "from src.voice_interview import check_microphone, check_tts; print(check_microphone(), check_tts())"
```

If either check returns `available: False`, voice mode will be disabled for that session. The interview continues in text mode.

### Vosk Model

The small English-India model (`vosk-model-small-en-in-0.4`) is bundled in the `models/` folder. It works reasonably well for standard English accents. If you need a different model:

```bash
python scripts/setup_vosk.py
```

This script downloads and sets up an alternative Vosk model.

---

## Webcam Proctoring

Proctoring runs as a **background thread** throughout the interview. The candidate's webcam is captured and analysed without interrupting the interview flow.

### How It Works

The `WebcamProctor` class in `src/webcam_proctor.py`:

1. Opens the webcam via OpenCV on `start()`
2. Reads frames continuously at ~30fps in a background thread
3. Every **2 seconds** (`CHECK_INTERVAL`), analyses the current frame for faces
4. Encodes frames as base64 JPEG (quality 60) for live streaming to the browser
5. Stops on `stop()` and returns a summary report

### Face Detection

Two detection methods are available:

| Method | When Used | How to Enable |
|---|---|---|
| **MediaPipe** | Primary — more accurate | `pip install mediapipe>=0.10.9` |
| **OpenCV Haar cascade** | Fallback — always available | No setup needed |

MediaPipe is used if installed; otherwise the system automatically falls back to OpenCV's built-in Haar cascade face detector.

### Violation Flags

| Violation | Trigger Condition |
|---|---|
| **No face detected** | Face absent for 3 consecutive checks (6 seconds) |
| **Multiple faces detected** | 2+ faces visible for 2 consecutive checks (4 seconds) |
| **Tab switch** | Browser visibility API fires `visibilitychange` event |
| **Copy-paste** | `copy`, `cut`, or `paste` events fired in the interview window |

All violations are timestamped and included in the interview transcript and PDF report.

### Thresholds Explained

- `CHECK_INTERVAL = 2.0` seconds — face check frequency
- `NO_FACE_THRESHOLD = 3` — 3 consecutive "no face" checks = 6 seconds before flagging
- `MULTI_FACE_THRESHOLD = 2` — 2 consecutive "multiple faces" checks before flagging

The thresholds exist to avoid false positives from brief occlusion (e.g. candidate adjusting glasses, looking down at notes for a second).

### Frame Resolution

Frames are captured at 320×240 pixels — small enough for smooth real-time streaming, sufficient for face detection accuracy.

### What HR Sees

From the Interview dashboard, HR can:
- See a live feed of the candidate's webcam (base64 JPEG stream)
- See the current proctor status (face count, active flags)
- See the running violation count

---

## Interview Transcript

At the end of the session, a JSON transcript is saved to `data/output/interviews/`:

```json
{
  "session_id": "...",
  "candidate_name": "...",
  "job_title": "...",
  "started_at": "2026-08-14T15:00:00",
  "completed_at": "2026-08-14T15:45:00",
  "transcript": [
    {
      "question_number": 1,
      "question_type": "technical",
      "topic": "Python",
      "question": "...",
      "answer": "...",
      "score": 7,
      "feedback": "...",
      "answer_time_seconds": 45
    }
  ],
  "proctor_summary": {
    "total_flags": 2,
    "no_face_events": 1,
    "multi_face_events": 0,
    "tab_switches": 1,
    "copy_paste_events": 0
  }
}
```

---

## Multiple Sessions

Each candidate token can only be used for one active session at a time. If a session is interrupted (browser closed, network drop), the candidate can re-open their URL to resume from the last saved question.

Sessions are stored in an in-memory dictionary (`interview_session`) and flushed to disk as JSON on completion.
