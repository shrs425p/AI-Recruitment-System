# Pipeline Guide

The recruitment pipeline consists of six sequential steps. Each step can be run individually (manual mode) or chained automatically (auto mode). This document explains each step, its inputs and outputs, and the controls available in the UI.

---

## Overview

| Step | Name | Input | Output | Engine |
|---|---|---|---|---|
| 1 | Upload | PDF / image files | `data/resumes/` | Flask upload handler |
| 2 | PDF to Text | `data/resumes/` | `data/output/txt/` | Tesseract OCR / PyMuPDF |
| 3 | NLP Extract | `data/output/txt/` | `data/output/nlp/` | LLM prompt via Ollama or cloud |
| 4 | AI Rank | `data/output/nlp/` + job description | `data/output/ranking/` | LLM scoring engine |
| 5 | Schedule | Ranking results + HR calendar slots | `data/output/scheduling/` | Slot assignment + ICS |
| 6 | Interview | Schedule + candidate tokens | `data/output/interviews/` | Interview bot + report |

---

## Step 1 — Upload

**Route:** `POST /api/upload`

HR uploads one or more PDF, PNG, JPG, or JPEG resume files. Each file is saved to `data/resumes/` with its original filename preserved.

**Supported formats:**
- PDF (digital text or scanned image)
- PNG, JPG, JPEG (image resumes)

**Limits:** No hard limit is enforced in code. Recommended: batch uploads of up to 200 files at a time for stable performance.

**Notes:**
- Duplicate filenames are silently overwritten.
- Only uploaded files are processed in subsequent steps. Already-existing TXT files are skipped by the PDF-to-text watcher (idempotent).

---

## Step 2 — PDF to Text

**Route:** `POST /api/run-pdf`  
**Engine:** `src/pdf_to_txt.py`

Converts each resume in `data/resumes/` to a plain `.txt` file in `data/output/txt/`.

### Conversion Logic

```
For each file in data/resumes/:
    if output/txt/<stem>.txt already exists:
        skip (idempotent)
    elif file is PDF:
        try direct text extraction (PyMuPDF)
        if extracted text length < 800 characters:
            fall back to OCR (Tesseract at 300 dpi)
    elif file is PNG / JPG:
        OCR with Tesseract
    clean text (normalise whitespace, remove null bytes)
    write to output/txt/<stem>.txt
```

**Tesseract binary:** `models/Tesseract-OCR/tesseract.exe` (bundled, no system install required)

**Output files:** One `.txt` file per resume, UTF-8 encoded.

---

## Step 3 — NLP Extraction

**Route:** `POST /api/run-nlp`  
**Engine:** `src/nlp_extractor.py`

Sends each `.txt` resume to the configured AI model and extracts structured candidate data as JSON.

### Extracted Fields

```json
{
  "personal_info": { "name", "email", "phone", "location", "linkedin", "portfolio_or_github" },
  "domain": "",
  "summary": "",
  "total_experience_years": null,
  "skills": { "technical_skills", "tools_and_technologies", "soft_skills", "domain_specific_skills", "languages_known" },
  "education": [ { "degree", "field_of_study", "institution", "year_of_completion", "grade_or_cgpa" } ],
  "work_experience": [ { "job_title", "company", "start_date", "end_date", "duration", "responsibilities", "achievements" } ],
  "projects": [ { "title", "description", "technologies_used", "outcome" } ],
  "certifications": [ { "name", "issuer", "year" } ],
  "awards_and_achievements": [],
  "publications_or_research": [],
  "volunteer_or_extracurricular": [],
  "languages": [],
  "candidate_strength_summary": ""
}
```

**Output files:**
- `data/output/nlp/<stem>_nlp.json` — machine-readable structured data
- `data/output/nlp/<stem>_nlp.txt` — human-readable summary

**Idempotency:** Files already having a `_nlp.json` counterpart are skipped.

**Fallback:** If the AI cannot detect the candidate name, the filename stem is used as the identifier.

---

## Step 4 — AI Ranking

**Route:** `POST /api/run-ranking`  
**Engine:** `src/ranking_engine.py`

Scores each candidate against a job description provided by HR, producing a ranked list with scores from 0–100.

### Scoring Criteria

| Criterion | Weight | Description |
|---|---|---|
| Skills match | 30% | Technical skills alignment with JD requirements |
| Experience | 25% | Years of experience and relevance |
| Education | 15% | Degree field and institution calibre |
| Domain fit | 20% | Industry/domain match |
| Achievements | 10% | Notable certifications, projects, awards |

**Output files:**
- `data/output/ranking/ranking_scores_<timestamp>.json` — full ranked list with scores and reasoning per candidate

The latest ranking file is automatically loaded on the Scheduling page.

---

## Step 5 — Scheduling

**Route:** `POST /api/schedule`  
**Engine:** `src/scheduling.py`

Assigns interview time slots to the top-ranked candidates. HR provides available slots; the engine distributes them across candidates and generates ICS calendar files.

### Slot Assignment

- Top 10 candidates by score are selected by default.
- Each candidate is offered up to 3 time slot options (`SLOTS_TO_OFFER`).
- The first available slot is auto-confirmed.
- HR can override any slot from the Scheduling UI.

### Google Calendar Integration

If Google Calendar is authenticated, interview events are created automatically. See [Google Calendar](google-calendar.md).

**Output files:**
- `data/output/scheduling/schedule_<timestamp>.json` — full schedule with status per candidate
- `data/output/scheduling/<candidate>_<timestamp>.ics` — individual ICS files for calendar import

---

## Step 6 — Interview

**Route:** `POST /api/generate-interview-links`  
**Engine:** `src/interview_bot.py`

Generates one-time interview tokens for each confirmed candidate. Candidates receive a unique URL and complete the interview in their browser.

### Interview Flow

```
HR generates tokens
    |
    v
Candidate opens interview URL (https://<ip>:5000/candidate-interview/<token>)
    |
    v
System generates personalised questions (technical + behavioural) via AI
    |
    v
Candidate answers each question (text or voice)
    |
    v
Each answer is evaluated in real time (AI scoring 0-10 per question)
    |
    v
Proctoring runs concurrently (webcam face detection, browser tab flags)
    |
    v
Session ends -> transcript saved to data/output/interviews/
    |
    v
Report generated to data/output/reports/
```

### Question Structure

| Type | Count | Scoring Dimensions |
|---|---|---|
| Technical | 5 | Relevance (0-3), Depth (0-3), Clarity (0-2), Correctness (0-2) |
| Behavioural | 3 | Same dimensions, STAR-format expected |

### Token Lifecycle

Tokens are single-use. Once a candidate completes the interview, the token is marked `used = 1` in the database and cannot be reused. Regenerating tokens invalidates all existing unused tokens for that batch.

---

## Automatic (Pipeline) Mode

The Dashboard page provides a **Run All** control that executes Steps 2 through 4 sequentially. Step 5 (Scheduling) and Step 6 (Interview) are always manual — they require HR input (slot selection and token dispatch) before proceeding.

### Concurrency Safety

Adding new resumes while a pipeline run is in progress is safe only if the new files have not yet been processed. The NLP and PDF-to-text stages are idempotent — already-processed files are skipped. However, adding new files mid-ranking or mid-scheduling will result in those candidates being excluded from the current run. Always complete the current run before uploading a new batch.

### Recommended Workflow

```
1. Upload all resumes for the current batch.
2. Run Steps 2, 3, and 4 (or use Run All).
3. Review ranked results.
4. Enter the job description and available slots.
5. Run Step 5 (Schedule).
6. Dispatch interview tokens to candidates.
7. Monitor interviews from the Interview page.
8. Download reports after all candidates complete.
```
