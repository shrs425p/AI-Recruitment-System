# Frequently Asked Questions

---

## General

### Does the system support Microsoft Word (.docx) resumes?
Yes. The upload pipeline natively accepts `.docx` documents alongside `.pdf` and image files. Word resumes are parsed directly via `python-docx` without calling external converters or cloud services.

### Can I run the entire application completely offline?
Yes. When **Privacy Mode** is active, the system runs with zero external internet dependencies:
- AI inference runs locally via Ollama (`http://127.0.0.1:11434`).
- Optical character recognition runs via bundled Tesseract OCR.
- Face detection uses bundled OpenCV Haar cascade files.
- UI fonts (Inter, JetBrainsMono) and the charting engine (Chart.js) are bundled locally in `app/static/`, with zero outbound CDN calls.

### Where is candidate data stored?
All application data is stored locally on the host machine:
- Database: `data/recruitment.db` (SQLite with 9 relational tables).
- Resumes: `data/resumes/` (optionally encrypted at rest via AES-Fernet).
- Text extractions: `data/output/txt/`.
- Structured profiles: `data/output/nlp/`.
- Leaderboards & CSV exports: `data/output/ranking/`.
- Interview transcripts: `data/output/interviews/`.
- Evaluation PDF dossiers: `data/output/reports/`.

No candidate resumes or personally identifiable information are sent to external databases or third-party storage buckets.

### How do candidate notes and tags work?
Recruiters can record qualitative notes (e.g. *"Strong portfolio"*, *"Prefers remote"*) and status tags (e.g. *"Shortlisted"*, *"Hold"*) directly on any candidate row on the Ranking or Reports pages. These annotations are saved immediately to the `candidates` table in SQLite and appear automatically in the candidate's final evaluation dossier.

### How do I export candidate rankings to Excel or an ATS?
Click the **Export to CSV** button on the Ranking or Reports page, or query `/api/ranking/export/csv`. This produces an RFC 4180 compliant CSV spreadsheet with Rank, Name, Email, Total Score, Skills Match, Experience Score, Strengths, and Recommendation.

---

## Interviews & Proctoring

### How does the HR manager know when an interview finishes?
The system emits an automated real-time notification:
1. An OS desktop pop-up notification appears on the HR manager's workstation: *"Candidate Completed: Jane Doe has completed the interview for Senior Python Developer. Report is ready."*
2. A record is added to the `hr_notifications` table.
3. The dashboard notification badge increments, allowing the HR team to open the candidate's dossier with a single click.

### Can I configure interview duration and question counts?
Yes. In the **Settings** tab, recruiters can customize:
- Technical question count (3 to 10 questions).
- Behavioral question count (1 to 5 STAR questions).
- Per-question response timer (60s, 90s, 120s, 180s).

### What happens if a candidate gives a shallow or vague answer?
The interview engine uses adaptive conversational follow-up probing (`should_probe_further`). If an answer lacks depth (depth score $\le 1$ or total score $< 7$), the bot dynamically interjects with a follow-up probing question asking for concrete implementation specifics, edge cases, or engineering trade-offs.

### Does the system detect fast copy-paste answers?
Yes. The server computes response elapsed time using a high-resolution monotonic clock. If a candidate submits more than 100 characters in less than 2.0 seconds, the server logs a `COPY_PASTE_DETECTED` violation flag in the interview transcript.

### Is candidate video footage recorded or stored?
No. Webcam frames are processed in-memory solely for real-time face detection counts (zero faces vs multiple faces). No video or image files are saved to disk, preserving candidate privacy.

---

## Technical & Architecture

### Why does the application run two separate servers?
The application uses a two-server isolation model:
- **HR Administrative Server (`127.0.0.1:5001`):** Bound strictly to localhost; inaccessible across the network.
- **Candidate Portal (`0.0.0.0:5000`):** Bound to the local network over HTTPS with token authentication. All HR routes return 404 on this port.

### How do I test the application locally?
The test suite consists of 140 automated tests across 14 domain modules:
```bash
pytest -v
```
All tests run with isolated temporary SQLite databases and mock fixtures, requiring no live external network access.
