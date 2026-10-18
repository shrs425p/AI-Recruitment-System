# Customization

This document details how to customize system behavior, ranking rubrics, interview lengths, and proctoring parameters — both via the Settings UI and in the code.

---

## 1. UI-Configurable Settings (No Code Changes Needed)

The following parameters can be adjusted directly from the **Settings** tab in the desktop application:

### Interview Length & Time Limits
| Setting | Default | Recommended Options | Description |
|---|---|---|---|
| **Technical Questions** | `5` | 3 to 10 | Number of technical questions asked per candidate. |
| **Behavioral Questions** | `3` | 1 to 5 | Number of STAR-format behavioral questions asked. |
| **Per-Question Time Limit** | `120s` | 60s, 90s, 120s, 180s | Time window allowed per answer before raising a response delay flag. |

### Candidate Ranking Weights & Presets
Recruiters can modify the 5 scoring weights in the Ranking tab. If weights do not add up to 100, the system automatically normalizes them proportionally:
- `skills_match` (Default: 35%)
- `experience_years` (Default: 20%)
- `domain_match` (Default: 20%)
- `education` (Default: 15%)
- `certifications` (Default: 10%)

### Knockout Criteria
Prerequisites that disqualify candidates before AI scoring takes place:
- **Minimum Experience:** Automatically disqualifies candidates with fewer verified years.
- **Mandatory Required Skills:** Disqualifies candidates missing any required technology.
- **Required Certifications:** Disqualifies candidates missing mandatory certifications.

---

## 2. Code-Level Parameters

For advanced modifications, the following constants can be configured in the codebase:

### Document Extraction (`src/pdf_to_txt.py`)

```python
MIN_DIGITAL_TEXT_LENGTH = 800
```
- If a PDF's stream extraction produces fewer than 800 characters, it is treated as a scanned document and routed to Tesseract OCR.
- Lower this (e.g. `300`) if short digital resumes are unnecessarily triggering OCR.
- Raise this (e.g. `1200`) if scanned PDFs with sparse header text are skipping OCR.

### NLP Extraction (`src/nlp_extractor.py`)

```python
WATCH_INTERVAL_SECONDS = 5
```
- Polling frequency in seconds for the background folder watcher that checks for new `.txt` files.

### Webcam Proctoring (`src/webcam_proctor.py`)

```python
CHECK_INTERVAL       = 2.0   # Frequency in seconds between background face checks
NO_FACE_THRESHOLD    = 3     # Consecutive missing face checks before flagging (6 seconds)
MULTI_FACE_THRESHOLD = 2     # Consecutive multi-face detections before flagging (4 seconds)
FRAME_WIDTH          = 320   # Video capture frame width
FRAME_HEIGHT         = 240   # Video capture frame height
JPEG_QUALITY         = 60    # Frame compression quality (0-100)
```

- **LENIENT SETUP:** Raise `NO_FACE_THRESHOLD = 5` to allow candidates to look away or take notes without flagging.
- **STRICT SETUP:** Lower `NO_FACE_THRESHOLD = 2` to flag face absence within 4 seconds.

### Scheduling (`src/scheduling.py`)

```python
TOP_N_CANDIDATES  = 10   # Default number of shortlisted candidates to invite
SLOTS_TO_OFFER    = 3    # Number of proposed interview time slots per candidate
INTERVIEW_MINUTES = 60   # Duration in minutes set in generated .ics calendar events
```

### Google Calendar Sync (`src/google_calendar.py`)

```python
INTERVIEW_DURATION = 60
TIMEZONE           = 'Asia/Kolkata'  # Local IANA timezone string
LOOKAHEAD_DAYS     = 14              # Days ahead to scan for calendar availability
WORK_HOUR_START    = 9               # Daily schedule start (24h)
WORK_HOUR_END      = 18              # Daily schedule end (24h)
```

---

## 3. Environment Variables

| Variable | Default | Description |
|---|---|---|
| `FLASK_PORT` | `5001` | Local HR administrative WSGI port. |
| `CANDIDATE_PORT` | `5000` | Remote candidate portal HTTPS port. |
| `ARS_MAX_UPLOAD_BYTES` | `26214400` (25 MB) | Maximum permitted resume file upload size. |
| `ARS_SERVER_THREADS` | `8` | Waitress WSGI server worker thread count. |
