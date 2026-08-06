# Pipeline Guide

The recruitment workflow is organized as repeatable stages. Each stage can be run manually from its page, and the dashboard can run the operational stages automatically in one click.

## Overview

| Stage | Input | Output | Main module |
|---|---|---|---|
| Upload | Resume files | `data/resumes/` | `app/routes/upload.py` |
| Text extraction | PDF/image resumes | `data/output/txt/` | `src/pdf_to_txt.py` |
| NLP extraction | Text resumes | `data/output/nlp/` | `src/nlp_extractor.py` |
| Ranking | Candidate profiles and job description | `data/output/ranking/` | `src/ranking_engine.py` |
| Scheduling | Ranking results and available slots | `data/output/scheduling/` | `src/scheduling.py` |
| Interview | Candidate tokens and live answers | `data/output/interviews/` | `src/interview_bot.py` |
| Reports | Interview transcripts | `data/output/reports/` | `src/report_generator.py` |

## One-Click Auto-Pipeline

The dashboard Auto-Pipeline runs in a background thread and updates progress through `/api/task-status`.

```text
1. Convert resumes to text
2. Extract candidate profiles
3. Update ranking from the active job description
4. Schedule ranked candidates and create interview tokens
5. Generate reports for completed interviews
```

The run is idempotent where possible. Existing text files, NLP JSON files, ranked candidates, scheduled candidates, and generated reports are skipped instead of overwritten.

The interview stage itself is not automated because it requires candidate participation, voice/text answers, and proctoring. Once transcripts exist, the report stage can be run automatically.

## Manual Workflow

1. Upload all resumes for the hiring batch.
2. Convert resumes to text.
3. Run NLP extraction.
4. Paste or load a job description and run ranking.
5. Review the leaderboard.
6. Generate the schedule from available slots or Google Calendar.
7. Send or copy interview links for confirmed candidates.
8. Let candidates complete interviews.
9. Generate final reports and review recommendations.

## Stage Details

### Upload

Supported formats:

- `.pdf`
- `.png`
- `.jpg`
- `.jpeg`

Uploaded files are stored with their original names. Avoid duplicate filenames in the same batch because later uploads can replace earlier files with the same name.

### Text Extraction

Digital PDFs are processed with PyMuPDF. Scanned PDFs and images use Tesseract OCR. The output is UTF-8 plain text in `data/output/txt/`.

### NLP Extraction

The configured AI model converts resume text into structured JSON. The most important fields are candidate identity, contact information, skills, education, experience, projects, certifications, and summary.

### Ranking

Ranking requires an active job description. The engine extracts role requirements and scores each candidate against them. Results are saved as timestamped JSON and text leaderboard files.

Ranking also creates a pre-interview shortlist report. This report helps HR review interview priority, score distribution, candidate strengths, and key gaps before scheduling.

### Scheduling

The scheduler loads top ranked candidates and assigns available slots. It writes schedule JSON files and ICS calendar files. Confirmed candidates receive interview tokens.

### Interviews

Candidates open a tokenized interview link and answer generated questions. The app records answers, scores, timing, and proctoring data in a transcript JSON file.

### Reports

Reports combine ranking scores, interview performance, and proctoring signals. Outputs include individual JSON/TXT reports and a final summary.

## Safety Notes

- Finish a pipeline run before adding more resumes to the same batch.
- Keep `LOGIN_ENABLED = True` when the app is exposed beyond a single trusted user.
- Do not delete `data/output/` during a run.
- Keep cloud AI providers disabled unless candidate data is allowed to leave the machine.
