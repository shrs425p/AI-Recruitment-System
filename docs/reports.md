# Reports & Evaluations

This document covers how final candidate evaluation reports are generated, the combined scoring model, PDF export formatting, and real-time completion notifications.

---

## Overview

Final candidate reports aggregate the entire candidate lifecycle into an evaluation document:
1. **Resume Fit Assessment (40%):** Skills match, years of experience, domain alignment, education, and certifications.
2. **Live Interview Performance (60%):** Technical accuracy, conceptual depth, communication clarity, problem-solving rubrics, and proctoring integrity logs.
3. **Recruiter Annotations:** Internal notes and status tags saved by hiring managers.

Reports are saved in both machine-readable JSON format and downloadable monochrome PDF format in `data/output/reports/`.

---

## 1. Combined Scoring Formula

The overall score is computed as a weighted composite of resume suitability and live interview demonstration:

$$\text{Final Score} = (\text{Resume Fit Score} \times 0.40) + (\text{Interview Score} \times 0.60)$$

Where:
- $\text{Resume Fit Score}$: 0 to 100 points calculated by the ranking engine.
- $\text{Interview Score}$: Percentage score calculated from total points achieved across all interview questions divided by maximum possible points.

### Recommendation Tiers
| Final Score Range | Recommendation Verdict |
|---|---|
| **85% — 100%** | Strongly Recommend |
| **70% — 84%** | Recommend |
| **55% — 69%** | Consider with Reservations |
| **Below 55%** | Do Not Recommend |

---

## 2. Report Content & Layout

Reports follow a Material Design 3 monochrome typographic structure designed for executive distribution:

### Header & Metadata
- Candidate Name, Email, Phone, and Portfolio URLs.
- Position Title and Evaluated Domain.
- Date of Evaluation and Unique Candidate ID.

### Executive Summary & Scores Card
- Final Composite Score (out of 100).
- Component Breakdown: Resume Fit (40%) vs Interview Performance (60%).
- Final Recommendation Verdict.

### Candidate Annotations
- Internal Recruiter Notes attached to the candidate record.
- Current Status Tags (e.g. *"Shortlisted"*, *"Team Review"*, *"Follow-Up"*).

### Rubric Breakdown & Interview Transcripts
For each interview question:
- Question Number, Type (Technical / Behavioral), and Topic.
- Question text and candidate's verbatim answer.
- 4-Part Rubric Scores: Relevance (3 pts), Depth (3 pts), Clarity (2 pts), Correctness (2 pts).
- Constructive feedback, identified strengths, and technical gaps.
- Response time in seconds and any adaptive follow-up probes.

### Proctoring & Integrity Summary
- Total Integrity Flags Count.
- Proctoring Status Tier: **Clean Session**, **Low Warning**, or **High Risk**.
- Itemized violation log with timestamps: Tab Switches, Face Absence, Multiple Faces, and Instant Paste flags.

---

## 3. PDF Generation Architecture

Reports are rendered using `fpdf2`:
- **Typography:** Uses clean system fonts (Helvetica/Arial) with Latin-1 character sanitization to prevent PDF encoding crashes.
- **Atomic File Saving:** Reports are written to temporary files and atomically moved to `data/output/reports/report_<candidate_name>.pdf`.
- **Download Route:** Authenticated recruiters download reports directly via `/api/report-pdf/<filename>`.

---

## 4. Real-Time HR Notifications

When a candidate finishes answering their final interview question on the candidate portal, the system automatically emits a real-time notification:

1. **Desktop Pop-Up Notification:** An OS desktop notification appears on the HR manager's workstation:
   > *"Candidate Completed: Jane Doe has completed the interview for Senior Python Developer. Report is ready."*
2. **Persistent Database Storage:** The event is logged to the `hr_notifications` table with an unread state (`is_read = 0`).
3. **UI Badge & Tray:** The navigation bar displays the unread counter badge. Clicking the notification icon opens a drawer listing recent completions.

### Notification Management API
- `GET /api/notifications` — Lists recent notifications.
- `GET /api/notifications/unread-count` — Returns current unread count for badge polling.
- `POST /api/notifications/<id>/read` — Marks a specific notification as read.
- `POST /api/notifications/read-all` — Marks all notifications as read.
