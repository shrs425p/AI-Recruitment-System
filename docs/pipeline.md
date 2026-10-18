# Pipeline

This document walks through the recruitment workflow step by step — from uploading resumes to candidate ranking, interviews, reports, and talent intelligence analytics.

---

## Overview

```
Upload Resumes (.pdf, .docx, images)
               │
               ▼
   Text Extraction (pypdf, python-docx, OCR)
               │
               ▼
     NLP Extraction (AI Entity Parser)
               │
               ▼
Candidate Ranking (Weights + Knockout Rules)
  ├── Recruiter Notes & Tags
  └── One-Click CSV / Excel Export
               │
               ▼
     Interview Scheduling & Calendar Sync
               │
               ▼
Proctored Interview (Configurable Length & Timer)
  ├── Role-Adaptive Blueprints
  └── Adaptive Probing for Shallow Answers
               │
               ▼
Evaluation Reports & Real-Time HR Notifications
  ├── Combined 40/60 Score Calculation
  └── Material Design 3 PDF Summary
               │
               ▼
Talent Intelligence & Analytics
  ├── Semantic Vector Talent Search
  ├── Candidate Comparison Matrix
  └── 6 Visual Recruitment Analytics Modules
```

Each stage produces structured output files that feed into subsequent stages. The pipeline is idempotent: already-processed records are preserved and not recomputed unnecessarily.

---

## Stage 1 — Upload Resumes

- **Where:** Sidebar → Upload
- **Input:** Microsoft Word (`.docx`), PDF (digital and scanned), PNG, JPG
- **Output:** Stored securely in `data/resumes/` (with optional AES-Fernet encryption at rest)

### Supported Formats & Whitelisting
| Format | Handler | Notes |
|---|---|---|
| `.docx` | `python-docx` | Native Microsoft Word document extraction. Extracts text paragraphs and tables cleanly. |
| `.pdf` | `pypdf` / OCR | Digital PDFs are read directly via stream parsing. Scanned PDFs fall back to Tesseract OCR. |
| `.png`, `.jpg`, `.jpeg` | Tesseract OCR | Image-only resumes read via bundled optical character recognition. |

The upload endpoint validates MIME types and file extensions against a strict whitelist. Dangerous file types (executables, scripts, HTML) are immediately rejected with HTTP 400. Duplicate filenames are preserved by appending incremental numeric suffixes.

---

## Stage 2 — Document Text Extraction

- **Where:** Automated background job after upload, or manually via the Dashboard
- **Module:** `src/pdf_to_txt.py`
- **Output:** Plain text files in `data/output/txt/`

### Processing Logic
1. **Word Documents:** Extracted directly using `extract_docx_text()`.
2. **Digital PDFs:** Extracted using `pypdf`. Encrypted storage is decrypted in-memory.
3. **Scanned Documents & Images:** If digital PDF extraction yields fewer than 800 characters or the file is an image, the file is routed to `Tesseract OCR`.
4. **Sanitization:** Null bytes are stripped, line endings are normalized (`\r\n` to `\n`), runs of blank lines are collapsed, and character encoding is converted to clean UTF-8.

---

## Stage 3 — NLP Entity Extraction

- **Where:** Sidebar → NLP → Run NLP Extraction
- **Module:** `src/nlp_extractor.py`
- **Input:** `.txt` files in `data/output/txt/`
- **Output:** `*_nlp.json` and `*_nlp.txt` in `data/output/nlp/`

### Extracted Entities
The AI model parses the unstructured text and extracts structured candidate profiles:
- `personal_info`: Full name, email address, phone number, location, portfolio/GitHub URLs.
- `domain`: Professional domain (Software Engineering, Data Science, DevOps, Marketing, etc.).
- `total_experience_years`: Numeric total years of relevant professional experience.
- `skills`: Categorized into technical skills, tools/technologies, domain-specific skills, and soft skills.
- `education`: List of degrees, institutions, graduation years, and fields of study.
- `work_experience`: Job titles, employers, dates, and core responsibilities.
- `certifications`: Industry certifications and issuing organizations.

---

## Stage 4 — Candidate Ranking & Shortlisting

- **Where:** Sidebar → Ranking
- **Module:** `src/ranking_engine.py`
- **Input:** Job Description text and `data/output/nlp/*_nlp.json`
- **Output:** `data/output/ranking/ranking_scores_*.json` and leaderboard text

### Weight Customization & Auto-Balancing
Scoring uses five criteria. Recruiters can customize weights or choose presets (Balanced, Technical Heavy, Experience Focused). If custom weights do not sum to 100, the system automatically normalizes them proportionally:
- `skills_match` (default: 35%)
- `experience_years` (default: 20%)
- `domain_match` (default: 20%)
- `education` (default: 15%)
- `certifications` (default: 10%)

### Knockout Disqualification Criteria
Recruiters can enforce mandatory prerequisites that disqualify candidates before AI scoring:
- **Minimum Experience:** Automatically scores 0 if verified experience is below threshold.
- **Mandatory Skills:** Candidate must possess all mandatory required skills.
- **Required Certifications:** Must possess specific professional licenses or certifications.

### Recruiter Notes, Tags & CSV Export
- **Notes & Tags:** Recruiters can attach notes (e.g. *"Strong distributed systems background"*) and status tags (e.g. *"Shortlisted"*, *"Review Later"*) directly on candidate rows. These persist in the SQLite database.
- **One-Click CSV Export:** The `/api/ranking/export/csv` endpoint generates an RFC 4180 compliant spreadsheet containing candidate rank, name, email, scores, strengths, and recommendations for ATS sharing.

---

## Stage 5 — Interview Scheduling

- **Where:** Sidebar → Scheduling
- **Module:** `src/scheduling.py`
- **Input:** Ranked candidates and candidate preferences
- **Output:** Slot allocations, `.ics` files, and optional Google Calendar invites

### Functionality
- Automatically shortlists the Top-N ranked candidates.
- Generates 3 prospective interview time slots per candidate.
- Generates standard `.ics` calendar invitation attachments.
- Integrates with Google Calendar API when configured.
- Dispatches SMTP interview invitation emails with dynamic placeholder replacement (`{candidate_name}`, `{job_title}`, `{interview_link}`).

---

## Stage 6 — Proctored Candidate Interview

- **Where:** Standalone Candidate Portal (`https://<host-ip>:5000`)
- **Modules:** `app/routes/interview.py`, `src/interview_bot.py`, `src/webcam_proctor.py`
- **Access:** Candidate enters via one-time cryptographically random UUID token

### Configurable Interview Parameters (Settings)
Recruiters can customize interview session parameters in Settings:
- **Technical Questions Count:** Configurable (e.g. 3 to 10 questions).
- **Behavioral Questions Count:** Configurable (e.g. 1 to 5 STAR questions).
- **Per-Question Time Limit:** Configurable (e.g. 60s, 90s, 120s, 180s).

### Adaptive Question Generation & Probing
- **Role-Adaptive Blueprints:** The engine checks `is_tech_role` to branch between software/engineering topics and domain-specific non-technical competencies.
- **Adaptive Probing (`should_probe_further`):** When a candidate gives a shallow, vague, or high-level response, the bot dynamically interjects with a follow-up probe demanding implementation trade-offs or edge-case handling.

### Proctoring Integrity Checks
- **Face Tracking:** Background thread monitors webcam frames using MediaPipe with OpenCV Haar cascade fallback.
- **Violation Logging:** Tracks zero-face absences, multiple faces, window tab switches, copy-paste events, and prolonged response timeouts.
- **Anti-Tamper Timing:** The server calculates response duration based on its own high-resolution monotonic timer, rejecting client-side timing manipulation.

---

## Stage 7 — Evaluation Reports & Real-Time HR Notifications

- **Where:** Sidebar → Reports
- **Module:** `src/report_generator.py`
- **Input:** Resume fit scores and completed interview transcripts
- **Output:** Comprehensive PDF report in `data/output/reports/`

### Combined Fit Score
The overall score combines resume suitability with live interview performance:
$$\text{Final Score} = (\text{Resume Fit} \times 0.40) + (\text{Interview Score} \times 0.60)$$

### Real-Time HR Notification Event
When a candidate completes their interview on `https://<host-ip>:5000`, the system automatically:
1. Emits a desktop pop-up notification on the HR manager's workstation: *"Jane Doe has completed the interview for Senior Python Developer. Report is ready."*
2. Records an entry in the `hr_notifications` SQLite table.
3. Updates the real-time notification badge and drawer in the HR web interface.

---

## Stage 8 — Talent Intelligence & Analytics

- **Where:** Sidebar → Intelligence
- **Module:** `src/talent_intelligence.py`

Provides post-interview analytics and talent pool analysis:
- **Semantic Vector Search:** Natural language search across the talent pool.
- **Candidate Comparison Matrix:** Side-by-side technical trade-off evaluation and executive brief.
- **Personalized Feedback Letters:** Constructive feedback generation with strengths and study topics.
- **Six Visual Analytics Modules:**
  1. Skill Supply vs. Demand Gap Analytics
  2. Experience vs. Score Quadrant Matrix
  3. Interview Question Difficulty Breakdown
  4. Proctoring Integrity & Risk Distribution
  5. Hiring Velocity & Bottleneck Tracker
  6. Education & Domain Talent Mix
