# Customization

This document lists all the hardcoded parameters in the codebase that can be changed to tune the system's behaviour, along with where to find them and what effect they have.

---

## Ranking Parameters

**File:** `src/ranking_engine.py`

### Scoring Weights

```python
WEIGHTS = {
    "domain_match":      20,   # Max 20 pts — domain/industry alignment
    "skills_match":      35,   # Max 35 pts — required skills coverage
    "experience_years":  20,   # Max 20 pts — years of relevant experience
    "education":         15,   # Max 15 pts — degree level
    "certifications":    10,   # Max 10 pts — number of relevant certifications
}
```

The five values must add up to 100. Change them to shift what the ranking prioritises.

**Example — prioritise experience over skills:**
```python
WEIGHTS = {
    "domain_match":      20,
    "skills_match":      25,
    "experience_years":  30,
    "education":         15,
    "certifications":    10,
}
```

**Example — ignore certifications, boost skills:**
```python
WEIGHTS = {
    "domain_match":      20,
    "skills_match":      45,
    "experience_years":  20,
    "education":         15,
    "certifications":    0,
}
```

### Parallel Workers

```python
MAX_WORKERS = 5   # How many candidates to score simultaneously
```

Increase this if you have fast AI providers and many candidates. Decrease it if you're hitting rate limits or seeing timeouts.

---

## NLP Extraction Parameters

**File:** `src/nlp_extractor.py`

### Watch Interval

```python
WATCH_INTERVAL_SECONDS = 5   # How often the watcher polls for new .txt files
```

The NLP watcher checks the `output/txt/` folder every 5 seconds for new files. You can lower this if you want faster response, or raise it to reduce polling overhead.

### AI Token Budget

Inside `extract_with_ai()`:
```python
raw = call_ollama(system, build_prompt(resume_text), temperature=0.0, num_predict=4096)
```
`num_predict=4096` — this is the maximum number of tokens the AI can use for the response. Very detailed resumes may need more. Raise it to `6144` or `8192` if the AI is truncating long resumes.

---

## PDF Extraction Parameters

**File:** `src/pdf_to_txt.py`

### Digital Text Threshold

```python
MIN_DIGITAL_TEXT_LENGTH = 800
```

If a PDF's direct text extraction produces fewer than 800 characters, it is treated as a scanned PDF and OCR is used. 

- Lower this (e.g. `200`) if scanned PDFs with small amounts of text are being missed
- Raise this (e.g. `1500`) if digital PDFs with sparse formatting are being OCR'd unnecessarily

---

## Interview Parameters

**File:** `src/interview_bot.py`

### Number of Questions

```python
TECHNICAL_QUESTIONS  = 5   # Technical questions per interview
BEHAVIORAL_QUESTIONS = 3   # Behavioral (STAR format) questions per interview
```

Total interview = 8 questions by default. You can change these to make interviews shorter or longer.

**Example — shorter interview (3 technical + 2 behavioral):**
```python
TECHNICAL_QUESTIONS  = 3
BEHAVIORAL_QUESTIONS = 2
```

### Answer Time Limit

```python
ANSWER_TIME_LIMIT = 120   # Seconds before a flag is raised for slow answers
```

If a candidate takes more than 120 seconds to answer, a proctoring flag is recorded. The interview does not stop — this is just flagged in the report.

---

## Proctoring Parameters

**File:** `src/webcam_proctor.py`

### Check Frequency

```python
CHECK_INTERVAL = 2.0   # Seconds between face detection checks
```

Face detection runs every 2 seconds. Lower this for more frequent checks (more CPU usage). Raise it to reduce CPU load.

### No-Face Threshold

```python
NO_FACE_THRESHOLD = 3   # Consecutive "no face" checks before flagging
```

With `CHECK_INTERVAL=2.0` and `NO_FACE_THRESHOLD=3`, a flag is raised if the candidate's face is absent for 6 seconds continuously.

Raise this to be more lenient (candidate looking away briefly). Lower it to flag faster.

### Multiple Faces Threshold

```python
MULTI_FACE_THRESHOLD = 2   # Consecutive "multiple faces" checks before flagging
```

Two consecutive detections of multiple faces (4 seconds) trigger a flag. Raise this to reduce false positives from reflections or background movement.

### Frame Resolution

```python
FRAME_WIDTH  = 320
FRAME_HEIGHT = 240
```

Larger values give better face detection accuracy but use more bandwidth for streaming.

### JPEG Streaming Quality

```python
JPEG_QUALITY = 60   # 0-100; lower = smaller frame size
```

Lower values reduce bandwidth but make the live feed look blurry. 60 is a reasonable balance.

---

## Scheduling Parameters

**File:** `src/scheduling.py`

### Shortlist Size

```python
TOP_N_CANDIDATES = 10   # How many top candidates to invite for interviews
```

Lower this for a tighter shortlist. The candidates are already sorted by score, so this just picks the top N.

### Slots Per Candidate

```python
SLOTS_TO_OFFER = 3   # Number of time options offered to each candidate
```

More options = higher chance candidates can confirm. Fewer = simpler schedule for HR.

### Interview Duration

```python
INTERVIEW_MINUTES = 60   # Duration of each interview event in .ics files
```

This affects the `.ics` calendar invite duration only. The actual interview session has no time limit.

---

## Google Calendar Parameters

**File:** `src/google_calendar.py`

```python
INTERVIEW_DURATION  = 60      # Event duration in calendar (minutes)
TIMEZONE            = 'Asia/Kolkata'   # Change to your local timezone (IANA string)
LOOKAHEAD_DAYS      = 14      # How many days ahead to scan for free slots
WORK_HOUR_START     = 9       # Work day start (24-hour)
WORK_HOUR_END       = 18      # Work day end (24-hour)
SLOT_INTERVAL_MINS  = 60      # Slot granularity (minutes)
```

**Common timezone strings:**
- `'Asia/Kolkata'` — India (IST)
- `'America/New_York'` — US Eastern
- `'America/Los_Angeles'` — US Pacific
- `'Europe/London'` — UK
- `'Europe/Berlin'` — Central Europe
- `'Asia/Dubai'` — UAE
- `'Asia/Singapore'` — Singapore/Malaysia

---

## Email Parameters

**File:** `src/email_sender.py` / Settings UI

The email content is mostly customisable through the Settings UI (subject template, body template). The SMTP timeout is hardcoded at:
```python
timeout=30   # seconds to wait for SMTP connection
```

---

## AI Retry Parameters

Set in the Settings UI (also in `config/__init__.py` defaults):

```python
AI_RETRY_ATTEMPTS = 3   # Number of attempts before giving up on an AI call
AI_RETRY_BACKOFF  = 2   # Seconds multiplier between retries (2, 4, 6... seconds)
```

Increase `AI_RETRY_ATTEMPTS` if you're on a slow or flaky connection. Decrease `AI_RETRY_BACKOFF` if you want faster retries.

---

## Server Parameters

Set via environment variables (see [Getting Started](getting-started.md)):

| Variable | Default | Description |
|---|---|---|
| `ARS_DESKTOP_PORT` | `5001` | HR UI server port |
| `ARS_CANDIDATE_PORT` | `5000` | Candidate portal port |
| `ARS_SERVER_THREADS` | `8` | Number of Waitress threads |
| `ARS_MAX_UPLOAD_BYTES` | `26214400` (25 MB) | Max upload file size |
