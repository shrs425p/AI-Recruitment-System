# Interview System

This document covers the candidate interview system including token management, the candidate portal, voice interview mode, real-time proctoring, and session transcript storage.

---

## Overview

The interview system is designed for asynchronous, remote interviews. HR generates one-time access tokens for confirmed candidates. Candidates open a unique URL in their browser and complete the interview independently. The system evaluates answers in real time using AI.

---

## Token Management

### Generating Tokens

**Route:** `POST /api/generate-interview-links`

This endpoint reads the latest schedule file (`data/output/scheduling/schedule_*.json`), creates a unique token for each `CONFIRMED` candidate, and stores it in the `interview_tokens` table.

**Token format:** `T_<unix_timestamp>_<6-character hex>`

**Example token:** `T_1748519432_a3f9c1`

**Behavior:**
- All existing unused tokens are deleted before new ones are generated. This prevents accumulation of stale tokens across multiple scheduling sessions.
- Token generation is idempotent within a single scheduling session — re-generating tokens for the same schedule replaces previous tokens.

### Token Database Schema

| Column | Type | Description |
|---|---|---|
| `token` | TEXT PRIMARY KEY | Unique interview token |
| `candidate_name` | TEXT | Full name from NLP extraction |
| `source_file` | TEXT | Original resume filename stem |
| `job_title` | TEXT | Job role from scheduling session |
| `rank` | INTEGER | Candidate rank from ranking step |
| `score` | REAL | Ranking score (0–100) |
| `used` | INTEGER | 0 = unused, 1 = used |
| `created_at` | TEXT | ISO timestamp |

### Token Lifecycle

```
Token created (used = 0)
    |
    v
Candidate opens /candidate-interview/<token>
    |
    v
Interview session starts (token still used = 0)
    |
    v
Candidate completes interview -> POST /api/candidate/interview/finish
    |
    v
Token marked used = 1
    |
    v
Reopening the URL returns "Invalid or expired interview token"
```

### Interview Link Format

```
https://<hr-machine-ip>:5000/candidate-interview/<token>
```

HTTPS is required. The self-signed certificate will trigger a browser warning — candidates must accept it to proceed.

---

## Candidate Interview Portal

The candidate portal is served at `/candidate-interview/<token>` and is a self-contained single-page application.

### Session Flow

1. Candidate opens the link and sees the introduction screen.
2. The portal calls `POST /api/candidate/interview/start` with the token.
3. The server validates the token, creates an in-memory session, starts proctoring, and returns the first question.
4. The candidate answers each question and submits via `POST /api/candidate/interview/answer`.
5. The server evaluates the answer and returns the next question.
6. After the final question, the candidate calls `POST /api/candidate/interview/finish`.
7. The transcript JSON is saved to `data/output/interviews/`.

### Question Structure

The interview consists of 5 questions by default:

| Question | Type | Topic |
|---|---|---|
| 1 | Technical | Introduction |
| 2 | Technical | Problem Solving |
| 3 | Technical | System Design |
| 4 | Behavioural | Teamwork |
| 5 | Behavioural | Conflict Resolution |

Questions are generated dynamically by `generate_interview_question` in `src/interview_bot.py` using the candidate's name, job title, and prior conversation history as context.

---

## Voice Interview Mode

The voice interview engine (`src/voice_interview.py`) enables speech-based Q&A using fully offline components.

### Components

| Component | Library | Model |
|---|---|---|
| Text-to-Speech (TTS) | pyttsx3 | Windows SAPI voices (built-in) |
| Speech-to-Text (STT) | Vosk | `vosk-model-small-en-in-0.4` (Indian English) |

### Model Download

```bat
python scripts/setup_vosk.py          # 36 MB Indian English model
python scripts/setup_vosk.py --large  # 1 GB high-accuracy model
```

The model is stored at `models/vosk-model-small-en-in-0.4/`.

### Fallback Behaviour

If the Vosk model directory is not found, the voice module falls back to the `speech_recognition` library using Google Web Speech API (requires internet). If that also fails, text input mode is used.

### Voice Session Architecture

```
pyttsx3 TTS speaks the question
    |
    v
Vosk STT listens on microphone (blocking, 120s timeout)
    |
    v
Transcribed text is submitted as the candidate's answer
    |
    v
AI evaluates the transcribed answer
```

---

## Proctoring

The proctoring system monitors the candidate during the interview for integrity signals.

### Browser-Level Proctoring

Detected client-side and reported to the server via `POST /api/candidate/proctor/browser_flag`:

- Tab switching / focus loss
- Full-screen exit
- Right-click context menu access
- Copy-paste keyboard shortcuts (Ctrl+C, Ctrl+V)

### Webcam-Level Proctoring

Handled by `src/webcam_proctor.py` which runs in a background thread during the interview session.

**Detection methods (in priority order):**

1. **MediaPipe Face Mesh** — High accuracy, requires `mediapipe>=0.10` installed.
2. **Haar Cascade (OpenCV)** — Fallback if MediaPipe is unavailable.

**Flags raised:**

| Flag | Trigger |
|---|---|
| `NO_FACE` | No face detected for > 3 consecutive frames |
| `MULTIPLE_FACES` | More than one face in the frame |
| `FACE_AWAY` | Head pose angle exceeds threshold |

### Proctoring Status

At session end, the proctoring summary is attached to the interview transcript:

```json
{
  "proctoring_status": "PASSED",
  "flagged_count": 0,
  "webcam_log": []
}
```

- `PASSED` — fewer than 3 proctoring events
- `SUSPICIOUS` — 3 or more proctoring events

---

## Answer Evaluation

Each answer is scored by the AI using the following rubric (10 points maximum):

| Dimension | Max | Description |
|---|---|---|
| Relevance | 3 | Does the answer address the question directly? |
| Depth | 3 | Does it demonstrate domain knowledge? |
| Clarity | 2 | Is it well-structured and professional? |
| Correctness | 2 | Is it technically accurate? |

**Total score per question: 0–10**  
**Total interview score: sum across all questions**  
**Percentage: `(total_score / max_score) * 100`**

---

## Transcript Storage

Transcripts are saved in JSON format to `data/output/interviews/interview_<name>_<timestamp>.json`.

### Transcript Schema

```json
{
  "candidate_name": "...",
  "source_file": "...",
  "rank": 1,
  "ranking_score": 87.5,
  "job_title": "...",
  "started_at": 1748519432.0,
  "ended_at": 1748520100.0,
  "responses": [
    {
      "question_num": 1,
      "type": "TECHNICAL",
      "topic": "Introduction",
      "question": "...",
      "answer": "...",
      "score": 8.0,
      "time_taken": 42
    }
  ],
  "proctoring_status": "PASSED",
  "flagged_count": 0,
  "webcam_log": [],
  "percentage": 80.0
}
```
