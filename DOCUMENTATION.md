# AI Recruitment System — Complete System Documentation

## 1. System Overview & Technology Stack

The AI Recruitment System (ARS) is an offline-capable, privacy-first desktop application designed to orchestrate and automate the complete technical hiring workflow. Built for talent acquisition specialists, engineering hiring managers, and recruitment operators, the system automates resume ingestion, structured attribute extraction, applicant ranking against job descriptions, calendar scheduling, proctored live technical assessments on an isolated local-network portal, evaluation scoring, and talent intelligence analytics.

### 1.1 Core Tenets

1. **Local Data Sovereignty:** All candidate resumes, extracted personal details, evaluation scorecards, interview transcripts, and proctoring telemetry remain stored locally in SQLite on the operator's machine. Data never leaves the workstation unless an external cloud AI provider is explicitly enabled by the operator.
2. **Two-Server Network Isolation:** Administrative functions and public candidate assessment portals run on separate network ports with distinct access boundaries. Operators manage the platform via a local-loopback native desktop window on Port 5001, while candidates connect to an isolated, TLS-secured assessment portal on Port 5000 across the local area network.
3. **100% Air-Gapped Operation:** The platform contains bundled typography, offline JavaScript charting libraries, local OCR engines, local speech recognizers, and support for local on-device large language models via Ollama. It can execute the entire recruitment lifecycle without an active internet connection.

### 1.2 Technology Stack

| Layer | Technology | Version / Specification | Purpose |
|---|---|---|---|
| Desktop Container | `pywebview` | 5.x | Native Windows desktop window wrapping Microsoft Edge WebView2. |
| Web Application Framework | `Flask` | 3.x | Back-end application framework for administrative and candidate portals. |
| WSGI Server | `Waitress` | 3.x | Multi-threaded production WSGI server serving the desktop UI on Port 5001. |
| Relational Database | `SQLite` | 3.x | Local ACID-compliant database with custom ORM layer in `app/database.py`. |
| Document Parsers | `python-docx` / `pypdf` | Latest | Native `.docx` XML parsing and digital PDF text stream extraction. |
| OCR Engine | Google Tesseract OCR | 5.3 (Bundled) | Optical character recognition for scanned PDFs and image resumes. |
| Computer Vision & Proctoring | Google MediaPipe / OpenCV | Latest | 468-point facial landmark mesh tracking with Haar cascade fallback. |
| Voice & Speech | HTML5 Web Speech / Vosk | Bundled Model | Client-side STT/TTS with offline local Vosk and `pyttsx3` fallbacks. |
| PDF Report Generation | `FPDF2` | Latest | Material Design 3 monochrome PDF compilation with Latin-1 font sanitization. |
| Data Visualization | `Chart.js` | 4.x (Bundled) | Offline UMD JavaScript charting bundle for talent intelligence dashboards. |
| Cryptography | `cryptography` (Fernet) | Latest | AES-128-CBC + HMAC-SHA256 encryption at rest derived from Machine GUID. |

---

## 2. System Architecture & Two-Server Model

The application enforces security and role separation by running two physically isolated HTTP server listeners within a single host process:

```
[ Operator Desktop Window (pywebview) ]
               │
               ▼ Loopback HTTP (Port 5001)
     [ Waitress WSGI Server ]
               │
               ├── Administrative Dashboard & Views (app/routes/views.py)
               ├── Pipeline Orchestration API (app/routes/api.py)
               ├── Talent Intelligence API (app/routes/intelligence.py)
               ├── System Settings & AI Providers (app/routes/settings.py)
               ├── SQLite Database Layer (app/database.py - 13 Tables)
               ├── Hardware Machine-GUID Encryption (src/security.py)
               └── AI Provider Router (src/provider_router.py)

                                    * * *

[ Candidate Devices on Local Network / VPN ]
               │
               ▼ Inbound HTTPS with Self-Signed TLS (Port 5000)
    [ Flask Candidate Portal Server ]
               │
               ├── Public Candidate Portal Routes (app/routes/candidate.py)
               ├── Token Authentication & Session Binding (interview_tokens)
               ├── Server Pacing & Anti-Tampering Timers (Linear progression)
               ├── Computer Vision Proctoring (MediaPipe Face Mesh + Haar Cascade)
               └── Speech Processing (Web Speech API + Offline Vosk/pyttsx3)
```

### 2.1 Administrative Desktop Port (Port 5001)
- **Host Binding:** `127.0.0.1` (Local Loopback).
- **WSGI Engine:** Waitress multi-threaded production server.
- **Access Boundary:** Rejects any incoming network packets originating from outside the local computer. LAN devices cannot access Port 5001.
- **Session Security:** The native launcher injects a single-use cryptographic nonce during startup to authenticate the native desktop session without exposing administrative credentials over the loopback network.

### 2.2 Candidate Assessment Portal (Port 5000)
- **Host Binding:** `0.0.0.0` (All Network Interfaces).
- **Transport Security:** HTTPS enforced using auto-generated 2048-bit RSA private keys and self-signed X.509 certificates (`cert.pem`, `key.pem`).
- **Access Boundary:** Accessible to candidates across the local area network or VPN via the host machine's LAN IP (e.g., `https://192.168.1.100:5000/candidate-interview/<token>`).
- **Route Isolation:** Exclusively serves candidate interview endpoints. All administrative, ranking, database, and settings routes return HTTP 404 or HTTP 403 on this port.

### 2.3 Runtime Data Storage Topology
All runtime data, database files, uploaded resumes, parsed outputs, cryptographic salts, and logs are resolved dynamically to the operating system's local application data folder (`%LOCALAPPDATA%\AI Recruitment System\` on Windows):

```
%LOCALAPPDATA%\AI Recruitment System\
│
├── data\
│   ├── ars.db                  ← SQLite database (13 relational tables)
│   ├── resumes\                ← Uploaded resumes (.pdf, .docx, .png, .jpg)
│   ├── credentials.json        ← Google Calendar OAuth client secrets (optional)
│   ├── token.json              ← Google Calendar OAuth token cache (auto-generated)
│   └── output\
│       ├── txt\                ← Plaintext extracted from resumes
│       ├── nlp\                ← Structured JSON candidate profiles (_nlp.json, _nlp.txt)
│       ├── ranking\            ← Ranking leaderboards (ranking_scores_<job_id>.json)
│       ├── scheduling\         ← Schedule timetables and RFC 5545 .ics invite files
│       ├── interviews\         ← Candidate response transcripts and proctoring logs
│       ├── reports\            ← Compiled PDF evaluation reports (report_<id>.pdf)
│       └── ssl\                ← Auto-generated TLS certificates (cert.pem, key.pem)
│
├── .secret_salt                ← 16-byte random salt for hardware-bound encryption
└── crash.log                   ← Operating system diagnostic dump on unhandled termination
```

---

## 3. Installation, Setup & Environment Verification

### 3.1 Prerequisites
- Operating System: 64-bit Windows 10 or Windows 11.
- Python Environment: Python 3.10, 3.11, or 3.12 (64-bit).
- Native WebView: Microsoft Edge WebView2 Runtime (installed by default on modern Windows).

### 3.2 Installation Steps

```bash
# 1. Clone the repository
git clone https://github.com/shrs425p/AI-Recruitment-System.git
cd AI-Recruitment-System

# 2. Create and activate a 64-bit Python virtual environment
python -m venv venv
venv\Scripts\activate

# 3. Upgrade core packaging tools
python -m pip install --upgrade pip setuptools wheel

# 4. Install production dependencies
pip install -r requirements.txt
```

### 3.3 Verifying Bundled Offline Assets
Verify that bundled offline models and typography exist in their expected locations:
- Tesseract OCR: `models/Tesseract-OCR/tesseract.exe`
- Vosk Speech Model: `models/vosk-model-small-en-in-0.4/`
- Offline Fonts: `app/static/fonts/inter/` and `app/static/fonts/jetbrains-mono/`
- Offline Chart.js: `app/static/js/chart.umd.min.js`

### 3.4 Launching the Application

```bash
# Start the application
python main.py
```
Upon execution:
1. The SQLite database is initialized with all 13 relational tables.
2. Self-signed TLS certificates are generated in `data/output/ssl/` if not present.
3. The Waitress server boots on `http://127.0.0.1:5001`.
4. The candidate HTTPS portal boots on `https://0.0.0.0:5000`.
5. The native desktop application window opens automatically via `pywebview`.

### 3.5 Running Automated Tests

```bash
# Execute the complete automated test suite (140 tests)
venv\Scripts\python.exe -m pytest -v --no-cov

# Run static code analysis with Ruff
venv\Scripts\ruff.exe check .
```

---

## 4. End-to-End Pipeline Execution Guide

The platform executes an automated 8-stage technical recruitment pipeline:

### Stage 1: Resume Upload & Ingestion
- Supported Formats: Digital PDF, Scanned PDF, Microsoft Word (`.docx`), PNG, JPG, JPEG.
- Processing Logic:
  - Files placed in `data/resumes/` or uploaded through the dashboard are verified for magic byte signatures (`%PDF-`, `PK\x03\x04`, `\x89PNG`, `\xff\xd8\xff`).
  - Filenames are sanitized against directory traversal (`../`, `..\`) and control characters.
  - Colliding filenames receive timestamped unique suffixes. Files exceeding 16 MB are rejected with HTTP 413.

### Stage 2: Text Extraction & OCR Recovery
- Digital PDFs: Decoded via `pypdf` stream readers to extract selectable text layers.
- Word Documents (`.docx`): Parsed natively via `python-docx` by traversing document paragraph runs (`w:p`) and embedded table cells (`w:tbl`), ensuring tabular experience matrices and education records are captured.
- Scanned Fallback & Images: If extracted text is under 50 characters or averages fewer than 10 characters per page, the file is routed to the OCR engine. Pages are rasterized to 300 DPI, converted to 8-bit grayscale, thresholded via Otsu binarization, deskewed in OpenCV, and processed using bundled Tesseract OCR 5.3 in Page Segmentation Mode 3.
- Output: Normalized UTF-8 plaintext saved to `data/output/txt/<candidate_id>.txt`.

### Stage 3: Structured Natural Language Processing (NLP) Extraction
- Two-Stage Parsing:
  1. Deterministic Heuristic Pre-Processing: Employs regular expressions to isolate high-confidence contact data (email addresses, phone numbers, URLs, GitHub, LinkedIn) and detect resume section boundaries.
  2. Large Language Model Extraction: Dispatches segmented text to the active AI provider inside strict XML delimiter blocks (`<resume_text>...</resume_text>`) with a schema definition. Temperature is locked at 0.0 for deterministic output.
- Extracted Attributes Schema:
  - Personal Details: Full name, primary email, phone number, geographic location, portfolio/GitHub/LinkedIn URIs.
  - Skills Taxonomy: Technical skills (languages, frameworks, cloud, databases, tools) and soft skills (leadership, communication, problem-solving).
  - Career History: Employer name, role title, start/end dates, calculated duration in months and years, and bulleted accomplishments.
  - Academic Background: Institution name, degree level, major, graduation year, GPA.
  - Projects: Name, technologies used, descriptive summary, live/repository link.
  - Certifications: Title, issuing body, issuance and expiration dates.
  - Domain Archetype: Categorized into an industry specialization (Backend, Frontend, Full Stack, DevOps/SRE, Data Science, Machine Learning, Cloud Architecture, Mobile Development, Security Engineering).
- Output: Structured JSON saved to `data/output/nlp/<candidate_id>_nlp.json` and human-readable summary in `_nlp.txt`.

### Stage 4: Candidate Ranking & Fit Scoring
- 5-Criterion Weighted Evaluation (Scale 0 to 100 per criterion):
  1. Skills Match (Default Weight: 35%): Evaluates coverage of required and preferred skills, tech stack overlap, and synonymous tools.
  2. Experience Relevance (Default Weight: 25%): Evaluates total career tenure, seniority levels, and historical job responsibilities relative to target role requirements.
  3. Education Fit (Default Weight: 15%): Compares academic degree level and field of study against role prerequisites.
  4. Projects & Applied Work (Default Weight: 15%): Assesses practical implementations, open-source work, and project complexity.
  5. Domain Alignment (Default Weight: 10%): Measures familiarity with domain architecture patterns, business logic, and methodologies.
- Dynamic Weight Normalization: If user-defined weights do not sum to 100%, the engine normalizes each weight proportionately:
  `Normalized Weight = User Weight / Sum of All User Weights`
- Automated Knockout Filters:
  - Minimum Tenure Knockout: Configurable experience threshold in years (`MIN_EXPERIENCE_YEARS`). Candidates below threshold are disqualified.
  - Mandatory Skills Filter: Disqualifies applicants lacking non-negotiable required skills from the job template.
  - Knocked-out candidates remain in the database for auditing but are excluded from interview scheduling.
- Candidate Tiers:
  - Tier 1: Strong Match (Score 85–100) — Direct interview recommendation.
  - Tier 2: Potential Match (Score 70–84) — Secondary interview shortlist.
  - Tier 3: Review Required (Score 50–69) — Manual recruiter assessment required.
  - Tier 4: Unmatched (Score 0–49) — Disqualified or pooled for future roles.
- Recruiter Notes, Tags & CSV Export: Recruiters can save in-place notes, assign workflow triage tags (Shortlisted, On Hold, Follow Up, Interviewed, Rejected), and export leaderboards to RFC 4180 CSV spreadsheets with formula injection escaping.

### Stage 5: Interview Scheduling & Calendar Synchronization
- Shortlist Cutoff: Isolates top N candidates (configurable via `SHORTLIST_TOP_N`, default 5), bypassing knocked-out candidates and resolving ties by technical skills score.
- Slot Allocation: Generates discrete interview slots across working weekdays within configured working hours (09:00 to 18:00), factoring in duration and buffer spacing.
- Google Calendar API: Connects via OAuth 2.0 desktop authorization, queries recruiter availability via the FreeBusy API to avoid conflicts, and automatically creates calendar events with attendee invites.
- iCalendar (.ics) Generation: Creates RFC 5545 `.ics` calendar invite files attached to outbound emails for one-click import into Microsoft Outlook, Apple Calendar, and Thunderbird.
- Automated SMTP Dispatch: Sends multi-part MIME (text and HTML) invitation emails via SMTP STARTTLS with dynamic template interpolation (`{candidate_name}`, `{job_title}`, `{selected_slot}`, `{interview_link}`, `{hr_name}`, `{company}`).

### Stage 6: Candidate Assessment Portal
- Isolated HTTPS Server: Operates on Port 5000 with self-signed TLS certificates.
- Single-Use Token Lifecycle: Validates unique tokens (`T_*`), checks expiration, initializes active sessions in `interview_sessions`, and flags tokens as used (`used = 1`) to prevent session replay.
- Candidate Onboarding: Presents informed consent disclosures regarding AI scoring and proctoring, verifies webcam framing via live video preview, and tests microphone audio levels.
- Anti-Tampering & Server Pacing: Enforces server-side elapsed timers (comparing delivery timestamp with submission timestamp), blocks client-side timer manipulation, mandates strict linear question progression (no skipping or editing past answers), and preserves state during network interruptions.

### Stage 7: Real-Time Computer Vision Proctoring
- Dual-Engine Computer Vision:
  - Primary: Google MediaPipe Face Mesh tracking 468 3D landmarks in real time. Analyzes facial presence, eye gaze vector estimation, head pose orientation (yaw, pitch, roll), and mouth movement.
  - Fallback: OpenCV Haar Cascade frontal face classifier (`haarcascade_frontalface_default.xml`) for environments lacking WebGL.
- Five Anomaly Violation Classes:
  1. Face Absence: No face detected for > 3 consecutive seconds.
  2. Multiple Faces: Two or more distinct faces detected simultaneously.
  3. Window Blur / Tab Switching: Monitors HTML5 Page Visibility API and `window.onblur` events when candidates leave the interview tab.
  4. Clipboard & Copy-Paste Deterrence: Intercepts paste events and flags automated clipboard injections via keystroke timing analysis.
  5. Response Timeout: Expiration of per-question timer before answer submission.
- Quantitative Scoring & Deductions:
  - Tab Switch / Window Blur: -15 points per occurrence.
  - Multiple Faces Detected: -20 points per occurrence.
  - Extended Face Absence: -10 points per occurrence.
  - Copy-Paste Attempt: -10 points per occurrence.
  - Question Timeout: -5 points per occurrence.
- Risk Levels: Clean (Score 90–100), Low Warning (Score 70–89), High Risk (Score 0–69).

### Stage 8: Interview Evaluation & Report Generation
- Rubric Evaluation Dimensions (0 to 10 each):
  1. Technical Accuracy: Correctness of technical concepts, frameworks, and architecture explanations.
  2. Communication Clarity: Structure, conciseness, articulation, and professional delivery.
  3. Problem-Solving Depth: Analytical methodology, edge case handling, and trade-off reasoning.
  4. Behavioral Alignment: Alignment with organizational values, ownership mindset, and teamwork.
- Combined Fit Score Formula:
  `Combined Score = (Resume Fit Score * 0.40) + (Interview Evaluation Score * 0.60)`
- Standardized PDF Report Generation (FPDF2):
  - Monochrome Material Design 3 layout optimized for digital viewing and black-and-white printing.
  - Latin-1 character sanitization to prevent unicode clipping.
  - Sections: Executive Scorecard, Rubric Matrix with comparative bars, Proctoring Integrity Breakdown, Recruiter Notes, Full Chronological Transcript, and Final Hiring Recommendation (Hire, Hold, Reject).
- Instant Alerts: Dispatches native Windows desktop pop-up notifications and records unread alerts in the in-app SQLite notification tray (`hr_notifications`).

---

## 5. Talent Intelligence & Workforce Analytics

### 5.1 Vector Semantic Search
- Architecture: Computes 384-dimensional dense semantic vectors representing candidate competencies and career accomplishments, indexed in the `candidate_embeddings` SQLite table.
- Search Interface: Recruiters execute natural language queries (e.g., "Find engineers experienced in distributed caching and microservices").
- Query Mathematics: Queries are embedded and compared against candidate vectors using cosine similarity routines executed directly in SQLite queries:
  `Cosine Similarity = (Vector A · Vector B) / (||Vector A|| * ||Vector B||)`
- Returns ranked candidate profiles matching query intent with similarity percentage scores.

### 5.2 Candidate Comparison Matrix
- Enables side-by-side comparative analysis of up to 4 shortlisted candidates simultaneously.
- Contrasts: Total years of professional experience, required skills match percentage, individual criteria scores (Skills, Experience, Education, Projects, Domain), live interview ratings, proctoring risk ratings, and highlighted strengths and gaps.

### 5.3 Automated Candidate Feedback Letters
- Generates personalized, constructive post-interview feedback letters.
- Structure: Appreciation for participation, commendations highlighting technical strengths demonstrated in the resume and interview, and actionable recommendations outlining technical areas for further study.

### 5.4 The Six Visual Talent Analytics Modules

1. **Skill Supply vs. Demand Gap Analytics:** Side-by-side comparative bar chart contrasting required skills from job descriptions against skill frequencies extracted across all candidate resumes. Identifies candidate surpluses and talent bottlenecks.
2. **Experience vs. Score Quadrant Matrix:** Four-quadrant scatter matrix plotting Total Years of Experience (X-axis) against Composite Fit Score (Y-axis):
   - Upper-Left (Rising Stars): Low experience, high fit score.
   - Upper-Right (Seasoned Veterans): High experience, high fit score.
   - Lower-Left (Entry Level / Needs Prep): Low experience, low fit score.
   - Lower-Right (Mismatched Experience): High experience, low fit score.
3. **Interview Question Difficulty Breakdown:** Ranked horizontal bar chart displaying average candidate score (0 to 10) and average response latency per interview topic, identifying filter questions versus ambiguous questions.
4. **Proctoring Integrity & Risk Breakdown:** Doughnut chart showing pool-wide distribution of Clean, Low Warning, and High Risk sessions, paired with categorical violation bars (tab switches, face absences, multiple faces, timeouts).
5. **Hiring Velocity & Bottleneck Tracker:** Milestone timeline card displaying elapsed hours and minutes between pipeline stages (Time to Screen, Candidate Turnaround, Time to Report).
6. **Education & Domain Talent Mix Demographics:** Dual progress-bar / doughnut charts displaying aggregate candidate distributions across academic degrees and technical domains.

---

## 6. Air-Gapped Offline Infrastructure

### 6.1 Zero Outbound CDN Architecture
- All frontend styling, interactive behaviors, typography, and charts run completely from local assets stored in `app/static/`.
- Automated test suites audit all HTML templates to confirm that zero external `<script src="https://...">` or `<link href="https://...">` tags exist.
- The application makes zero outbound HTTP/HTTPS requests to external hosts when operating in Privacy Mode.

### 6.2 Bundled Local Typography
- Inter Font Family: Regular (400), Medium (500), SemiBold (600), and Bold (700) weights located in `app/static/fonts/inter/`.
- JetBrains Mono Font Family: Regular monospace font located in `app/static/fonts/jetbrains-mono/`.
- Fonts are loaded locally via `@font-face` rules in `app/static/css/styles.css`.

### 6.3 Bundled Chart.js Library
- Charting library powering all six talent intelligence widgets and score bars is stored locally at `app/static/js/chart.umd.min.js`.
- License: Open-source MIT license.
- Execution: Client-side canvas rendering running entirely within the local browser runtime without external telemetry.

### 6.4 On-Device Large Language Model Inference (Ollama)
- Daemon Endpoint: `http://localhost:11434`.
- Default Model: `llama3.2:3b`.
- Operates on local CPU or GPU hardware via the Ollama server. Zero candidate text or transcripts leave the physical workstation.

---

## 7. Multi-Provider AI Architecture

### 7.1 Operation Modes
- **Cloud Mode (`APP_MODE = "cloud"`):** Routes AI requests through the `ProviderRouter` across enabled cloud providers using round-robin load balancing and automatic rate-limit tracking.
- **Privacy Mode (`APP_MODE = "privacy"`):** Routes all AI requests directly to the local Ollama server on the host machine. Operates 100% offline.

### 7.2 The ProviderRouter Engine
- Coordinates requests across up to 8 AI providers.
- Filters enabled providers possessing valid, non-placeholder API keys.
- Tracks request timestamps per provider over sliding 60-second windows to calculate Requests Per Minute (RPM).
- If an enabled provider reaches its RPM threshold, requests route automatically to alternate enabled providers.
- Catches HTTP 429 (Rate Limit) and HTTP 500 (Service Error) exceptions and retries prompts against alternate providers.
- If Ollama times out in Privacy Mode and `CLOUD_ENABLED` is `True`, falls back to Anthropic Claude as a secondary failover.

### 7.3 Supported AI Providers Directory

| Provider | Endpoint URL | Key Prefix | Default Model | Free Tier RPM |
|---|---|---|---|---|
| NVIDIA NIM | `https://integrate.api.nvidia.com/v1` | `nvapi-` | `meta/llama-3.1-8b-instruct` | ~10 RPM |
| Anthropic | `https://api.anthropic.com/v1` | `sk-ant-` | `claude-3-5-haiku-latest` | Pay-as-you-go |
| Google Gemini | `https://generativelanguage.googleapis.com/v1beta` | `AIza` | `gemini-1.5-flash` | 15 RPM |
| Groq | `https://api.groq.com/openai/v1` | `gsk_` | `llama3-8b-8192` | 30 RPM |
| OpenAI | `https://api.openai.com/v1` | `sk-` | `gpt-4o-mini` | Pay-as-you-go |
| OpenRouter | `https://openrouter.ai/api/v1` | `sk-or-` | `meta-llama/llama-3.1-8b-instruct:free` | Varies |
| GitHub Models | `https://models.inference.ai.azure.com` | `ghp_` | `gpt-4o-mini` | Developer Tier |
| Local Ollama | `http://localhost:11434` | None | `llama3.2:3b` | Unlimited (Local) |

---

## 8. Relational Database Reference (SQLite Schema)

The persistent data layer is implemented via SQLite (`ars.db`) in `%LOCALAPPDATA%\AI Recruitment System\data\ars.db` and managed through `app/database.py`. It comprises 13 relational tables:

### 1. `pipeline_runs`
Tracks execution runs of the recruitment pipeline.
- `run_id` (TEXT, Primary Key): Unique run identifier (e.g., `RUN_20261019_001`).
- `run_ts` (TEXT, Not Null): ISO 8601 creation timestamp.
- `job_title` (TEXT, Not Null): Job title evaluated in this pipeline run.
- `candidate_count` (INTEGER, Default 0): Total resumes processed.
- `status` (TEXT, Default 'Pending'): Pipeline state (`Pending`, `Running`, `Completed`, `Failed`).
- `error_msg` (TEXT, Nullable): Diagnostic error string in the event of failure.

### 2. `candidates`
Stores extracted candidate profiles and evaluated fit scores.
- `candidate_id` (TEXT, Primary Key): Unique candidate identifier.
- `run_id` (TEXT, Foreign Key referencing `pipeline_runs.run_id`): Pipeline run reference.
- `full_name` (TEXT, Not Null): Candidate full name.
- `email` (TEXT, Nullable): Primary contact email address.
- `phone` (TEXT, Nullable): Telephone contact number.
- `resume_filename` (TEXT, Not Null): Filename of the uploaded resume document.
- `total_experience_years` (REAL, Default 0.0): Computed career tenure in years.
- `domain` (TEXT, Nullable): Classified technical domain specialization.
- `fit_score` (REAL, Default 0.0): Composite resume ranking fit score (0 to 100).
- `skills_json` (TEXT, Nullable): Serialized JSON array of extracted technical and soft skills.
- `profile_json` (TEXT, Nullable): Complete serialized JSON candidate profile.
- `created_at` (TEXT, Not Null): ISO 8601 creation timestamp.

### 3. `schedules`
Stores allocated candidate interview slots.
- `schedule_id` (TEXT, Primary Key): Unique schedule record identifier.
- `candidate_id` (TEXT, Foreign Key referencing `candidates.candidate_id`): Candidate reference.
- `job_title` (TEXT, Not Null): Target role title.
- `slot_start` (TEXT, Not Null): ISO 8601 interview start time.
- `slot_end` (TEXT, Not Null): ISO 8601 interview end time.
- `ics_path` (TEXT, Nullable): Filesystem path to the generated `.ics` calendar file.
- `gcal_event_id` (TEXT, Nullable): Remote Google Calendar event identifier.
- `status` (TEXT, Default 'Scheduled'): Slot status (`Scheduled`, `Confirmed`, `Completed`, `Cancelled`).
- `created_at` (TEXT, Not Null): ISO 8601 creation timestamp.

### 4. `email_log`
Maintains an audit log of all outbound SMTP email communications.
- `email_id` (TEXT, Primary Key): Unique email event identifier.
- `recipient` (TEXT, Not Null): Recipient email address.
- `subject` (TEXT, Not Null): Message subject header.
- `body_snippet` (TEXT, Nullable): Truncated preview of sent message text.
- `status` (TEXT, Default 'Sent'): Dispatch status (`Sent`, `Failed`, `Queued`).
- `error` (TEXT, Nullable): SMTP error diagnostic string if failed.
- `sent_at` (TEXT, Not Null): ISO 8601 dispatch timestamp.

### 5. `interview_tokens`
Manages access tokens for the candidate interview portal.
- `token` (TEXT, Primary Key): Unique candidate access token (e.g., `T_1792180299_151492`).
- `candidate_id` (TEXT, Foreign Key referencing `candidates.candidate_id`): Candidate record reference.
- `role` (TEXT, Not Null): Target job role for question generation.
- `expires_at` (TEXT, Not Null): ISO 8601 expiration timestamp.
- `created_at` (TEXT, Not Null): ISO 8601 generation timestamp.
- `used` (INTEGER, Default 0): Binary flag (0 = unused, 1 = session initiated/used).

### 6. `job_templates`
Stores job description templates and evaluation rubrics.
- `template_id` (TEXT, Primary Key): Unique template identifier.
- `title` (TEXT, Not Null): Target job role title.
- `domain` (TEXT, Nullable): Role domain archetype.
- `description` (TEXT, Not Null): Complete job description text.
- `required_skills` (TEXT, Nullable): Comma-delimited or JSON string of mandatory skills.
- `preferred_skills` (TEXT, Nullable): Comma-delimited or JSON string of optional skills.
- `min_experience_years` (REAL, Default 0.0): Minimum tenure required.
- `created_at` (TEXT, Not Null): ISO 8601 creation timestamp.

### 7. `app_settings`
Key-value storage for application configurations and encrypted secrets.
- `key` (TEXT, Primary Key): Configuration setting key string.
- `value` (TEXT, Nullable): Stored value (plaintext or encrypted ciphertext).
- `is_encrypted` (INTEGER, Default 0): Binary flag (1 if value is encrypted via AES-Fernet).
- `updated_at` (TEXT, Not Null): ISO 8601 update timestamp.

### 8. `interview_sessions`
Captures interview execution transcripts, proctoring metrics, and evaluations.
- `session_id` (TEXT, Primary Key): Unique session identifier.
- `token` (TEXT, Foreign Key referencing `interview_tokens.token`): Authentication token reference.
- `candidate_id` (TEXT, Foreign Key referencing `candidates.candidate_id`): Candidate reference.
- `transcript_json` (TEXT, Nullable): Complete serialized JSON transcript of questions and answers.
- `proctor_data_json` (TEXT, Nullable): Serialized JSON logs of proctoring events and violations.
- `interview_score` (REAL, Default 0.0): Evaluated interview performance score (0 to 100).
- `combined_score` (REAL, Default 0.0): Composite fit score (40% resume + 60% interview).
- `status` (TEXT, Default 'In_Progress'): Session state (`In_Progress`, `Completed`, `Terminated`).
- `created_at` (TEXT, Not Null): ISO 8601 session start timestamp.
- `completed_at` (TEXT, Nullable): ISO 8601 session completion timestamp.

### 9. `candidate_embeddings`
Stores dense vector representations for semantic search.
- `candidate_id` (TEXT, Primary Key, Foreign Key referencing `candidates.candidate_id`): Candidate reference.
- `embedding_json` (TEXT, Not Null): Serialized 384-dimensional dense vector array.
- `indexed_at` (TEXT, Not Null): ISO 8601 indexing timestamp.

### 10. `ai_telemetry`
Records latency, token consumption, and operational metrics for AI invocations.
- `telemetry_id` (TEXT, Primary Key): Unique telemetry record identifier.
- `provider` (TEXT, Not Null): Name of the AI provider called (e.g., `nvidia`, `groq`, `ollama`).
- `model` (TEXT, Not Null): Specific model identifier used.
- `prompt_tokens` (INTEGER, Default 0): Estimated or reported prompt token count.
- `completion_tokens` (INTEGER, Default 0): Estimated or reported completion token count.
- `latency_ms` (INTEGER, Default 0): Execution duration in milliseconds.
- `success` (INTEGER, Default 1): Binary success flag.
- `created_at` (TEXT, Not Null): ISO 8601 timestamp.

### 11. `candidate_feedback`
Stores AI-generated candidate feedback letters.
- `feedback_id` (TEXT, Primary Key): Unique feedback record identifier.
- `candidate_id` (TEXT, Foreign Key referencing `candidates.candidate_id`): Candidate reference.
- `feedback_text` (TEXT, Not Null): Complete candidate feedback letter.
- `created_at` (TEXT, Not Null): ISO 8601 generation timestamp.

### 12. `candidate_notes`
Stores recruiter notes, annotations, and recruitment triage tags.
- `note_id` (TEXT, Primary Key): Unique note identifier.
- `candidate_id` (TEXT, Foreign Key referencing `candidates.candidate_id`): Candidate reference.
- `note_text` (TEXT, Nullable): Recruiter notes and comments.
- `tag` (TEXT, Nullable): Triage tag (`Shortlisted`, `On Hold`, `Follow Up`, `Interviewed`, `Rejected`).
- `updated_at` (TEXT, Not Null): ISO 8601 timestamp.

### 13. `hr_notifications`
Stores real-time alerts notifying recruitment staff of interview completions.
- `notification_id` (TEXT, Primary Key): Unique notification identifier.
- `candidate_id` (TEXT, Foreign Key referencing `candidates.candidate_id`): Candidate reference.
- `event_type` (TEXT, Not Null): Event category (`interview_completed`).
- `message` (TEXT, Not Null): Human-readable alert notification text.
- `is_read` (INTEGER, Default 0): Binary read status flag (0 = unread, 1 = read).
- `created_at` (TEXT, Not Null): ISO 8601 creation timestamp.

---

## 9. Complete REST API Reference

### 9.1 Administrative Desktop Endpoints (Port 5001)

| Route Path | HTTP Method | Auth / Headers | Input Parameters | Output Response |
|---|---|---|---|---|
| `/` | GET | Desktop Session | None | Renders primary dashboard HTML. |
| `/ranking` | GET | Desktop Session | None | Renders candidate leaderboard HTML. |
| `/scheduling` | GET | Desktop Session | None | Renders interview timetable HTML. |
| `/reports` | GET | Desktop Session | None | Renders evaluation reports catalog HTML. |
| `/talent-intelligence` | GET | Desktop Session | None | Renders talent analytics & vector search HTML. |
| `/settings` | GET | Desktop Session | None | Renders settings hub HTML. |
| `/api/run-auto-pipeline` | POST | CSRF Token | None | Returns JSON acknowledgment (`status: "started"`). |
| `/api/reset-pipeline` | POST | CSRF Token | None | Wipes runtime output folders while preserving settings. |
| `/api/pipeline-status` | GET | Session | None | Returns JSON with current stage, percent, and state. |
| `/api/logs/stream` | GET | Session | None | Server-Sent Events stream emitting live text logs. |
| `/api/open-output-folder` | POST | CSRF Token | None | Invokes Windows Explorer to display runtime output folder. |
| `/api/ranking/export/csv` | GET | Session | None | Streams RFC 4180 CSV spreadsheet file download. |
| `/api/candidate/<id>/notes` | GET | Session | `id` in path | Returns JSON object with candidate notes and triage tag. |
| `/api/candidate/<id>/notes` | POST | CSRF Token | JSON: `note_text`, `tag` | Saves or updates recruiter notes and tag in database. |
| `/api/candidate/<id>/purge` | DELETE | CSRF Token | `id` in path | GDPR purge; permanently deletes database rows and files. |
| `/api/intelligence/search` | POST | CSRF Token | JSON: `query`, `top_k` | Returns ranked list of semantically matching candidates. |
| `/api/intelligence/compare` | POST | CSRF Token | JSON: `candidate_ids` (up to 4) | Returns side-by-side comparative matrix of scores/skills. |
| `/api/intelligence/feedback/<id>` | GET | Session | `id` in path | Returns personalized feedback letter text for candidate. |
| `/api/intelligence/analytics` | GET | Session | None | Returns JSON object with data for all 6 analytics widgets. |
| `/api/settings/save` | POST | CSRF Token | Form/JSON: settings dict | Encrypts secrets, updates `app_settings`, reloads config. |
| `/api/provider-models` | POST | CSRF Token | JSON: `provider`, `api_key` | Queries remote provider API and returns live model list. |
| `/api/email/test` | POST | CSRF Token | None | Tests SMTP server login and returns status tuple. |
| `/api/notifications` | GET | Session | None | Returns array of recent alerts and unread alert count. |
| `/api/notifications/mark-read` | POST | CSRF Token | JSON: `notification_ids` | Updates notification read status to 1. |

### 9.2 Candidate Interview Portal Endpoints (Port 5000)

| Route Path | HTTP Method | Auth / Headers | Input Parameters | Output Response |
|---|---|---|---|---|
| `/candidate-interview/<token>` | GET | Valid Token in URL | None | Validates token, checks expiry, renders portal HTML. |
| `/api/interview/start` | POST | Valid Token | JSON: `token` | Marks token as used, creates session, returns question 1. |
| `/api/interview/question` | GET | Valid Token | Query: `token` | Returns active question text, index, and timer allowance. |
| `/api/interview/answer` | POST | Valid Token | JSON: `token`, `answer_text`, `elapsed_seconds` | Commits answer, records time, triggers follow-up analysis. |
| `/api/interview/proctor-event` | POST | Valid Token | JSON: `token`, `event_type`, `details` | Logs anomaly violation to session proctoring log. |
| `/api/interview/finish` | POST | Valid Token | JSON: `token` | Finalizes interview, calculates scores, compiles PDF, alerts HR. |

---

## 10. Security, Cryptography & Privacy Architecture

### 10.1 Hardware-Bound AES-Fernet Encryption at Rest
- Sensitive configurations—such as AI provider API keys, SMTP passwords, and Google OAuth tokens—are encrypted at rest within SQLite using AES-128 in Cipher Block Chaining (CBC) mode with PKCS7 padding and HMAC-SHA256 authentication (Fernet specification).
- Key Derivation: Cryptographic keys are derived dynamically using PBKDF2 with HMAC-SHA256 across 100,000 iterations.
- Hardware Binding: The derivation inputs combine a persistent 16-byte random salt stored in `.secret_salt` with the host workstation's unique hardware Machine GUID (queried from Windows Registry at `HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Cryptography\MachineGuid`).
- Portability Protection: If an unauthorized party copies `ars.db` to another computer, encrypted values cannot be decrypted because the hardware Machine GUID will not match, preventing credential theft from offline backups.

### 10.2 Cryptographic Cross-Site Request Forgery (CSRF) Protection
- State-modifying administrative endpoints (`POST`, `PUT`, `DELETE`) require a valid cryptographic CSRF token.
- Tokens are bound to the active user session and verified using constant-time string comparison algorithms to prevent timing attacks.

### 10.3 In-Memory Sliding-Window Rate Limiting
- The candidate portal incorporates an in-memory sliding-window IP rate limiter restricting clients to a maximum of 60 requests per minute per IP address.
- Defends against denial-of-service attempts and rapid automated answer submission attacks.

### 10.4 Loopback Desktop Nonces
- Upon startup, the `pywebview` desktop launcher generates a high-entropy single-use cryptographic token passed into the native window.
- The desktop interface injects this nonce during initial session establishment.
- Incoming HTTP requests to Port 5001 lacking a valid session cookie or matching nonce are rejected with HTTP 403 Forbidden, preventing unauthorized local applications from tampering with administrative APIs.

### 10.5 XML Prompt Injection Containment Boundaries
- Resume content parsed by large language models is encapsulated inside strict XML delimiter blocks (`<resume_text>...</resume_text>`).
- System prompts instruct models to treat all internal content strictly as passive data and ignore any commands attempting to reset system instructions, alter scoring rubrics, or bypass knockout criteria.

### 10.6 GDPR Right to Erasure (Candidate Data Purging)
- Provides full compliance with data protection mandates (GDPR, CCPA) through an automated candidate purge routine:
  1. Deletes candidate records from `candidates`.
  2. Deletes associated notes from `candidate_notes`.
  3. Deletes interview sessions and transcripts from `interview_sessions`.
  4. Deletes active tokens from `interview_tokens`.
  5. Purges semantic vector representations from `candidate_embeddings`.
  6. Deletes candidate feedback records from `candidate_feedback`.
  7. Clears notification logs from `hr_notifications`.
  8. Deletes all associated filesystem assets: original resume (`.pdf`/`.docx`), extracted plaintext (`.txt`), structured NLP JSON, and compiled PDF reports.

---

## 11. Quality Assurance, Automated Tests & Code Quality

### 11.1 Test Suite Architecture

The test suite consists of 14 domain-scoped modules covering 140 automated tests:

| Test Module | Domain Coverage |
|---|---|
| `test_airgap.py` | Verifies local existence of Inter and JetBrains Mono fonts, local Chart.js bundle, and audits templates for zero CDN links. |
| `test_api.py` | Tests all administrative routes, CSRF token validation, candidate notes and tags, CSV export, and error handling. |
| `test_auth.py` | Tests user authentication, password hashing, session management, rate limiting, and desktop nonces. |
| `test_db.py` | Tests SQLite initialization, schema creation for all 13 tables, migration scripts, and transactional CRUD logic. |
| `test_intelligence.py` | Tests vector search cosine similarity math, candidate comparison matrix, feedback letters, and 6 analytics calculators. |
| `test_interview.py` | Tests token validation, question generation, role blueprints, timers, adaptive follow-up probing, and transcripts. |
| `test_nlp.py` | Tests regex heuristic pre-parsing, contact extraction, skills taxonomy classification, and JSON normalization. |
| `test_proctor.py` | Tests proctoring anomaly detection algorithms, tab switch tracking, webcam face counting, and integrity scoring. |
| `test_ranking.py` | Tests 5-criterion fit scoring math, dynamic weight normalization, tenure knockouts, and mandatory skill checks. |
| `test_reports.py` | Tests FPDF2 PDF generation, Latin-1 character sanitization, 40/60 combined fit scoring, and report layouts. |
| `test_resume.py` | Tests document parsing across digital PDFs, python-docx Word documents, Tesseract OCR text recovery, and corrupt files. |
| `test_schedule.py` | Tests shortlist isolation, timetable slot generation, iCalendar (.ics) syntax, and SMTP dispatch routines. |
| `test_security.py` | Tests AES-Fernet hardware-bound encryption, machine GUID salt mixing, sensitive configuration protection, and GDPR purge. |
| `test_voice.py` | Tests offline speech recognition and synthesis fallbacks, audio buffers, and Vosk model discovery. |

### 11.2 Test Execution Metrics
- Automated Tests: 140 tests.
- Pass Rate: 100% (140 passed in approximately 34 seconds).
- Code Quality: Clean static analysis under Ruff linter rules with zero formatting or linting errors.

---

## 12. Windows Deployment & Installer Packaging

### 12.1 PyInstaller Standalone Compilation
- Spec File: `build/build.spec`.
- Packaging Mode: Onedir mode (bundles Python runtime, compiled C-extensions, and dependencies into `dist/ARS/`).
- Bundled Binaries & Models:
  - `Tesseract-OCR/` binary distribution and English language `traineddata`.
  - Vosk speech recognition model (`vosk-model-small-en-in-0.4`).
  - Pre-compiled OpenCV and MediaPipe vision binaries.
- Bundled Static Assets:
  - HTML templates (`app/templates/`).
  - Static styles, local fonts, and bundled Chart.js (`app/static/`).

### 12.2 Inno Setup Windows Installer Creation
- Script File: `build/installer.iss`.
- Generated Executable: `installer_output/ARS_Setup_1.0.exe`.
- Installation Directory: `C:\Program Files\AI Recruitment System\`.
- System Integration: Creates Start Menu shortcuts, registers an uninstaller in Windows Add or Remove Programs, and preserves user data in `%LOCALAPPDATA%\AI Recruitment System\` during upgrades.

### 12.3 Windows Firewall Configuration
- Helper Script: `scripts/setup_firewall.bat`.
- Configuration: Adds an inbound TCP firewall rule to Windows Defender Firewall allowing incoming traffic on Port 5000 across private and domain network profiles.

---

## 13. Master Settings & Tuning Reference Index

Dynamic configuration keys stored in the `app_settings` table in SQLite:

| Setting Key | Default Value | Value Type | Encrypted | Operational Impact |
|---|---|---|---|---|
| `APP_MODE` | `'cloud'` | String | No | Toggles between `'cloud'` (ProviderRouter) and `'privacy'` (Local Ollama). |
| `OLLAMA_BASE_URL` | `'http://localhost:11434'` | String | No | Endpoint URL for the on-device Ollama daemon. |
| `OLLAMA_MODEL` | `'llama3.2:3b'` | String | No | Model tag used for local on-device inference. |
| `NVIDIA_ENABLED` | `True` | Boolean | No | Toggles NVIDIA NIM cloud provider in ProviderRouter pool. |
| `NVIDIA_KEY` | `''` | String | Yes | API authentication key for NVIDIA NIM catalog. |
| `NVIDIA_MODEL` | `'meta/llama-3.1-8b-instruct'` | String | No | Active model tag for NVIDIA inference. |
| `GROQ_ENABLED` | `False` | Boolean | No | Toggles Groq provider in ProviderRouter pool. |
| `GROQ_KEY` | `''` | String | Yes | API authentication key for Groq Cloud. |
| `GROQ_MODEL` | `'llama3-8b-8192'` | String | No | Active model tag for Groq inference. |
| `GEMINI_ENABLED` | `False` | Boolean | No | Toggles Google Gemini in ProviderRouter pool. |
| `GEMINI_KEY` | `''` | String | Yes | API key for Google AI Studio / Gemini API. |
| `GEMINI_MODEL` | `'gemini-1.5-flash'` | String | No | Active model tag for Gemini inference. |
| `ANTHROPIC_ENABLED` | `False` | Boolean | No | Toggles Anthropic Claude in ProviderRouter pool. |
| `ANTHROPIC_KEY` | `''` | String | Yes | API key for Anthropic Claude console. |
| `ANTHROPIC_MODEL` | `'claude-3-5-haiku-latest'` | String | No | Active model tag for Anthropic inference. |
| `OPENAI_ENABLED` | `False` | Boolean | No | Toggles OpenAI GPT in ProviderRouter pool. |
| `OPENAI_KEY` | `''` | String | Yes | API key for OpenAI platform. |
| `OPENAI_MODEL` | `'gpt-4o-mini'` | String | No | Active model tag for OpenAI inference. |
| `OPENROUTER_ENABLED` | `False` | Boolean | No | Toggles OpenRouter gateway in ProviderRouter pool. |
| `OPENROUTER_KEY` | `''` | String | Yes | API key for OpenRouter gateway. |
| `OPENROUTER_MODEL` | `'meta-llama/llama-3.1-8b-instruct:free'` | String | No | Active model tag for OpenRouter inference. |
| `GITHUB_ENABLED` | `False` | Boolean | No | Toggles GitHub Models in ProviderRouter pool. |
| `GITHUB_TOKEN` | `''` | String | Yes | GitHub Personal Access Token with model scope. |
| `GITHUB_MODEL` | `'gpt-4o-mini'` | String | No | Active model tag for GitHub Models inference. |
| `SMTP_HOST` | `''` | String | No | Outgoing SMTP mail server hostname. |
| `SMTP_PORT` | `587` | Integer | No | Outgoing SMTP port (587 STARTTLS). |
| `SMTP_EMAIL` | `''` | String | No | Sender email address for interview invitations. |
| `SMTP_PASSWORD` | `''` | String | Yes | Sender email account password or app password. |
| `HR_NAME` | `'HR Manager'` | String | No | Recruiter / hiring manager display name in emails. |
| `COMPANY_NAME` | `'Our Company'` | String | No | Organization name shown in emails and reports. |
| `INTERVIEW_TECH_QUESTIONS` | `5` | Integer | No | Number of technical questions generated per interview (3–10). |
| `INTERVIEW_BEHAVIORAL_QUESTIONS` | `3` | Integer | No | Number of behavioral questions generated per interview (1–5). |
| `INTERVIEW_TIME_LIMIT` | `120` | Integer | No | Per-question timer limit in seconds (60, 90, 120, 180). |
| `WEIGHT_SKILLS` | `35` | Integer | No | Weight assigned to Skills Match criterion in ranking. |
| `WEIGHT_EXPERIENCE` | `25` | Integer | No | Weight assigned to Experience Relevance criterion. |
| `WEIGHT_EDUCATION` | `15` | Integer | No | Weight assigned to Education Fit criterion. |
| `WEIGHT_PROJECTS` | `15` | Integer | No | Weight assigned to Projects & Practical Work criterion. |
| `WEIGHT_DOMAIN` | `10` | Integer | No | Weight assigned to Domain Alignment criterion. |
| `MIN_EXPERIENCE_YEARS` | `0.0` | Float | No | Experience knockout threshold in years (0.0 = disabled). |
| `SHORTLIST_TOP_N` | `5` | Integer | No | Number of top candidates shortlisted for interview scheduling. |

---

## 14. Operational Troubleshooting & Runbooks

### 14.1 Document Ingestion & Extraction Runbook
- **Issue: Text extracted from PDF is empty.**
  - Cause: The document is a scanned image PDF lacking an active text layer, and Tesseract OCR was unable to initialize.
  - Action: Verify `models/Tesseract-OCR/tesseract.exe` exists in the application root. Check that system temporary directories have write permissions.
- **Issue: Word (.docx) upload returns HTTP 400.**
  - Cause: The file has a `.docx` extension but is an older legacy binary `.doc` format or contains corrupted ZIP headers.
  - Action: Re-save the file in Microsoft Word or LibreOffice as an Office Open XML Document (`.docx`) before uploading.
- **Issue: Upload rejected with HTTP 413 Payload Too Large.**
  - Cause: File exceeds the 16 MB size limit.
  - Action: Compress embedded images in the resume document to reduce file size below 16 MB.

### 14.2 AI Provider & Model Runbook
- **Issue: "No cloud providers are enabled" error.**
  - Cause: System is in Cloud Mode, but all enabled providers have placeholder keys (e.g., `nvapi-...`).
  - Action: Open Settings → AI Providers. Paste a valid API key into at least one provider (NVIDIA, Groq, Gemini), enable it, and click Save Settings.
- **Issue: Provider returns HTTP 429 Rate Limit.**
  - Cause: Exceeded provider free-tier Requests Per Minute limit.
  - Action: The `ProviderRouter` automatically fails over to other enabled providers. Enable multiple providers in Settings to spread extraction load.
- **Issue: Ollama fails to respond in Privacy Mode.**
  - Cause: The Ollama daemon is not running, or the model has not been pulled.
  - Action: Open a command terminal and execute `ollama serve`. Verify model presence with `ollama list`. Pull missing models via `ollama pull llama3.2:3b`.

### 14.3 Network, TLS & Candidate Portal Runbook
- **Issue: Candidate cannot load interview URL across LAN.**
  - Cause: Windows Defender Firewall is blocking inbound connections on TCP Port 5000.
  - Action: Right-click `scripts/setup_firewall.bat` and select Run as Administrator. Confirm host IP via `ipconfig`.
- **Issue: Browser displays "Your connection is not private" (SSL Warning).**
  - Cause: Self-signed TLS certificate (`cert.pem`) generated for local network use.
  - Action: Instruct the candidate to click Advanced → Proceed to [IP Address] (unsafe) to access the interview portal.
- **Issue: Camera or microphone fails to initialize in candidate portal.**
  - Cause: Browser blocked media permissions, or another application (Zoom, Teams) is holding the webcam lock.
  - Action: Close competing video applications, click the camera icon in the browser address bar, and set permissions to Allow.

### 14.4 Email & Calendar Runbook
- **Issue: SMTP connection fails with (535, 'Authentication failed').**
  - Cause: Incorrect username or password. For Gmail, this indicates the user entered their account password rather than an App Password.
  - Action: Create a 16-character App Password at `myaccount.google.com/apppasswords` (requires 2-Step Verification) and save it in Settings → Email.
- **Issue: Google Calendar returns HttpError 403.**
  - Cause: Google Calendar API is not enabled in the Google Cloud Console.
  - Action: Navigate to `console.cloud.google.com` → APIs & Services → Library, search for Google Calendar API, and click Enable.

---

## 15. Complete Project File Manifest

```
AI-Recruitment-System/
├── main.py                          ← Application entry point (Waitress + Flask + pywebview)
├── pyproject.toml                   ← Package specification, dependencies, and Ruff config
├── requirements.txt                 ← Production dependency manifest
├── README.md                        ← Public repository documentation & feature overview
├── report.md                        ← Master System Manual & Technical Reference
├── DOCUMENTATION.md                 ← Complete System Documentation
│
├── app/                             ← Application Web Package
│   ├── __init__.py                  ← Flask application factory (create_app)
│   ├── core.py                      ← Thread-safe log queue and Server-Sent Events (SSE)
│   ├── database.py                  ← SQLite database layer and 13-table schema DDL
│   ├── folder_opener.py             ← Cross-platform shell utility for Windows Explorer
│   ├── rate_limiter.py              ← In-memory sliding-window IP rate limiting
│   ├── utils.py                     ← Security decorators (@login_required, @csrf_protect)
│   ├── routes/                      ← Flask Route Blueprints
│   │   ├── api.py                   ← Administrative API routes (pipeline, notes, CSV export)
│   │   ├── auth.py                  ← Authentication routes (login, logout, CSRF token)
│   │   ├── candidate.py             ← Public candidate interview portal on Port 5000
│   │   ├── intelligence.py          ← Talent Intelligence API routes (vector search, compare)
│   │   ├── reports.py               ← PDF report viewing and streaming routes
│   │   ├── settings.py              ← System configuration, AI providers, and model discovery
│   │   └── views.py                 ← Administrative desktop dashboard page views
│   ├── templates/                   ← Jinja2 HTML Templates
│   │   ├── base.html                ← Master administrative layout with navigation & trays
│   │   ├── dashboard.html           ← Pipeline console, stage cards, live SSE log stream
│   │   ├── ranking.html             ← Ranked candidate leaderboard, criteria breakdown, notes
│   │   ├── scheduling.html          ← Interview timetable and calendar slot coordinator
│   │   ├── interview.html           ← Candidate assessment portal, video feed, timers
│   │   ├── reports.html             ← Evaluation reports catalog and PDF viewer
│   │   ├── intelligence.html        ← Talent intelligence suite, vector search, analytics
│   │   └── settings.html            ← Configuration controls, AI providers, weights, timers
│   └── static/                      ← Static Front-End Assets
│       ├── css/styles.css           ← Design system styles and responsive layout rules
│       ├── fonts/inter/             ← Bundled local Inter fonts (Regular, Medium, SemiBold, Bold)
│       ├── fonts/jetbrains-mono/    ← Bundled local JetBrains Mono fonts
│       └── js/chart.umd.min.js      ← Bundled offline Chart.js UMD distribution
│
├── src/                             ← Core Processing Pipeline Modules
│   ├── common.py                    ← Path resolution, AI dispatcher (call_ollama), atomic I/O
│   ├── ai_mode.py                   ← AI provider registry and execution mode selector
│   ├── provider_router.py           ← Multi-provider router with RPM tracking and failover
│   ├── security.py                  ← Machine-GUID AES-Fernet encryption at rest, GDPR purge
│   ├── pdf_to_txt.py                ← Resume text extraction (digital PDF, Word .docx, OCR)
│   ├── txt_to_nlp.py                ← NLP candidate profile extraction into structured JSON
│   ├── rank_candidates.py           ← 5-criterion fit scoring, weight normalization, knockouts
│   ├── schedule_candidates.py       ← Shortlist isolation, slot allocation, iCalendar files
│   ├── email_sender.py              ← SMTP email dispatch with STARTTLS and custom templates
│   ├── google_calendar.py           ← Google Calendar API OAuth 2.0 integration
│   ├── generate_questions.py        ← Interview question generation and adaptive follow-up probing
│   ├── proctoring.py                ← Computer vision proctoring engine (MediaPipe, OpenCV)
│   ├── voice_system.py              ← Offline text-to-speech and speech-to-text fallbacks
│   ├── evaluate_interview.py        ← Transcript evaluation, rubric scoring, 40/60 combined fit
│   ├── generate_reports.py          ← Multi-page PDF evaluation report compilation (FPDF2)
│   └── talent_intelligence.py       ← 384-dim vector embeddings, compare matrix, 6 analytics
│
├── config/                          ← Dynamic Configuration Package
│   └── __init__.py                  ← SQLite database-backed runtime configuration module
│
├── tests/                           ← Domain-Scoped Automated Test Suite (140 Tests)
│   ├── conftest.py                  ← Shared pytest fixtures, temporary directories, mocks
│   ├── test_airgap.py               ← 100% offline air-gapped compliance verification
│   ├── test_api.py                  ← Administrative API routes and CSV export tests
│   ├── test_auth.py                 ← Authentication, session, rate limiting, nonce tests
│   ├── test_db.py                   ← SQLite database schema and transactional CRUD tests
│   ├── test_intelligence.py         ← Vector search, candidate compare, and 6 analytics tests
│   ├── test_interview.py            ← Interview flow, question generation, and timer tests
│   ├── test_nlp.py                  ← Regex heuristic pre-parsing and JSON profile schema tests
│   ├── test_proctor.py              ← Computer vision proctoring anomaly detection tests
│   ├── test_ranking.py              ← Fit scoring, weight normalization, and knockout tests
│   ├── test_reports.py              ← PDF report compilation and Latin-1 encoding tests
│   ├── test_resume.py               ← Document parsing (digital PDF, Word .docx, OCR) tests
│   ├── test_schedule.py             ← Shortlist scheduling, iCalendar, and SMTP dispatch tests
│   ├── test_security.py             ← AES-Fernet encryption, Machine GUID, and GDPR purge tests
│   └── test_voice.py                ← Offline speech recognition and synthesis fallback tests
│
├── build/                           ← Deployment & Installer Configuration
│   ├── build.spec                   ← PyInstaller single-folder standalone compilation spec
│   └── installer.iss                ← Inno Setup 6 Windows installer creation script
│
├── scripts/                         ← Utility & Setup Scripts
│   ├── build_installer.bat          ← Orchestrates PyInstaller and Inno Setup builds
│   ├── setup_firewall.bat           ← Configures Windows Firewall inbound rule for Port 5000
│   └── verify_providers.py          ← Standalone connectivity diagnostic for AI providers
│
├── models/                          ← Bundled Offline Binary Models
│   ├── Tesseract-OCR/               ← Google Tesseract OCR 5.3 Windows binary distribution
│   └── vosk-model-small-en-in-0.4/  ← Offline Vosk English speech recognition model
│
└── docs/                            ← Modular Documentation Topics (22 Guides)
    ├── index.md                     ← Master documentation index and stack breakdown
    ├── getting-started.md           ← Installation, environment verification, first run
    ├── architecture.md              ← Two-server model, subsystem boundaries, data flow
    ├── pipeline.md                  ← Step-by-step recruitment pipeline walkthrough
    ├── talent-intelligence.md       ← Vector search, candidate compare, 6 analytics modules
    ├── airgap.md                    ← 100% offline air-gapped operation and verification
    ├── interview-system.md          ← Token authentication, adaptive probing, proctoring
    ├── reports.md                   ← Combined score formula, PDF layout, HR desktop alerts
    ├── configuration.md             ← Dynamic database settings reference and defaults
    ├── ai-providers.md              ← Cloud vs Privacy mode, provider setup, model selection
    ├── security.md                  ← Machine-GUID encryption, CSRF, rate limiting, GDPR purge
    ├── api-reference.md             ← Detailed HTTP endpoint reference and schemas
    ├── testing.md                   ← Test suite architecture, 14 domain modules, 140 tests
    ├── google-calendar.md           ← Google Calendar OAuth 2.0 integration and setup
    ├── email-setup.md               ← SMTP configuration, provider guides, template variables
    ├── data-formats.md              ← DDL for 13 SQLite tables, JSON schemas, CSV formats
    ├── customization.md             ← Tuning weights, knockout thresholds, interview timers
    ├── data-management.md           ← Backup, restore, reset, and candidate purge procedures
    ├── deployment.md                ← PyInstaller compilation and Inno Setup Windows installer
    ├── troubleshooting.md           ← Diagnostic workflows for common runtime issues
    ├── faq.md                       ← Frequently asked questions
    └── contributing.md              ← Code conventions, Ruff lint rules, air-gap guidelines
```
