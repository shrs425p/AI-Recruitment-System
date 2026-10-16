# Reports

This document explains what the interview reports contain, how they are generated, and how to read them.

---

## What Is a Report?

After a candidate completes their interview, HR can generate a PDF report from the Reports page. The report combines:
- The candidate's NLP profile (skills, experience, education)
- Their interview performance (per-question scores and AI feedback)
- Proctoring summary (webcam violations, tab switches)
- An overall AI-generated HR assessment

Reports are useful for sharing candidate evaluations with the wider hiring team, keeping records, or comparing candidates after the interviews.

---

## Generating a Report

1. Go to **Sidebar → Reports**
2. Locate the candidate under completed interviews
3. Click **Generate Report** to run the AI HR evaluation
4. Click **Download PDF** (or **View Report**) to export the report

PDF reports are saved to `%LOCALAPPDATA%\AI Recruitment System\data\output\reports\` and can be viewed directly in the application or opened in any standard PDF reader.

---

## Report Structure (Material Design 3 Monochrome)

The PDF evaluation dossier is styled using a high-contrast Material Design 3 monochrome palette (off-black, slate gray, bordered containers, and white background) designed for clean printing and executive review.

### 1. Header & Candidate Overview
- Candidate full name and target job title
- Report timestamp and evaluation ID
- Prominent Combined Score badge (out of 100)
- AI Hire Recommendation badge (`Strongly Recommend`, `Recommend`, `Maybe`, `Not Recommended`)

### 2. Candidate Profile & Technical Summary
- Domain specialization and total years of professional experience
- Highest degree and education background
- Extracted technical skills and core tool competencies

### 3. AI HR Assessment & Executive Analysis
- **Overall Summary:** Concise synthesis of candidate performance across ranking and interview stages
- **Technical Assessment:** Evaluation of depth, domain grasp, and technical trade-offs
- **Behavioral Assessment:** Analysis of communication, problem-solving, and STAR-format responses
- **Key Strengths:** Bulleted list of candidate standout competencies
- **Key Gaps:** Bulleted list of growth areas or missing qualifications
- **Suggested Next Steps:** Recommended follow-up actions (e.g. system design round, code review, reference verification)

### 4. Proctoring & Integrity Summary
- Overall proctoring status (`CLEAN`, `SUSPICIOUS`, `FLAGGED`)
- Proctoring Risk Level (`Low`, `Medium`, `High`)
- Flag breakdown table:
  - Tab switches count
  - Copy-paste attempts count
  - Face absence occurrences
  - Multiple faces detected count
  - Total violation flags recorded

### 5. Detailed Question-by-Question Evaluation
Each question answered by the candidate is presented with:
- Question number, category badge (`Technical` or `Behavioral`), and difficulty level
- Question score (0 to 10 points) and response time in seconds
- Full prompt text asked during the interview
- 4-part evaluation rubric breakdown:
  - **Relevance:** Directness and alignment with the question prompt
  - **Depth:** Thoroughness, technical accuracy, and domain familiarity
  - **Clarity:** Structure, conciseness, and articulation
  - **Correctness:** Factual accuracy and problem-solving soundness
- Verbatim candidate response
- AI Evaluator Feedback detailing strengths, partial credit rationale, and gaps
- Proctor flags logged specifically during the question window (if any)

---

## How the AI Assessment Is Generated

The report generator (`src/report_generator.py`) sends the full interview transcript to the AI with a structured prompt asking for the assessment JSON. It uses:
- `temperature=0.0` — deterministic output
- `num_predict=4096` — enough tokens for detailed assessments

The AI is not given any identity information about the HR system — only the transcript and scores — to keep the assessment objective.

---

## Combined Score Calculation

The combined score visible in the report takes into account both the ranking stage score and the interview stage score. It is a weighted blend — the exact weighting is determined by the AI's overall assessment rather than a fixed formula, making it a holistic evaluation rather than a pure number.

---

## Risk Level

The risk level (`Low` / `Medium` / `High`) is assessed by the AI based on:

| Factor | Low Risk | Medium Risk | High Risk |
|---|---|---|---|
| Proctoring flags | 0–1 | 2–4 | 5+ |
| Interview score | >75% | 50–75% | <50% |
| Answer quality | Consistent, detailed | Inconsistent | Very short or off-topic |

This is the AI's judgment based on the full picture — it is not a rigid formula.

---

## Report File Naming

PDF reports are saved as:
```
report_<candidate_name>_<timestamp>.pdf
```

Example:
```
report_john_doe_20260820_104700.pdf
```

A companion `.json` file with the raw AI assessment data is also saved in the same folder.

---

## Viewing Reports Without the App

The PDF reports are standard PDFs readable in any PDF viewer (Adobe Acrobat, Edge, Chrome, etc.).

The companion JSON file (`report_*.json`) can be read programmatically — see [Data Formats](data-formats.md) for the full schema.

---

## Re-generating a Report

Reports can be re-generated from the same interview transcript. Each re-generation:
- Re-runs the AI assessment (may produce slightly different wording even with `temperature=0.0`, due to context differences)
- Overwrites the previous report file (same filename)

If you want to keep multiple versions, rename the existing PDF before re-generating.
