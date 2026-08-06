# Interview System

The interview system lets HR create tokenized candidate links, conduct AI-assisted interviews, collect proctoring signals, and store transcripts for reporting.

## Token Lifecycle

```text
Schedule confirmed -> token created -> candidate opens link -> interview completed -> token marked used
```

Tokens are stored in SQLite and are intended for one candidate interview. Regenerating interview links removes stale unused tokens for the current batch.

## Candidate Portal

Candidate links use the HTTPS server:

```text
https://<host>:<candidate-port>/candidate-interview/<token>
```

The default preferred candidate port is `5000`. Use `ARS_CANDIDATE_HOST=0.0.0.0` when the portal must be reachable from another device on the LAN.

Candidate-facing network access is route-limited. Token interview pages and candidate APIs remain public, but HR pages and HR APIs require a local desktop request or an authenticated HR session. If someone edits the URL to `/dashboard`, `/scheduling`, `/reports`, or an HR API, the request is blocked or redirected to login.

Candidate APIs are session-key protected and rate limited (default 30 requests/minute per IP). Opening a token creates an in-memory interview session with a private per-session key bound to the same client address and browser user agent. Sessions have an automatic TTL expiration (default 2 hours) and are pruned periodically to prevent memory accumulation. Answer submission, finish, browser flags, and webcam frame analysis are rejected if the request has only a guessed `session_id` or comes from another device on the same network.

## Interview Flow

1. Candidate opens the token link.
2. Server validates the token.
3. The app creates an interview session.
4. AI generates contextual questions.
5. Candidate answers in text or voice mode.
6. Answers are evaluated against the scoring rubric.
7. Proctoring signals are attached to the transcript.
8. Transcript is saved to `data/output/interviews/`.

## Voice Mode

| Component | Library | Notes |
|---|---|---|
| Text to speech | `pyttsx3` | Uses Windows voices |
| Speech to text | `Vosk` | Offline model under `models/` |
| Fallback | `SpeechRecognition` | May require internet depending on backend |

Install the offline model:

```bat
python scripts\setup_vosk.py
```

## Proctoring

The app records browser-level and webcam-level integrity signals.

| Signal | Source |
|---|---|
| Tab switch or focus loss | Browser |
| Full-screen exit | Browser |
| Copy/paste attempt | Browser |
| No face detected | Webcam analysis |
| Multiple faces detected | Webcam analysis |
| Face away or suspicious movement | Webcam analysis when available |

Proctoring results are not automatic rejection decisions. They are evidence for HR review.

## Transcript Output

Transcripts are JSON files containing candidate metadata, generated questions, answers, scores, timings, and proctoring events.

```json
{
  "candidate_name": "Jane Smith",
  "job_title": "Backend Developer",
  "ranking_score": 87.5,
  "responses": [],
  "proctoring_status": "PASSED",
  "flagged_count": 0,
  "percentage": 82.0
}
```

Reports are generated from these transcripts after interviews are complete.
