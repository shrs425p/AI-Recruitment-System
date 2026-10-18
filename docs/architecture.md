# Architecture

This document describes the architectural design of the AI Recruitment System — the runtime two-server model, component boundaries, database persistence layer, and end-to-end data flow.

---

## High-Level Topology

```
┌─────────────────────────────────────────────────────────────────┐
│                         Windows Host                            │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                   pywebview Desktop Shell               │    │
│  │   (native OS frame wrapping an embedded Chromium view)  │    │
│  │                                                         │    │
│  │   http://127.0.0.1:5001  ──────►  Waitress WSGI         │    │
│  │                                   HR Dashboard Server   │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                 │
│  ┌────────────────────────┐    ┌───────────────────────────┐    │
│  │   SQLite Database      │    │  Flask HTTPS Server       │    │
│  │   recruitment.db       │    │  (port 5000, 0.0.0.0)     │    │
│  │   (9 Relational Tables)│    │ Candidate Interview Portal│    │
│  └────────────────────────┘    └──────────────▲────────────┘    │
│                                               │                 │
│  ┌────────────────────────┐                   │                 │
│  │   Local Engines        │                   │                 │
│  │   - Ollama (11434)     │                   │                 │
│  │   - Tesseract OCR      │                   │                 │
│  │   - Bundled Assets     │                   │                 │
│  └────────────────────────┘                   │                 │
└───────────────────────────────────────────────│─────────────────┘
                                                │ HTTPS (TLS)
                                     ┌──────────┴──────────┐
                                     │ Candidate's Browser │
                                     │ (Any Device on LAN) │
                                     └─────────────────────┘
```

---

## The Two-Server Isolation Model

To strictly segregate administrative HR capabilities from external candidate inputs, the application operates two concurrent network servers:

### 1. HR Desktop Administrative Server (Waitress, HTTP)
- **Interface:** `127.0.0.1` (strictly loopback — unreachable from the local network).
- **Port:** `5001` (configurable via `FLASK_PORT`).
- **Serving Engine:** Production WSGI server via `Waitress` (multi-threaded pool).
- **Access Model:** Renders inside the embedded desktop shell. Protected by scrypt password hashing, session cookies, and single-use desktop nonces.

### 2. Candidate Interview Portal (Flask, HTTPS)
- **Interface:** `0.0.0.0` (all network interfaces — accessible over the local area network).
- **Port:** `5000` (configurable via `CANDIDATE_PORT`).
- **Serving Engine:** Flask HTTPS server with an auto-generated RSA-2048 certificate.
- **Access Model:** Token-gated candidate entrypoints (`/candidate-interview/<token>`).
- **Isolation Policy:** All administrative HR endpoints (`/dashboard`, `/ranking`, `/reports`, `/settings`) return HTTP 404 when requested on this port.

---

## Component Boundaries

```
┌────────────────────────── Flask Layer (app/) ──────────────────────────┐
│                                                                        │
│  routes/auth.py         ← Login, password scrypt, desktop nonces       │
│  routes/dashboard.py    ← Aggregations, pipeline tasks, GDPR delete    │
│  routes/upload.py       ← .docx, .pdf, and image ingestion             │
│  routes/nlp.py          ← NLP profile extraction triggers              │
│  routes/ranking.py      ← Candidate scoring, weights, notes, CSV export│
│  routes/scheduling.py   ← Slots, interview tokens, email dispatch      │
│  routes/interview.py    ← Candidate portal, session state, proctoring  │
│  routes/reports.py      ← PDF evaluation dossiers, notification tray   │
│  routes/intelligence.py ← Semantic search, comparison, 6 analytics     │
│  routes/settings.py     ← Dynamic settings CRUD & provider secrets     │
│  routes/logs.py         ← Live SSE log streaming                       │
│  database.py            ← Transactional SQLite persistence layer       │
│  rate_limiter.py        ← Sliding-window IP rate limiter               │
│                                                                        │
└────────────────────────────────────┬───────────────────────────────────┘
                                     │ dispatches
┌────────────────────────────────────▼───────── Business Logic (src/) ──┐
│                                                                       │
│  pdf_to_txt.py          ← python-docx, pypdf, Tesseract OCR           │
│  nlp_extractor.py       ← Schema-constrained AI entity extraction     │
│  ranking_engine.py      ← Weight balancing, knockouts, rubric scoring │
│  talent_intelligence.py ← Vector embeddings, comparisons, 6 analytics │
│  scheduling.py          ← Top-N shortlist, slot allocation, .ics      │
│  interview_bot.py       ← Adaptive blueprints, probing, evaluation    │
│  webcam_proctor.py      ← Face tracking (MediaPipe + Haar cascades)   │
│  voice_interview.py     ← Web Speech API + Vosk speech fallback       │
│  report_generator.py    ← FPDF2 Latin-1 PDF compilation & 40/60 score │
│  provider_router.py     ← Multi-cloud routing & RPM load balancing    │
│  security.py            ← AES-Fernet encryption & secret derivation   │
│  common.py              ← Paths, JSON repair, call_ollama wrapper     │
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘
```

---

## Database Schema (recruitment.db)

Database persistence is handled transactionally by `app/database.py`. The database consists of 9 relational tables:

| Table | Purpose |
|---|---|
| `runs` | Tracks pipeline execution batches, stages, status, and configuration metadata. |
| `candidates` | Stores candidate names, resume scores, hire recommendations, recruiter notes, and status tags. |
| `schedules` | Stores candidate interview time slots, confirmation statuses, and run associations. |
| `interview_tokens` | Manages single-use UUID tokens granting candidates access to the interview portal. |
| `interview_sessions` | Tracks live candidate sessions, HMAC session keys, and proctoring flag counts. |
| `job_templates` | Stores reusable job descriptions, domain targets, and custom weighting presets. |
| `hr_notifications` | Persistent record of HR notifications (e.g. candidate interview completions) with read states. |
| `app_settings` | Key-value store for runtime settings (interview question limits, timer, active provider). |
| `talent_embeddings` | High-dimensional dense vector embeddings of candidate profiles for semantic search. |

---

## End-to-End Pipeline Data Flow

```
1. RESUME INGESTION (app/routes/upload.py)
   Accepts .docx, .pdf, .png, .jpg files.
   Validates extension whitelist and writes to data/resumes/.

2. TEXT EXTRACTION (src/pdf_to_txt.py)
   Routes .docx to python-docx.
   Routes digital PDFs to pypdf stream reader.
   Routes scanned PDFs and images to bundled Tesseract OCR.
   Normalizes whitespace and saves UTF-8 text to data/output/txt/.

3. NLP PROFILE PARSING (src/nlp_extractor.py)
   Extracts personal info, skills, experience years, domain, education, and certs.
   Performs JSON repair and saves structured profiles to data/output/nlp/*_nlp.json.

4. RANKING & KNOCKOUTS (src/ranking_engine.py)
   Normalizes rubric weights.
   Evaluates knockout prerequisites (min experience, mandatory skills, certs).
   Computes composite scores, attaches recruiter notes/tags, and exports CSV.
   Saves to data/output/ranking/ranking_scores_*.json.

5. SCHEDULING (src/scheduling.py)
   Selects Top-N candidates and allocates interview time slots.
   Generates standard .ics calendar invites and issues UUID interview tokens.
   Dispatches SMTP email invitations.

6. PROCTORED INTERVIEW (app/routes/interview.py + src/interview_bot.py)
   Candidate accesses https://<host-ip>:5000/candidate-interview/<token>.
   Consent verified; session initialized with HMAC key.
   Administers dynamic technical and behavioral questions based on role blueprint.
   Triggers adaptive probing if an answer lacks depth.
   Proctoring thread tracks face presence, tab switches, and instant copy-paste.
   Saves transcript to data/output/interviews/interview_*.json.

7. EVALUATION REPORTS & NOTIFICATIONS (src/report_generator.py)
   Computes combined score (40% resume fit + 60% interview performance).
   Renders Material Design 3 monochrome PDF via fpdf2.
   Emits real-time desktop notification and logs entry in hr_notifications.

8. TALENT INTELLIGENCE (src/talent_intelligence.py)
   Generates dense vector embeddings into SQLite.
   Executes semantic talent pool queries.
   Computes side-by-side candidate comparisons and feedback letters.
   Computes 6 visual analytics modules for executive review.
```
