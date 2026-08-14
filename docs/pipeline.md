# Pipeline

This document walks through the full recruitment workflow step by step — from uploading resumes to generating interview reports.

---

## Overview

```
Upload Resumes
     │
     ▼
Text Extraction (OCR)
     │
     ▼
NLP Extraction (AI)
     │
     ▼
Candidate Ranking (AI)
     │
     ▼
Scheduling
     │
     ▼
Interview
     │
     ▼
Reports
```

Each stage produces output files that feed into the next stage. You can stop and resume at any stage — the system never reprocesses files that are already done.

---

## Stage 1 — Upload Resumes

**Where:** Sidebar → Upload  
**Input:** PDF, PNG, JPG files  
**Output:** Files saved to `data/resumes/`

### What Happens
- Files are uploaded through the web UI
- Each file is validated (type + size — max 25 MB by default)
- Saved to the resumes folder under the original filename
- Duplicate filenames are not overwritten — rename before re-uploading if needed

### Supported Formats
| Format | Notes |
|---|---|
| `.pdf` | Works for both digital PDFs (text-based) and scanned PDFs (image-only) |
| `.png`, `.jpg`, `.jpeg` | Resume photos or scanned images — processed via OCR |

---

## Stage 2 — Text Extraction

**Where:** Runs automatically after upload, or manually from the NLP page  
**Module:** `src/pdf_to_txt.py`  
**Input:** Files in `data/resumes/`  
**Output:** `.txt` files in `data/output/txt/`

### How It Decides Between Direct Extraction and OCR

1. PyMuPDF tries to extract embedded text from the PDF directly (fast — milliseconds)
2. If the extracted text is **fewer than 800 characters**, the PDF is treated as a scanned document
3. For scanned PDFs: PyMuPDF renders each page to a 300 DPI image, then Tesseract OCR reads it
4. For image files (PNG/JPG): Tesseract OCR reads them directly

### Text Cleaning
After extraction, the text is cleaned:
- Null bytes removed
- Windows line endings normalised (`\r\n` → `\n`)
- Runs of 3+ blank lines collapsed to one
- Multiple spaces/tabs collapsed to single space

### Output
One `.txt` file per resume, saved as `{original_filename}.txt`. Already-processed files are skipped on re-runs.

---

## Stage 3 — NLP Extraction

**Where:** Sidebar → NLP → Run NLP Extraction  
**Module:** `src/nlp_extractor.py`  
**Input:** `.txt` files in `data/output/txt/`  
**Output:** `*_nlp.json` + `*_nlp.txt` in `data/output/nlp/`

### What the AI Extracts

The AI is given the full resume text and asked to return a structured JSON with:

| Field | Description |
|---|---|
| `personal_info` | Name, email, phone, location, LinkedIn, GitHub/portfolio |
| `domain` | Detected industry (IT, Finance, Medical, Legal, etc.) |
| `summary` | Professional summary |
| `total_experience_years` | Total years of relevant work experience |
| `skills.technical_skills` | Programming languages, frameworks, etc. |
| `skills.tools_and_technologies` | Software tools, platforms |
| `skills.soft_skills` | Communication, leadership, etc. |
| `skills.domain_specific_skills` | Industry-specific skills |
| `skills.languages_known` | Spoken/written languages |
| `education` | Degree, field, institution, year, grade |
| `work_experience` | Job titles, companies, dates, responsibilities, achievements |
| `projects` | Title, description, technologies, outcomes |
| `certifications` | Name, issuer, year |
| `awards_and_achievements` | Awards, honours |
| `publications_or_research` | Papers, research work |
| `candidate_strength_summary` | AI-written summary of strengths |

### Notes
- Temperature is set to `0.0` for deterministic output
- Token budget: 4096 — enough for detailed multi-page resumes
- If the AI cannot find the candidate's name, the filename is used as the identifier
- Files are written atomically (temp file first, renamed on success) to prevent partial outputs
- Already-processed files are skipped — running NLP again is safe

### Output Files
- `{name}_nlp.json` — machine-readable, used by the ranking engine
- `{name}_nlp.txt` — human-readable summary for quick review

---

## Stage 4 — Candidate Ranking

**Where:** Sidebar → Ranking → Enter JD → Run Ranking  
**Module:** `src/ranking_engine.py`  
**Input:** `*_nlp.json` files + Job Description text  
**Output:** `ranking_scores_<timestamp>.json` + `leaderboard_<timestamp>.json`

### Step 1 — Parse the Job Description
The AI reads the JD and extracts:
- Job title and domain
- Required experience years
- Required and preferred skills
- Required education level
- Required certifications
- Job summary

### Step 2 — Score Each Candidate

Each candidate is scored on 5 criteria (100 points total):

| Criterion | Max Points | What It Measures |
|---|---|---|
| `domain_match` | 20 | Does the candidate's industry match the JD domain? |
| `skills_match` | 35 | How many required skills does the candidate have? |
| `experience_years` | 20 | Years of relevant experience |
| `education` | 15 | Degree level (PhD > Masters > Bachelors > Diploma) |
| `certifications` | 10 | Number of relevant certifications |

#### Scoring Rubrics (enforced strictly)

**domain_match (20 pts)**
- 20 pts — Direct domain match
- 13 pts — Related domain (e.g. Software Dev for an AI role)
- 6 pts — Adjacent domain (STEM for a tech role)
- 0 pts — Completely unrelated

**skills_match (35 pts)**
- 35 pts — 80%+ of required skills present
- 24 pts — 50–80% present
- 15 pts — 25–50% present
- 7 pts — <25% present
- 0 pts — No relevant skills
- Related skills get partial credit (e.g. PyTorch counts for TensorFlow requirement)

**experience_years (20 pts)**
- 20 pts — 5+ years
- 18 pts — 2–5 years
- 14 pts — 0–2 years
- 10 pts — Fresher / not mentioned (never 0 for freshers)
- 0 pts — Clearly irrelevant experience only

**education (15 pts)**
- 15 pts — PhD / Doctorate
- 12 pts — Masters / M.Tech / MBA
- 9 pts — Bachelors / B.Tech / B.E.
- 5 pts — Diploma / Associate
- 0 pts — No education info found

**certifications (10 pts)**
- 10 pts — 3+ relevant certifications
- 6 pts — 1–2 relevant certifications
- 0 pts — No certifications

### Step 3 — Generate Output
For each candidate, the AI also produces:
- `overall_verdict` — a one-line assessment
- `strengths` — list of standout qualities
- `gaps` — list of missing requirements
- `hire_recommendation` — Strongly Recommend / Recommend / Maybe / Not Recommended

Candidates are sorted by total score, highest first.

### Deduplication
Before scoring, candidates are deduplicated by a hash of `name + domain + top 5 skills`. If the same resume was uploaded twice, only one copy is scored.

### Parallelism
Up to 5 candidates are scored simultaneously using `ThreadPoolExecutor`. You can adjust this in `src/ranking_engine.py` (`MAX_WORKERS`).

---

## Stage 5 — Scheduling

**Where:** Sidebar → Scheduling  
**Module:** `src/scheduling.py` + `src/google_calendar.py` + `src/email_sender.py`  
**Input:** Latest `ranking_scores_*.json` + HR availability  
**Output:** `schedule_<timestamp>.json` + `.ics` files per candidate

### What Happens
1. The top 10 candidates (configurable) from the latest ranking are selected
2. HR enters their available time slots
3. Each candidate is assigned 3 slot options
4. A `.ics` calendar invite is generated for each candidate (UUID event ID, 60-minute duration)
5. An interview token (UUID) is generated per candidate and stored
6. If email is configured, scheduling emails are sent with the slot options and interview link

### Interview Tokens
Each candidate gets a unique URL like:
```
https://<your-ip>:5000/candidate-interview/<token>
```
This URL is valid until the interview is completed or the session is closed.

### Google Calendar Integration
If Google Calendar credentials are configured in Settings, the system can:
- Create calendar events in HR's Google Calendar
- Send Google Calendar invites to candidates via the Google API

---

## Stage 6 — Interview

**Where:** Candidate accesses their unique URL; HR monitors from Sidebar → Interview  
**Modules:** `src/interview_bot.py`, `src/webcam_proctor.py`, `src/voice_interview.py`  
**Input:** Interview token, candidate NLP JSON  
**Output:** `interview_<name>_<timestamp>.json`

See [Interview System](interview-system.md) for full details.

### Quick Summary
- 8 questions per candidate (5 technical + 3 behavioral)
- Questions are personalised based on the candidate's actual skills and experience
- Candidate can answer via text or voice (Vosk STT)
- Webcam proctoring runs in the background throughout
- Each answer is evaluated by AI (score + feedback)
- Session transcript saved on completion

---

## Stage 7 — Reports

**Where:** Sidebar → Reports  
**Module:** `src/report_generator.py`  
**Input:** Interview transcript JSON  
**Output:** PDF report in `data/output/reports/`

### Report Contents
- Candidate profile summary (name, domain, experience, education)
- Per-question scores and AI feedback
- Overall interview score and recommendation
- Proctoring summary (total flags, face detection events, tab switches, copy-paste violations)
- Full Q&A transcript

Reports are generated using `fpdf2` and saved as PDF files.
