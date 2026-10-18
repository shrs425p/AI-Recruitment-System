# AI Recruitment System — Comprehensive Master System Manual & Technical Reference

## 1. System Overview & Operational Concept

The AI Recruitment System (ARS) is a privacy-focused, offline-first desktop application designed to orchestrate and execute the complete technical hiring workflow. The software enables talent acquisition teams, engineering hiring managers, and recruitment operators to ingest resumes, extract structured candidate profiles, rank applicants against customized job descriptions, schedule interviews, host proctored live technical assessments on an isolated local-network portal, evaluate candidate responses, and analyze aggregate talent metrics.

### Core Operating Philosophy

The application is built on three core operational pillars:

1. **Local Data Sovereignty:** All candidate resumes, extracted personal information, interview video/audio analyses, transcripts, evaluation scorecards, and system configurations are stored locally on the host machine. Data does not leave the operating workstation unless an operator explicitly configures a cloud AI provider.
2. **Two-Server Network Isolation:** Administrative functions and public candidate assessment portals run on separate network ports with distinct access boundaries. Administrators control the system via a local-loopback native desktop window, while candidates connect to an isolated, TLS-secured assessment portal across the local area network.
3. **Air-Gapped Offline Operation:** The platform contains bundled typography, offline JavaScript visualization libraries, local optical character recognition binaries, local speech recognition models, and support for local on-device large language models via Ollama. It can execute the entire recruitment lifecycle without an active internet connection.

---

## 2. Hardware, Software & Network Prerequisites

### 2.1 Hardware Requirements

- **Processor (CPU):** 64-bit multi-core x86_64 processor (Intel Core i5/i7/i9 8th Generation or AMD Ryzen 5/7/9 equivalent or higher). A minimum of 4 physical cores is recommended for local PDF parsing, computer vision processing, and concurrent audio transcription.
- **System Memory (RAM):**
  - Minimum: 8 Gigabytes of RAM for running the application in Cloud Mode.
  - Recommended: 16 Gigabytes to 32 Gigabytes of RAM when operating in Privacy Mode with on-device local LLM execution via Ollama.
- **Storage Space:**
  - Application Installation: Approximately 500 Megabytes.
  - Bundled OCR and Voice Models: Approximately 300 Megabytes.
  - Local AI Models (Ollama): 2 Gigabytes to 8 Gigabytes depending on the selected model parameter size (e.g., llama3.2:3b requires approximately 2.0 GB of disk space).
  - Candidate Resumes and Generated Reports: 1 Megabyte to 5 Megabytes per evaluated candidate.
- **Camera & Audio (Candidate Device):** Standard USB or integrated webcam capable of 720p video capture at 15 frames per second, and a functional microphone for verbal answers.

### 2.2 Operating System & Platform Dependencies

- **Supported Operating Systems:** Microsoft Windows 10 (64-bit) and Windows 11 (64-bit).
- **Desktop Runtime Shell:** Microsoft Edge WebView2 Runtime (installed by default on modern Windows 10 and 11 builds).
- **Core Software Dependencies (Bundled or Virtual Environment):**
  - Python Runtime: Python version 3.10, 3.11, or 3.12 (64-bit).
  - WSGI Web Server: Waitress multi-threaded production WSGI server.
  - Web Application Framework: Flask.
  - Native Desktop Wrapper: pywebview.
  - Database Engine: SQLite 3.
  - PDF & Document Parsers: pypdf (digital PDF text stream decoder) and python-docx (Office Open XML Word document parser).
  - Optical Character Recognition (OCR): Google Tesseract OCR 5.3 (pre-compiled Windows distribution bundled in models/Tesseract-OCR/) paired with pytesseract and pdf2image.
  - Computer Vision & Proctoring: Google MediaPipe (468-point face mesh tracking) and OpenCV (Haar cascade frontal face classifier fallback).
  - Voice & Speech Systems: HTML5 Web Speech API (in-browser SpeechRecognition and SpeechSynthesis) with offline fallbacks via pyttsx3 and Vosk (vosk-model-small-en-in-0.4 bundled in models/).
  - PDF Report Generation: FPDF2.
  - Data Visualization: Chart.js UMD distribution bundled locally in app/static/js/chart.umd.min.js.

### 2.3 Network Architecture & Port Binding

The platform establishes two distinct HTTP network listeners:

1. **Administrative Desktop Port (Port 5001):**
   - Bound Address: 127.0.0.1 (Loopback).
   - Protocol: HTTP via Waitress WSGI.
   - Purpose: Hosts the administrative dashboard, pipeline control engines, settings management, and talent analytics.
   - Access Rule: Inbound requests originating from outside the host machine are rejected at the operating system socket layer. Outside devices on the local network cannot view or connect to Port 5001.

2. **Candidate Assessment Portal (Port 5000):**
   - Bound Address: 0.0.0.0 (All Host Interfaces).
   - Protocol: HTTPS via Flask with auto-generated 2048-bit RSA self-signed TLS certificates.
   - Purpose: Hosts the candidate assessment portal, question progression engine, audio input handler, and proctoring event receiver.
   - Access Rule: Reachable across the local area network or VPN via the host machine's LAN IP address (e.g., https://192.168.1.100:5000/candidate-interview/<token>). All administrative routes are blocked on this port.

---

## 3. Screen-by-Screen User Interface Guide

### 3.1 Dashboard & Pipeline Control Console (/)

The primary dashboard serves as the operational cockpit for executing recruitment batches:
- **Pipeline Stage Cards:** Displays the eight recruitment stages (Upload, Extraction, NLP Parsing, Ranking, Scheduling, Interview, Evaluation, Reporting) with visual status indicators (Pending, In Progress, Completed, Failed).
- **Batch Control Buttons:**
  - Run Pipeline: Initiates the automated end-to-end processing pipeline across all uploaded candidate resumes.
  - Reset Pipeline: Wipes temporary pipeline outputs (parsed text, scorecards, schedules, reports) to allow a clean run while preserving system settings, API keys, and database configurations.
  - Open Output Folder: Invokes Windows File Explorer directly to the dynamic output directory in AppData.
- **Real-Time Live Console Log:** An interactive terminal card that streams live server logs via Server-Sent Events (SSE). Operators can watch text extraction, AI prompt dispatches, scoring calculations, and scheduling operations in real time.

### 3.2 Candidate Ranking & Leaderboard (/ranking)

The ranking dashboard displays evaluated candidates ordered by composite fit:
- **Leaderboard Table:**
  - Rank: Numerical ranking position based on final score.
  - Candidate Name & Contact: Full name, verified email address, and phone number.
  - Composite Fit Score: Normalized score (0 to 100) reflecting weighted alignment with the job description.
  - Criteria Breakdown: Individual scores for Skills Match, Experience Relevance, Education Fit, Projects, and Domain Alignment.
  - Status / Knockout Badge: Indicates candidate tier (Strong Match, Potential Match, Review Required, Unmatched) or Knockout flags.
  - Actions: Buttons to inspect qualitative strengths/gaps, add recruiter notes, assign triage tags, or purge candidate data.
- **Recruiter Notes & Tags Modal:** An interactive dialog where recruiters can type qualitative observations (e.g., notice period, salary requirements, interview impressions) and assign color-coded triage tags (Shortlisted, On Hold, Follow Up, Interviewed, Rejected).
- **Export to CSV Button:** Downloads an RFC 4180-compliant comma-separated spreadsheet of the current leaderboard.

### 3.3 Interview Timetable & Scheduling (/scheduling)

The scheduling interface allows recruiters to coordinate interview windows:
- **Shortlist Selection:** Displays the top N shortlisted candidates selected for interview scheduling based on ranking scores.
- **Timetable View:** Displays allocated calendar slots mapped across upcoming working weekdays with start times, end times, and duration blocks.
- **Calendar Synchronization Controls:**
  - Connect Google Calendar: Initiates OAuth 2.0 authorization to link the recruiter's Google Calendar.
  - Scan Free/Busy Slots: Queries Google Calendar for available openings within configured working hours.
- **Dispatch Invites Button:** Generates unique candidate portal tokens, creates iCalendar (.ics) files, and dispatches automated invitation emails via SMTP.

### 3.4 Candidate Assessment Portal (/candidate-interview/<token>)

The candidate-facing interface rendered on Port 5000:
- **Onboarding & Consent Screen:** Introduces the candidate to the automated interview process, explains the evaluation criteria, and requests informed consent for webcam proctoring and audio recording.
- **Hardware Permission & Preview Card:** Displays a live video preview from the candidate's webcam to verify framing, lighting, and camera angle, alongside an interactive audio volume meter to verify microphone levels.
- **Assessment Workspace:**
  - Question Header: Displays the current question sequence index (e.g., Question 3 of 8) and topic classification.
  - Question Card: Formatted question prompt, with optional audible text-to-speech playback.
  - Server Countdown Timer: An animated countdown bar showing remaining response time.
  - Dual Answering Interface: An interactive text editor for typed responses, paired with a microphone button for verbal speech-to-text dictation.
  - Real-Time Proctoring Overlay: A floating video container showing the candidate's live camera feed with MediaPipe facial landmark tracking indicators.

### 3.5 Evaluation Reports & Transcript Viewer (/reports)

The reports catalog enables hiring managers to review completed interview assessments:
- **Report Catalog Table:** Lists all evaluated candidates, associated role titles, completion timestamps, combined fit scores, and proctoring risk ratings.
- **In-App PDF Viewer:** An integrated document previewer rendering compiled multi-page PDF evaluation reports.
- **Download Action:** Allows hiring managers to save standardized PDF reports directly to local storage.

### 3.6 Talent Intelligence & Visual Analytics Suite (/talent-intelligence)

The executive intelligence dashboard provides deep aggregate insights:
- **Vector Semantic Search Bar:** A natural-language query input allowing recruiters to search candidate profiles semantically (e.g., "Find developers with high-concurrency Redis caching experience").
- **Candidate Comparison Matrix:** An interactive tool allowing recruiters to select up to 4 candidates and compare their scores, credentials, and pros/cons in an aligned side-by-side grid.
- **Personalized Feedback Generator:** Generates structured, professional candidate feedback letters.
- **The Six Talent Analytics Widgets:** Interactive visual charts rendering skill gaps, experience-to-score quadrants, question difficulty ratings, proctoring integrity distributions, hiring velocity timelines, and candidate talent demographics.

### 3.7 Settings & Provider Configuration (/settings)

The central configuration hub:
- **General Settings:** Recruiter display name, company name, working hours, and lookahead calendar horizon.
- **AI Mode Toggle:** Switch between Cloud Mode (ProviderRouter) and Privacy Mode (Local Ollama).
- **AI Provider Cards:** Individual configuration panels for NVIDIA NIM, Anthropic, Gemini, Groq, OpenAI, OpenRouter, GitHub Models, and Ollama. Includes API key input, live model discovery buttons, and model selector dropdowns.
- **Interview Configuration:** Inputs to adjust the number of technical questions (3 to 10), behavioral questions (1 to 5), and per-question timers (60s, 90s, 120s, 180s).
- **Scoring Weights & Knockouts:** Numeric sliders to adjust the 5 criteria weights (Skills, Experience, Education, Projects, Domain) and minimum experience knockout thresholds.
- **Email Server Configuration:** SMTP host, port, sender email, app password, and interactive Test Connection button.

---

## 4. End-to-End Recruitment Pipeline Operational Guide

The recruitment pipeline consists of eight sequential, automated stages:

### Stage 1: Document Upload & Ingestion

1. The recruiter places candidate resume files into the data/resumes/ directory or uploads them via the dashboard interface.
2. The ingestion validator checks each file against format extensions (.pdf, .docx, .png, .jpg, .jpeg) and verifies binary magic byte signatures.
3. Filenames are sanitized to remove path traversal sequences and special characters. Colliding filenames receive timestamped unique suffixes. Files exceeding 16 MB are rejected.

### Stage 2: Text Extraction & OCR Recovery

1. Digital PDFs are processed via pypdf stream decoders to extract text layers.
2. Word documents (.docx) are processed via python-docx, traversing paragraphs and embedded table cells.
3. If an uploaded PDF has low text density (fewer than 50 total characters or under 10 characters per page), or if the file is an image (.png, .jpg), it is routed to the OCR engine.
4. The OCR engine converts pages to 300 DPI images, applies Otsu binarization and deskewing via OpenCV, and executes Tesseract OCR 5.3 in Page Segmentation Mode 3.
5. Extracted text is normalized to UTF-8 and saved to data/output/txt/<candidate_id>.txt.

### Stage 3: Natural Language Profile Extraction

1. The raw extracted text is segmented using regex pattern recognition to identify contact markers (email, phone, URLs).
2. The segmented text is encapsulated inside strict XML delimiters (<resume_text>...</resume_text>) and dispatched to the active AI provider with a standardized JSON extraction schema.
3. The AI normalizes dates, categorizes technical and soft skills, structures employment chronologies, parses academic degrees, and classifies the profile into a technical domain archetype.
4. The structured output is validated and written to data/output/nlp/<candidate_id>_nlp.json.

### Stage 4: Candidate Ranking & Fit Scoring

1. The ranking engine loads the target job description and parses required skills, preferred skills, and minimum tenure requirements.
2. Each candidate profile is evaluated across five criteria: Skills Match (35%), Experience Relevance (25%), Education Fit (15%), Projects (15%), and Domain Alignment (10%).
3. If user-configured weights do not sum to 100%, the engine dynamically normalizes each weight proportionately.
4. Knockout filters evaluate candidate tenure and mandatory skills. Candidates failing minimum criteria are flagged with knockout disqualifications.
5. Composite fit scores (0 to 100) are computed. Candidates are assigned to recruitment tiers (Strong Match, Potential Match, Review Required, Unmatched), and qualitative strength/gap summaries are generated.
6. The evaluated leaderboard is saved to data/output/ranking/ranking_scores_<job_id>.json.

### Stage 5: Interview Scheduling & Calendar Synchronization

1. The scheduling engine isolates the top N candidates from the ranking leaderboard, bypassing knocked-out applicants.
2. The scheduler generates sequential interview slots across working weekdays within configured working hours (e.g., 09:00 to 18:00), factoring in duration and buffer spacing.
3. If Google Calendar integration is active, the engine queries the recruiter's calendar via the FreeBusy API to detect conflicting events and selects only unoccupied time windows.
4. For each candidate, the system generates a secure access token (e.g., T_1792180299_151492) stored in interview_tokens, creates an RFC 5545 .ics calendar invite, and dispatches a confirmation email via SMTP STARTTLS.
5. Schedule records are saved to data/output/scheduling/schedules_<job_id>.json and persisted in the schedules table.

### Stage 6: The Candidate Interview Assessment

1. The candidate opens their invitation link (https://<host-ip>:5000/candidate-interview/<token>) in their web browser.
2. The server validates the token against expiration and verifies it has not already been used.
3. The candidate accepts proctoring consent and completes webcam and microphone hardware verification checks.
4. The interview commences: the server serves questions sequentially based on role blueprints (technical vs. non-technical).
5. The candidate provides answers by typing into the response box or speaking verbally via browser speech recognition.
6. The server monitors elapsed response time. When time expires, or when the candidate clicks Submit, the response is committed to the database.
7. If an answer is identified as ambiguous or superficial, the engine dynamically injects a targeted follow-up probing question.

### Stage 7: Real-Time Proctoring & Integrity Monitoring

1. Throughout the interview, the candidate portal analyzes the webcam video feed using Google MediaPipe Face Mesh (with OpenCV Haar cascade fallback).
2. The proctoring engine monitors five anomaly classes: face absence, multiple faces, window focus loss / tab switching, clipboard paste attempts, and question timeouts.
3. Detected anomalies are transmitted to /api/interview/proctor-event and logged to the interview session record in SQLite.
4. At interview conclusion, an overall Proctoring Integrity Score (0 to 100) is calculated, and the session is classified as Clean, Low Warning, or High Risk.

### Stage 8: Interview Evaluation & Report Generation

1. The evaluation engine analyzes the complete interview transcript across four rubric dimensions: Technical Accuracy, Communication Clarity, Problem-Solving Depth, and Behavioral Alignment (each scored 0 to 10).
2. The system computes the final Combined Fit Score:
   - Combined Score = (Resume Fit Score multiplied by 0.40) plus (Interview Score multiplied by 0.60).
3. The FPDF2 report engine compiles a multi-page PDF evaluation report containing executive scorecards, rubric bar charts, proctoring violation logs, full interview transcripts, recruiter notes, and final hiring recommendations.
4. The report is saved to data/output/reports/report_<candidate_id>.pdf, a desktop pop-up notification is triggered for the HR manager, and an unread alert is added to the in-app notification tray.

---

## 5. Recruiter Notes, Triage Tags & Candidate Management

### 5.1 In-Place Recruiter Annotations

Recruiters can record contextual notes directly on candidate records from the ranking leaderboard:
- Storage: Persisted in the candidate_notes table in SQLite.
- Content: Supports free-form text annotations, including candidate salary expectations, notice period constraints, specific portfolio highlights, and interview impressions.
- Persistence: Notes remain linked to the candidate across all pipeline stages, survive application restarts, and are embedded into the final PDF evaluation report.

### 5.2 Workflow Triage Tags

Candidates can be assigned standardized workflow tags to manage pipeline progression:
- Shortlisted: Candidate has passed initial screening and is queued for scheduling.
- On Hold: Candidate meets qualifications but is held in reserve pending other candidate evaluations.
- Follow Up: Requires recruiter action (e.g., verifying references, requesting portfolio links).
- Interviewed: Candidate has completed the technical interview assessment.
- Rejected: Candidate disqualified based on knockout rules or interview performance.

### 5.3 GDPR Right to Erasure (Candidate Data Purging)

To comply with data protection regulations (GDPR, CCPA), the platform provides an automated one-click candidate purge function:
- Trigger: Recruiter clicks the Purge Candidate button or dispatches an authenticated HTTP DELETE request to /api/candidate/<id>/purge.
- Automated Cleanup Actions:
  1. Deletes candidate records from the candidates table.
  2. Deletes associated notes from candidate_notes.
  3. Deletes interview sessions and transcripts from interview_sessions.
  4. Deletes active tokens from interview_tokens.
  5. Deletes vector representations from candidate_embeddings.
  6. Deletes candidate feedback records from candidate_feedback.
  7. Removes notification entries from hr_notifications.
  8. Unlinks and deletes all associated physical files from disk: original resume (.pdf/.docx), extracted plaintext (.txt), structured NLP JSON, and compiled PDF reports.

---

## 6. Talent Intelligence & Advanced Analytics Manual

### 6.1 Vector Semantic Search Engine

- Vector Model: 384-dimensional dense semantic vectors generated from candidate competencies, project descriptions, and experience histories.
- Database Indexing: Stored in the candidate_embeddings table in SQLite.
- Search Interface: Recruiters enter natural language search queries in the Talent Intelligence dashboard.
- Mathematical Matching: The query is converted into an embedding and evaluated against stored candidate vectors using cosine similarity mathematics executed directly inside SQLite query routines:
  - Cosine Similarity = Dot Product of Vectors divided by the Product of Vector Magnitudes.
- Output: Returns a ranked list of candidate profiles matching the semantic intent of the query, complete with similarity percentage scores.

### 6.2 Candidate Comparison Matrix

- Purpose: Enables side-by-side comparative analysis of up to 4 shortlisted candidates simultaneously.
- Matrix Attributes Contrasted:
  - Total years of professional experience.
  - Required skills match percentage.
  - Individual criteria scores (Skills, Experience, Education, Projects, Domain).
  - Live interview performance ratings.
  - Proctoring integrity risk classifications.
  - Key technical strengths and identified gaps.
- Rationale: Assists hiring managers in resolving close hiring decisions by highlighting trade-offs between candidates (e.g., higher technical accuracy vs. superior communication clarity).

### 6.3 Automated Candidate Feedback Letters

- Purpose: Generates constructive, personalized post-interview feedback letters for candidates.
- Structure:
  - Formal greeting and appreciation for candidate participation.
  - Highlighted commendations celebrating specific strengths observed during the resume evaluation and interview.
  - Constructive recommendations outlining specific technical topics, architectural patterns, or methodologies suggested for further study.
- Generation Logic: Dispatches an AI prompt analyzing candidate strengths and gaps, enforcing an encouraging, professional, and actionable tone free of generic rejection templates.

### 6.4 The Six Visual Talent Analytics Modules

1. **Skill Supply vs. Demand Gap Analytics:**
   - Visual Representation: Side-by-side comparative bar chart.
   - Data Source: Required skills from job_templates versus skills extracted across all candidate profiles in candidates.
   - Recruiter Value: Identifies skill surpluses (e.g., 90% of applicants have Python) versus talent bottlenecks (e.g., only 5% possess Docker or Kubernetes), warning recruiters if job descriptions are unrealistically restrictive.

2. **Experience vs. Score Quadrant Matrix:**
   - Visual Representation: Four-quadrant scatter matrix plotting Total Years of Experience (X-axis) against Composite Fit Score (Y-axis).
   - Quadrant Breakdown:
     - Upper-Left (Rising Stars): Low experience, high fit score. Highlights junior talent outperforming senior applicants.
     - Upper-Right (Seasoned Veterans): High experience, high fit score. Experienced professionals directly matching requirements.
     - Lower-Left (Entry Level / Needs Preparation): Low experience, low fit score. Junior applicants requiring foundational development.
     - Lower-Right (Mismatched Experience): High experience, low fit score. Senior applicants whose legacy technical stack does not align with modern role tools.

3. **Interview Question Difficulty Breakdown:**
   - Visual Representation: Ranked horizontal bar chart displaying average candidate score (0 to 10) and average response latency per interview topic.
   - Recruiter Value: Identifies filter questions that effectively differentiate top performers from average applicants, and flags ambiguous questions that are consistently misunderstood.

4. **Proctoring Integrity & Risk Breakdown:**
   - Visual Representation: Doughnut chart showing pool-wide distribution of Clean, Low Warning, and High Risk sessions, paired with categorical violation bars (tab switches, face absences, multiple faces, timeouts).
   - Recruiter Value: Provides department leadership with an instant audit of assessment integrity across the entire applicant batch.

5. **Hiring Velocity & Pipeline Bottleneck Tracker:**
   - Visual Representation: Milestone timeline card displaying elapsed hours and minutes between pipeline stages:
     - Average Time to Screen: Resume upload to ranking completion.
     - Average Candidate Turnaround: Interview invitation dispatch to candidate interview completion.
     - Average Time to Report: Interview completion to final compiled PDF report generation.
   - Recruiter Value: Pinpoints administrative delays and candidate responsiveness bottlenecks.

6. **Education & Domain Talent Mix Demographics:**
   - Visual Representation: Dual progress-bar / doughnut charts displaying aggregate candidate distributions across academic degrees (Bachelor's, Master's, Doctorate, Diploma) and technical domains (Software Development, DevOps, Cloud Engineering, Data Science).
   - Recruiter Value: Provides executive snapshots of applicant pool diversity and background for workforce planning.

---

## 7. Air-Gapped Offline Infrastructure Guide

The application is engineered to operate in secure, air-gapped corporate intranets without outbound internet access:

### 7.1 Zero Outbound CDN Architecture

- Traditional web applications rely on remote Content Delivery Networks (CDNs) for fonts and JavaScript libraries.
- The AI Recruitment System bundles all frontend dependencies locally in app/static/.
- Template Verification: An automated audit verifies that no external script tags (<script src="https://...">) or remote stylesheet links (<link href="https://...">) exist in any HTML template.
- Network Behavior: The application makes zero outbound HTTP/HTTPS requests to external hosts when running in Privacy Mode.

### 7.2 Bundled Local Typography Assets

All application fonts are stored locally and loaded via standard CSS @font-face rules:
- Inter Font Family: Regular (400), Medium (500), SemiBold (600), and Bold (700) weights located in app/static/fonts/inter/. Used for all user interface prose, headings, cards, and buttons.
- JetBrains Mono Font Family: Regular monospace font located in app/static/fonts/jetbrains-mono/. Used for technical tokens, hashes, session identifiers, and code elements.

### 7.3 Bundled Chart.js Data Visualization Library

- The charting library powering all six talent intelligence analytics widgets, candidate scorecards, and proctoring distributions is stored locally at app/static/js/chart.umd.min.js.
- License: Permissive open-source MIT license.
- Execution: Canvas-based client rendering running entirely within the local browser runtime without external telemetry.

### 7.4 On-Device Large Language Model Inference (Ollama)

When configured in Privacy Mode, all natural language processing, question generation, and transcript scoring run locally:
- Daemon Endpoint: http://localhost:11434.
- Default Model: llama3.2:3b.
- Execution Architecture: Runs on local CPU or GPU hardware via the Ollama server.
- Confidentiality: Zero candidate text, resume contents, or interview transcripts leave the physical workstation.

---

## 8. AI Provider Configuration & Management Manual

### 8.1 Dual Operation Modes

- **Cloud Mode (APP_MODE = "cloud"):** Routes AI requests through the ProviderRouter across enabled cloud providers using round-robin load balancing and automatic rate-limit tracking.
- **Privacy Mode (APP_MODE = "privacy"):** Routes all AI requests directly to the local Ollama server on the host machine. Operates 100% offline.

### 8.2 The ProviderRouter Architecture

In Cloud Mode, the ProviderRouter subsystem in src/provider_router.py coordinates request execution:
1. Filters enabled providers that possess valid, non-placeholder API keys.
2. Tracks request timestamps per provider over sliding 60-second windows to calculate Requests Per Minute (RPM).
3. If an enabled provider reaches its RPM threshold, the router automatically skips it and routes the request to the next available provider.
4. If a provider returns an HTTP 429 (Rate Limit) or HTTP 500 (Service Error), the router catches the exception and immediately retries the prompt against an alternate provider.
5. If Ollama times out in Privacy Mode and CLOUD_ENABLED is set to True, the system falls back to Anthropic Claude as a secondary failover.

### 8.3 Dynamic Provider Model Discovery

Rather than relying on hardcoded model lists that become obsolete:
- Recruiters paste an API key in Settings and click the Load button.
- The system dispatches a secure request to /api/provider-models.
- The backend queries the provider's official model catalog API (e.g., querying NVIDIA's /v1/models endpoint) and returns all active models available on that account.
- Model selection dropdowns populate dynamically with live model IDs.

### 8.4 Supported AI Providers Directory

1. **NVIDIA NIM:**
   - Provider URL: https://integrate.api.nvidia.com/v1
   - Key Format: Begins with nvapi-
   - Default Model: meta/llama-3.1-8b-instruct
   - Free Tier Limit: Approximately 10 RPM per model.
   - Recommended Models: meta/llama-3.1-8b-instruct, meta/llama-3.1-70b-instruct, nvidia/llama-3.1-nemotron-70b-instruct.

2. **Anthropic (Claude):**
   - Provider URL: https://api.anthropic.com/v1
   - Key Format: Begins with sk-ant-
   - Default Model: claude-3-5-haiku-latest
   - Recommended Models: claude-3-5-haiku-latest, claude-3-5-sonnet-latest.

3. **Google Gemini:**
   - Provider URL: https://generativelanguage.googleapis.com/v1beta
   - Key Format: Begins with AIza
   - Default Model: gemini-1.5-flash
   - Free Tier Limit: 15 RPM.
   - Recommended Models: gemini-1.5-flash, gemini-1.5-pro.

4. **Groq:**
   - Provider URL: https://api.groq.com/openai/v1
   - Key Format: Begins with gsk_
   - Default Model: llama3-8b-8192
   - Free Tier Limit: 30 RPM.
   - Recommended Models: llama3-8b-8192, llama-3.1-70b-versatile.

5. **OpenAI:**
   - Provider URL: https://api.openai.com/v1
   - Key Format: Begins with sk-
   - Default Model: gpt-4o-mini
   - Recommended Models: gpt-4o-mini, gpt-4o.

6. **OpenRouter:**
   - Provider URL: https://openrouter.ai/api/v1
   - Key Format: Begins with sk-or-
   - Default Model: meta-llama/llama-3.1-8b-instruct:free
   - Provides access to multiple open-source and commercial models.

7. **GitHub Models:**
   - Provider URL: https://models.inference.ai.azure.com
   - Key Format: GitHub Personal Access Token beginning with ghp_
   - Default Model: gpt-4o-mini

8. **Local Ollama:**
   - Provider URL: http://localhost:11434
   - Key Format: None required (Local connection)
   - Default Model: llama3.2:3b
   - Recommended Models: llama3.2:3b (low RAM), llama3.1:8b (balanced), llama3.1:70b (high capability).

---

## 9. Google Calendar & Email Setup Manual

### 9.1 Google Calendar OAuth 2.0 Integration

Connecting Google Calendar enables automated free/busy conflict checking and automatic interview event creation:

1. Create a Google Cloud Project in the Google Cloud Console (console.cloud.google.com).
2. Enable the Google Calendar API under APIs & Services.
3. Configure the OAuth Consent Screen (User Type: External, enter Application Name and Support Email).
4. Create an OAuth Client ID under Credentials (Application Type: Desktop App).
5. Download the client secrets JSON file, rename it to credentials.json, and place it in %LOCALAPPDATA%\AI Recruitment System\data\credentials.json.
6. When scheduling runs for the first time, the application opens a local browser window to authorize calendar access.
7. Upon successful authentication, Google returns access and refresh tokens saved to data/token.json. Future calendar operations reuse this token file automatically.

### 9.2 SMTP Email Configuration

The system uses Python's smtplib with mandatory STARTTLS encryption to dispatch invitation emails:

- **SMTP Host:** Outgoing mail server (e.g., smtp.gmail.com, smtp-mail.outlook.com, smtp.mail.yahoo.com).
- **SMTP Port:** Standard port 587 (STARTTLS).
- **Sender Email:** The email address from which candidate invitations originate.
- **Password:** Email account password or dedicated App Password.
  - Gmail: Requires a 16-character App Password generated from myaccount.google.com/apppasswords with 2-Step Verification enabled.
  - Microsoft Outlook / 365: Requires Authenticated SMTP enabled in the Microsoft 365 Admin Center.
  - Yahoo Mail: Requires an App Password generated under account security settings.
- **Display Name & Company:** Recruiter name and corporate entity displayed in invitation emails.
- **Testing the Connection:** Recruiters can verify server credentials by clicking the Test Connection button in Settings.

### 9.3 Email Template Customization

Recruiters can customize invitation email subjects and bodies using dynamic interpolation tags:
- {candidate_name}: Candidate's extracted full name.
- {job_title}: Role title from the scheduling run.
- {selected_slot}: Formatted interview date and time (e.g., Wednesday, August 20 2026 at 10:00 AM).
- {hr_name}: Recruiter or hiring manager display name.
- {company}: Company or organization name.
- {interview_link}: Unique candidate interview portal link (e.g., https://192.168.1.100:5000/candidate-interview/T_1792180299_151492).
- The email is dispatched as a multi-part MIME payload containing both plain text and styled HTML versions, complete with an attached RFC 5545 .ics calendar file.

---

## 10. Relational Database Reference Manual

The application data layer is managed through SQLite (ars.db) in %LOCALAPPDATA%\AI Recruitment System\data\ars.db. The schema consists of 13 relational tables:

### 10.1 Table: pipeline_runs
Tracks pipeline execution batches.
- run_id (TEXT, Primary Key): Unique batch identifier (e.g., RUN_20261019_001).
- run_ts (TEXT, Not Null): ISO 8601 creation timestamp.
- job_title (TEXT, Not Null): Evaluated job title.
- candidate_count (INTEGER, Default 0): Total resumes processed.
- status (TEXT, Default 'Pending'): Batch status (Pending, Running, Completed, Failed).
- error_msg (TEXT, Nullable): Diagnostic error string if failed.

### 10.2 Table: candidates
Stores candidate profile records, contact data, and fit scores.
- candidate_id (TEXT, Primary Key): Unique candidate identifier.
- run_id (TEXT, Foreign Key referencing pipeline_runs.run_id): Pipeline run reference.
- full_name (TEXT, Not Null): Candidate full name.
- email (TEXT, Nullable): Primary email address.
- phone (TEXT, Nullable): Telephone contact number.
- resume_filename (TEXT, Not Null): Uploaded resume filename.
- total_experience_years (REAL, Default 0.0): Calculated professional tenure in years.
- domain (TEXT, Nullable): Classified technical domain specialization.
- fit_score (REAL, Default 0.0): Composite resume fit score (0 to 100).
- skills_json (TEXT, Nullable): Serialized JSON array of extracted technical and soft skills.
- profile_json (TEXT, Nullable): Complete serialized JSON candidate profile.
- created_at (TEXT, Not Null): ISO 8601 creation timestamp.

### 10.3 Table: schedules
Stores allocated candidate interview calendar slots.
- schedule_id (TEXT, Primary Key): Unique schedule record identifier.
- candidate_id (TEXT, Foreign Key referencing candidates.candidate_id): Candidate reference.
- job_title (TEXT, Not Null): Target role title.
- slot_start (TEXT, Not Null): ISO 8601 interview start timestamp.
- slot_end (TEXT, Not Null): ISO 8601 interview end timestamp.
- ics_path (TEXT, Nullable): Path to generated .ics calendar file on disk.
- gcal_event_id (TEXT, Nullable): Google Calendar remote event identifier.
- status (TEXT, Default 'Scheduled'): Slot status (Scheduled, Confirmed, Completed, Cancelled).
- created_at (TEXT, Not Null): ISO 8601 creation timestamp.

### 10.4 Table: email_log
Maintains an audit trail of all outbound SMTP messages.
- email_id (TEXT, Primary Key): Unique email event identifier.
- recipient (TEXT, Not Null): Recipient email address.
- subject (TEXT, Not Null): Message subject string.
- body_snippet (TEXT, Nullable): Truncated preview of sent message text.
- status (TEXT, Default 'Sent'): Delivery status (Sent, Failed, Queued).
- error (TEXT, Nullable): SMTP diagnostic error string if failed.
- sent_at (TEXT, Not Null): ISO 8601 dispatch timestamp.

### 10.5 Table: interview_tokens
Manages single-use authentication tokens for the candidate assessment portal.
- token (TEXT, Primary Key): Unique random token string (e.g., T_1792180299_151492).
- candidate_id (TEXT, Foreign Key referencing candidates.candidate_id): Candidate reference.
- role (TEXT, Not Null): Target role title for question blueprints.
- expires_at (TEXT, Not Null): ISO 8601 token expiration timestamp.
- created_at (TEXT, Not Null): ISO 8601 token generation timestamp.
- used (INTEGER, Default 0): Binary session usage flag (0 = unused, 1 = session initiated).

### 10.6 Table: job_templates
Stores job description templates and evaluation rubrics.
- template_id (TEXT, Primary Key): Unique template identifier.
- title (TEXT, Not Null): Target job role title.
- domain (TEXT, Nullable): Role domain archetype.
- description (TEXT, Not Null): Complete job description text.
- required_skills (TEXT, Nullable): Comma-delimited or JSON string of mandatory skills.
- preferred_skills (TEXT, Nullable): Comma-delimited or JSON string of optional skills.
- min_experience_years (REAL, Default 0.0): Tenure knockout threshold.
- created_at (TEXT, Not Null): ISO 8601 creation timestamp.

### 10.7 Table: app_settings
Key-value storage for application configurations and encrypted secrets.
- key (TEXT, Primary Key): Configuration setting key string.
- value (TEXT, Nullable): Stored value string (plaintext or encrypted ciphertext).
- is_encrypted (INTEGER, Default 0): Binary encryption flag (1 if encrypted via AES-Fernet).
- updated_at (TEXT, Not Null): ISO 8601 update timestamp.

### 10.8 Table: interview_sessions
Captures interview execution transcripts, proctoring metrics, and evaluations.
- session_id (TEXT, Primary Key): Unique interview session identifier.
- token (TEXT, Foreign Key referencing interview_tokens.token): Access token reference.
- candidate_id (TEXT, Foreign Key referencing candidates.candidate_id): Candidate reference.
- transcript_json (TEXT, Nullable): Serialized JSON transcript of questions and responses.
- proctor_data_json (TEXT, Nullable): Serialized JSON log of proctoring events and violations.
- interview_score (REAL, Default 0.0): Evaluated interview performance score (0 to 100).
- combined_score (REAL, Default 0.0): Final combined fit score (40% resume + 60% interview).
- status (TEXT, Default 'In_Progress'): Session state (In_Progress, Completed, Terminated).
- created_at (TEXT, Not Null): ISO 8601 session start timestamp.
- completed_at (TEXT, Nullable): ISO 8601 session completion timestamp.

### 10.9 Table: candidate_embeddings
Stores 384-dimensional dense semantic vector representations for vector search.
- candidate_id (TEXT, Primary Key, Foreign Key referencing candidates.candidate_id): Candidate reference.
- embedding_json (TEXT, Not Null): Serialized JSON array of 384 floating-point coordinates.
- indexed_at (TEXT, Not Null): ISO 8601 indexing timestamp.

### 10.10 Table: ai_telemetry
Tracks operational telemetry, latency, and token consumption for AI invocations.
- telemetry_id (TEXT, Primary Key): Unique telemetry record identifier.
- provider (TEXT, Not Null): Name of the AI provider called (e.g., nvidia, groq, ollama).
- model (TEXT, Not Null): Specific model identifier called.
- prompt_tokens (INTEGER, Default 0): Estimated or reported prompt token count.
- completion_tokens (INTEGER, Default 0): Estimated or reported completion token count.
- latency_ms (INTEGER, Default 0): Execution duration in milliseconds.
- success (INTEGER, Default 1): Binary success flag.
- created_at (TEXT, Not Null): ISO 8601 timestamp.

### 10.11 Table: candidate_feedback
Stores AI-generated personalized candidate feedback letters.
- feedback_id (TEXT, Primary Key): Unique feedback record identifier.
- candidate_id (TEXT, Foreign Key referencing candidates.candidate_id): Candidate reference.
- feedback_text (TEXT, Not Null): Complete personalized feedback letter text.
- created_at (TEXT, Not Null): ISO 8601 generation timestamp.

### 10.12 Table: candidate_notes
Stores recruiter annotations, notes, and workflow triage tags.
- note_id (TEXT, Primary Key): Unique note identifier.
- candidate_id (TEXT, Foreign Key referencing candidates.candidate_id): Candidate reference.
- note_text (TEXT, Nullable): Recruiter notes and comments.
- tag (TEXT, Nullable): Workflow triage tag (e.g., Shortlisted, Hold, Follow Up, Rejected).
- updated_at (TEXT, Not Null): ISO 8601 timestamp.

### 10.13 Table: hr_notifications
Stores real-time candidate interview completion alerts.
- notification_id (TEXT, Primary Key): Unique notification identifier.
- candidate_id (TEXT, Foreign Key referencing candidates.candidate_id): Candidate reference.
- event_type (TEXT, Not Null): Event category string (e.g., interview_completed).
- message (TEXT, Not Null): Human-readable alert notification text.
- is_read (INTEGER, Default 0): Binary read status flag (0 = unread, 1 = read).
- created_at (TEXT, Not Null): ISO 8601 creation timestamp.

---

## 11. Complete REST API Reference Manual

### 11.1 Administrative Dashboard Endpoints (Port 5001)

- **GET /**
  - Purpose: Renders the primary pipeline dashboard.
  - Authentication: Desktop Session.
  - Response: HTML page displaying pipeline stage cards, SSE log console, and batch controls.

- **GET /ranking**
  - Purpose: Renders the candidate leaderboard.
  - Authentication: Desktop Session.
  - Response: HTML page containing ranked candidate table, criteria breakdown, and notes modals.

- **GET /scheduling**
  - Purpose: Renders the interview scheduling timetable.
  - Authentication: Desktop Session.
  - Response: HTML page displaying candidate shortlist and allocated calendar slots.

- **GET /reports**
  - Purpose: Renders the evaluation reports catalog.
  - Authentication: Desktop Session.
  - Response: HTML page containing completed report cards and in-app PDF previewer.

- **GET /talent-intelligence**
  - Purpose: Renders the talent intelligence suite.
  - Authentication: Desktop Session.
  - Response: HTML page rendering semantic search, comparison matrix, and 6 talent analytics charts.

- **GET /settings**
  - Purpose: Renders the system configuration hub.
  - Authentication: Desktop Session.
  - Response: HTML page displaying AI provider cards, interview timer inputs, scoring weight sliders, and email configuration forms.

### 11.2 Pipeline Execution & Data Management Endpoints

- **POST /api/run-auto-pipeline**
  - Purpose: Triggers end-to-end execution of all pipeline stages.
  - Headers: X-CSRF-Token required.
  - Response: JSON object with success status and execution batch ID.

- **POST /api/reset-pipeline**
  - Purpose: Cleans up runtime output directories (txt, nlp, ranking, scheduling, reports) while preserving database settings.
  - Headers: X-CSRF-Token required.
  - Response: JSON object with success confirmation.

- **GET /api/pipeline-status**
  - Purpose: Polling endpoint returning active execution progress.
  - Authentication: Desktop Session.
  - Response: JSON object containing current stage string, percent complete integer, and execution state.

- **GET /api/logs/stream**
  - Purpose: Server-Sent Events (SSE) log stream.
  - Authentication: Desktop Session.
  - Response: Text event stream (text/event-stream) pushing live server log entries to the UI console.

- **POST /api/open-output-folder**
  - Purpose: Launches Windows Explorer to view the runtime output directory.
  - Headers: X-CSRF-Token required.
  - Response: JSON object confirming shell execution.

- **GET /api/ranking/export/csv**
  - Purpose: Streams candidate leaderboard as an RFC 4180 CSV spreadsheet.
  - Authentication: Desktop Session.
  - Response: File stream (text/csv) with Content-Disposition header triggering browser download.

- **GET /api/candidate/<candidate_id>/notes**
  - Purpose: Retrieves recruiter notes and triage tags for a specific candidate.
  - Authentication: Desktop Session.
  - Response: JSON object containing note_text string and tag string.

- **POST /api/candidate/<candidate_id>/notes**
  - Purpose: Saves or updates recruiter notes and triage tags.
  - Headers: X-CSRF-Token required.
  - Request Body: JSON object containing note_text and tag strings.
  - Response: JSON object confirming database persistence.

- **DELETE /api/candidate/<candidate_id>/purge**
  - Purpose: Permanently deletes all candidate PII, database records, and disk files (GDPR purge).
  - Headers: X-CSRF-Token required.
  - Response: JSON object detailing count of deleted records and unlinked files.

### 11.3 Talent Intelligence & Analytics Endpoints

- **POST /api/intelligence/search**
  - Purpose: Executes natural language vector semantic search across candidate embeddings.
  - Headers: X-CSRF-Token required.
  - Request Body: JSON object with query string and optional top_k integer limit.
  - Response: JSON array of candidate objects with similarity scores and profile summaries.

- **POST /api/intelligence/compare**
  - Purpose: Generates a side-by-side comparative matrix for up to 4 candidates.
  - Headers: X-CSRF-Token required.
  - Request Body: JSON object with candidate_ids array.
  - Response: JSON object containing comparative metrics across scores, experience, skills, and pros/cons.

- **GET /api/intelligence/feedback/<candidate_id>**
  - Purpose: Retrieves or generates a personalized candidate feedback letter.
  - Authentication: Desktop Session.
  - Response: JSON object with feedback_text string.

- **GET /api/intelligence/analytics**
  - Purpose: Computes aggregate metrics for all six talent analytics visual widgets.
  - Authentication: Desktop Session.
  - Response: JSON object containing data structures for skill gaps, experience quadrant, question difficulty, proctoring risks, hiring velocity, and education demographics.

### 11.4 Settings & Provider Management Endpoints

- **POST /api/settings/save**
  - Purpose: Updates application settings, weights, timers, and encrypts sensitive keys.
  - Headers: X-CSRF-Token required.
  - Request Body: Form or JSON object containing settings key-value pairs.
  - Response: JSON object confirming settings persistence.

- **POST /api/provider-models**
  - Purpose: Queries a remote AI provider endpoint to fetch available live models.
  - Headers: X-CSRF-Token required.
  - Request Body: JSON object with provider string and api_key string.
  - Response: JSON object containing models array.

- **POST /api/email/test**
  - Purpose: Tests SMTP server authentication without sending an email.
  - Headers: X-CSRF-Token required.
  - Response: JSON object with boolean success flag and diagnostic message string.

- **GET /api/notifications**
  - Purpose: Retrieves recent HR interview completion notifications.
  - Authentication: Desktop Session.
  - Response: JSON object containing notifications array and unread_count integer.

- **POST /api/notifications/mark-read**
  - Purpose: Marks notifications as read.
  - Headers: X-CSRF-Token required.
  - Request Body: JSON object with notification_ids array or all flag.
  - Response: JSON object confirming status update.

### 11.5 Public Candidate Interview Portal Endpoints (Port 5000)

- **GET /candidate-interview/<token>**
  - Purpose: Renders the candidate interview portal.
  - Authentication: Valid, unexpired interview token in path.
  - Response: HTML page providing candidate onboarding, device permissions, and question workspace.

- **POST /api/interview/start**
  - Purpose: Initializes an active interview session and burns the token.
  - Request Body: JSON object with token string.
  - Response: JSON object returning session_id string, question 1 details, and timer allowance.

- **GET /api/interview/question**
  - Purpose: Retrieves the active question for a session.
  - Parameters: token query parameter.
  - Response: JSON object containing question text, sequence index, total questions, and timer limit.

- **POST /api/interview/answer**
  - Purpose: Submits a candidate answer and records elapsed response time.
  - Request Body: JSON object with token, answer_text, and elapsed_seconds.
  - Response: JSON object confirming answer recording and returning next question (or follow-up probe).

- **POST /api/interview/proctor-event**
  - Purpose: Logs a real-time proctoring anomaly detected on the candidate device.
  - Request Body: JSON object with token, event_type (tab_switch, face_absence, multiple_faces, paste_attempt, timeout), and details string.
  - Response: JSON object acknowledging event logging.

- **POST /api/interview/finish**
  - Purpose: Concludes the interview session, triggers scoring, generates PDF report, and alerts HR.
  - Request Body: JSON object with token string.
  - Response: JSON object returning interview conclusion acknowledgment.

---

## 12. Security, Cryptography & Privacy Manual

### 12.1 Hardware-Bound AES-Fernet Encryption at Rest

Sensitive configuration keys—such as AI provider API keys, SMTP credentials, and Google OAuth tokens—are encrypted within SQLite using AES-128-CBC with PKCS7 padding and HMAC-SHA256 authentication:
- Machine-Specific Key Derivation: Cryptographic keys are derived dynamically using PBKDF2 with HMAC-SHA256 across 100,000 iterations.
- Hardware Binding: The key derivation inputs combine a persistent 16-byte random salt stored in .secret_salt with the host computer's unique hardware Machine GUID (queried from Windows Registry at HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Cryptography\MachineGuid).
- Portability Protection: If an unauthorized party copies ars.db to another computer, encrypted secrets cannot be decrypted because the hardware Machine GUID will not match, preventing credential theft from offline database backups.

### 12.2 Scoped Cross-Site Request Forgery (CSRF) Protection

- All state-modifying administrative HTTP endpoints (POST, PUT, DELETE) require a valid cryptographic CSRF token.
- Tokens are bound to the active user session and verified using constant-time string comparison algorithms to prevent timing attacks.
- Requests lacking a valid token are rejected with HTTP 403 Forbidden.

### 12.3 Sliding Window Rate Limiting

- The candidate portal incorporates an in-memory sliding-window IP rate limiter restricting clients to a maximum of 60 requests per minute per IP address.
- Defends against denial-of-service attempts and rapid automated answer submission attacks.
- Excessive requests trigger HTTP 429 Too Many Requests responses.

### 12.4 Loopback Desktop Nonces

- Upon startup, the pywebview desktop launcher generates a high-entropy single-use cryptographic token passed into the native window.
- The desktop interface injects this nonce during initial session establishment.
- Incoming HTTP requests to Port 5001 lacking a valid session cookie or matching nonce are rejected with HTTP 403 Forbidden, preventing unauthorized local applications from tampering with the administrative API.

### 12.5 XML Prompt Injection Containment Boundaries

- Resume content parsed by large language models is encapsulated inside strict XML delimiter blocks (<resume_text>...</resume_text>).
- System prompts instruct models to treat all internal content strictly as passive data and ignore any commands attempting to reset system instructions, alter scoring rubrics, or bypass knockout criteria.

---

## 13. Operational Troubleshooting & Diagnostics Manual

### 13.1 Resume Ingestion & Parsing Issues

- **Symptom: Candidate resume extracted text is completely empty.**
  - Diagnosis: The resume is a scanned image or photo PDF lacking a digital text layer, and Tesseract OCR was unable to locate binary dependencies.
  - Resolution: Verify that models/Tesseract-OCR/tesseract.exe exists in the installation directory. Ensure that poppler binaries (for pdf2image) are accessible on the system PATH.

- **Symptom: Word (.docx) upload is rejected with HTTP 400.**
  - Diagnosis: The uploaded file has a .docx extension but contains invalid binary headers, or is an older legacy binary Word format (.doc).
  - Resolution: The ingestion engine supports modern Office Open XML documents (.docx). Convert legacy .doc files to .docx in Microsoft Word or LibreOffice prior to uploading.

- **Symptom: Upload fails with HTTP 413 Payload Too Large.**
  - Diagnosis: The uploaded file exceeds the 16 MB size threshold.
  - Resolution: Compress embedded high-resolution images within the resume document to reduce total file size below 16 MB.

### 13.2 AI Provider & Model Issues

- **Symptom: Error message "No cloud providers are enabled".**
  - Diagnosis: System is running in Cloud Mode, but no providers are toggled on, or all enabled providers have placeholder keys (e.g., nvapi-...).
  - Resolution: Open Settings → AI Providers. Enable at least one provider (e.g., NVIDIA, Groq, Gemini) and paste a valid API key. Click Save Settings.

- **Symptom: Provider returns HTTP 429 Rate Limit.**
  - Diagnosis: You have exceeded the provider's free-tier Requests Per Minute limit.
  - Resolution: The ProviderRouter automatically attempts failover to other enabled providers. To prevent throttling, enable multiple cloud providers in Settings to allow the router to spread extraction requests across providers.

- **Symptom: Provider returns HTTP 404 Model Not Found.**
  - Diagnosis: The selected model identifier has been deprecated by the provider or is a vision-only model (e.g., nvidia/neva-22b) that does not support text completions.
  - Resolution: In Settings, click Load on the provider card to retrieve the live model list, and select a standard text instruction model (such as meta/llama-3.1-8b-instruct).

- **Symptom: Ollama fails to respond in Privacy Mode.**
  - Diagnosis: The Ollama background service is not running, or the requested model has not been downloaded.
  - Resolution: Open a terminal and run ollama serve. Verify that the configured model is installed by running ollama list. If missing, download it via ollama pull llama3.2:3b.

### 13.3 Network, TLS & Candidate Portal Issues

- **Symptom: Candidate cannot connect to the interview URL on the local network.**
  - Diagnosis: Windows Defender Firewall is blocking inbound connections on TCP Port 5000, or the host machine's IP address changed.
  - Resolution: Run scripts/setup_firewall.bat as Administrator to open Port 5000 in Windows Firewall. Run ipconfig in Command Prompt to confirm the current LAN IPv4 address.

- **Symptom: Browser displays "Your connection is not private" (SSL Warning).**
  - Diagnosis: The candidate portal uses an auto-generated self-signed TLS certificate (cert.pem).
  - Resolution: This is expected behavior for local network servers. Instruct the candidate to click Advanced → Proceed to [IP Address] (unsafe) to continue to the interview portal.

- **Symptom: Candidate webcam or microphone fails to load.**
  - Diagnosis: The candidate's browser blocked media permissions, or another application (such as Zoom or Teams) is locking the webcam hardware.
  - Resolution: Instruct the candidate to close competing video applications, click the camera icon in their browser address bar, and grant permission to allow camera and microphone access.

### 13.4 Email & Calendar Issues

- **Symptom: SMTP connection fails with (535, 'Authentication failed').**
  - Diagnosis: Incorrect username or password. For Gmail, this indicates the user entered their Google account password instead of an App Password.
  - Resolution: Generate a 16-character App Password at myaccount.google.com/apppasswords and paste it into the Password field in Settings → Email.

- **Symptom: Google Calendar returns HttpError 403 Caller does not have permission.**
  - Diagnosis: The Google Calendar API is not enabled in the Google Cloud Project.
  - Resolution: Go to console.cloud.google.com → APIs & Services → Library, search for Google Calendar API, and click Enable.

---

## 14. Quality Assurance, Test Suite & Maintenance Manual

### 14.1 Test Suite Structure

The test suite consists of 14 domain-scoped modules covering 140 automated tests:

| Test Module | Domain Coverage |
|---|---|
| test_airgap.py | Verifies local existence of Inter and JetBrains Mono fonts, local Chart.js bundle, and audits templates for zero CDN links. |
| test_api.py | Tests all administrative routes, CSRF token validation, candidate notes and tags, CSV export, and error handling. |
| test_auth.py | Tests user authentication, password hashing, session management, rate limiting, and desktop nonces. |
| test_db.py | Tests SQLite initialization, schema creation for all 13 tables, migration scripts, and transactional CRUD logic. |
| test_intelligence.py | Tests vector search cosine similarity math, candidate comparison matrix, feedback letters, and 6 analytics calculators. |
| test_interview.py | Tests token validation, question generation, role blueprints, timers, adaptive follow-up probing, and transcripts. |
| test_nlp.py | Tests regex heuristic pre-parsing, contact extraction, skills taxonomy classification, and JSON normalization. |
| test_proctor.py | Tests proctoring anomaly detection algorithms, tab switch tracking, webcam face counting, and integrity scoring. |
| test_ranking.py | Tests 5-criterion fit scoring math, dynamic weight normalization, tenure knockouts, and mandatory skill checks. |
| test_reports.py | Tests FPDF2 PDF generation, Latin-1 character sanitization, 40/60 combined fit scoring, and report layouts. |
| test_resume.py | Tests document parsing across digital PDFs, python-docx Word documents, Tesseract OCR text recovery, and corrupt files. |
| test_schedule.py | Tests shortlist isolation, timetable slot generation, iCalendar (.ics) syntax, and SMTP dispatch routines. |
| test_security.py | Tests AES-Fernet hardware-bound encryption, machine GUID salt mixing, sensitive configuration protection, and GDPR purge. |
| test_voice.py | Tests offline speech recognition and synthesis fallbacks, audio buffers, and Vosk model discovery. |

### 14.2 Test Execution Metrics

- Automated Tests: 140 tests.
- Pass Rate: 100% (140 passed in approximately 34 seconds).
- Code Quality: Clean static analysis under Ruff linter rules with zero formatting or linting errors.

---

## 15. Building, Packaging & Windows Deployment Manual

### 15.1 PyInstaller Standalone Compilation

The application is compiled into a standalone Windows directory distribution using PyInstaller:
- Spec File: build/build.spec.
- Packaging Mode: Onedir mode (bundles Python runtime, compiled C-extensions, and dependencies into dist/ARS/).
- Bundled Binaries & Models:
  - Tesseract-OCR/ binary distribution and English language traineddata.
  - Vosk speech recognition model (vosk-model-small-en-in-0.4).
  - Pre-compiled OpenCV and MediaPipe vision binaries.
- Bundled Static Assets:
  - HTML templates (app/templates/).
  - Static styles, local fonts, and bundled Chart.js (app/static/).

### 15.2 Inno Setup Windows Installer Creation

The compiled PyInstaller distribution is wrapped into a standard Windows installer using Inno Setup 6:
- Script File: build/installer.iss.
- Generated Executable: installer_output/ARS_Setup_1.0.exe.
- Installation Directory: C:\Program Files\AI Recruitment System\.
- System Integration:
  - Creates Start Menu shortcuts and optional desktop icons.
  - Registers an uninstaller in Windows Add or Remove Programs.
  - Preserves User Data: Uninstalling the software leaves the %LOCALAPPDATA%\AI Recruitment System\ directory intact to safeguard settings, resumes, and candidate databases during application updates.

### 15.3 Windows Firewall Configuration

To allow candidates to connect to the interview portal on Port 5000:
- Helper Script: scripts/setup_firewall.bat.
- Configuration: Adds an inbound TCP firewall rule to Windows Defender Firewall allowing incoming traffic on Port 5000 across private and domain network profiles.

---

## 16. Master Settings & Tuning Reference Index

The application stores dynamic configuration keys in the app_settings table in SQLite, accessible at runtime via config/__init__.py:

| Setting Key | Default Value | Value Type | Encrypted | Operational Impact |
|---|---|---|---|---|
| APP_MODE | 'cloud' | String | No | Toggles between 'cloud' (ProviderRouter) and 'privacy' (Local Ollama). |
| OLLAMA_BASE_URL | 'http://localhost:11434' | String | No | Endpoint URL for the on-device Ollama daemon. |
| OLLAMA_MODEL | 'llama3.2:3b' | String | No | Model tag used for local on-device inference. |
| NVIDIA_ENABLED | True | Boolean | No | Toggles NVIDIA NIM cloud provider in ProviderRouter pool. |
| NVIDIA_KEY | '' | String | Yes | API authentication key for NVIDIA NIM catalog. |
| NVIDIA_MODEL | 'meta/llama-3.1-8b-instruct' | String | No | Active model tag for NVIDIA inference. |
| GROQ_ENABLED | False | Boolean | No | Toggles Groq provider in ProviderRouter pool. |
| GROQ_KEY | '' | String | Yes | API authentication key for Groq Cloud. |
| GROQ_MODEL | 'llama3-8b-8192' | String | No | Active model tag for Groq inference. |
| GEMINI_ENABLED | False | Boolean | No | Toggles Google Gemini in ProviderRouter pool. |
| GEMINI_KEY | '' | String | Yes | API key for Google AI Studio / Gemini API. |
| GEMINI_MODEL | 'gemini-1.5-flash' | String | No | Active model tag for Gemini inference. |
| ANTHROPIC_ENABLED | False | Boolean | No | Toggles Anthropic Claude in ProviderRouter pool. |
| ANTHROPIC_KEY | '' | String | Yes | API key for Anthropic Claude console. |
| ANTHROPIC_MODEL | 'claude-3-5-haiku-latest' | String | No | Active model tag for Anthropic inference. |
| OPENAI_ENABLED | False | Boolean | No | Toggles OpenAI GPT in ProviderRouter pool. |
| OPENAI_KEY | '' | String | Yes | API key for OpenAI platform. |
| OPENAI_MODEL | 'gpt-4o-mini' | String | No | Active model tag for OpenAI inference. |
| OPENROUTER_ENABLED | False | Boolean | No | Toggles OpenRouter gateway in ProviderRouter pool. |
| OPENROUTER_KEY | '' | String | Yes | API key for OpenRouter gateway. |
| OPENROUTER_MODEL | 'meta-llama/llama-3.1-8b-instruct:free' | String | No | Active model tag for OpenRouter inference. |
| GITHUB_ENABLED | False | Boolean | No | Toggles GitHub Models in ProviderRouter pool. |
| GITHUB_TOKEN | '' | String | Yes | GitHub Personal Access Token with model scope. |
| GITHUB_MODEL | 'gpt-4o-mini' | String | No | Active model tag for GitHub Models inference. |
| SMTP_HOST | '' | String | No | Outgoing SMTP mail server hostname. |
| SMTP_PORT | 587 | Integer | No | Outgoing SMTP port (587 STARTTLS). |
| SMTP_EMAIL | '' | String | No | Sender email address for interview invitations. |
| SMTP_PASSWORD | '' | String | Yes | Sender email account password or app password. |
| HR_NAME | 'HR Manager' | String | No | Recruiter / hiring manager display name in emails. |
| COMPANY_NAME | 'Our Company' | String | No | Organization name shown in emails and reports. |
| INTERVIEW_TECH_QUESTIONS | 5 | Integer | No | Number of technical questions generated per interview (3–10). |
| INTERVIEW_BEHAVIORAL_QUESTIONS | 3 | Integer | No | Number of behavioral questions generated per interview (1–5). |
| INTERVIEW_TIME_LIMIT | 120 | Integer | No | Per-question timer limit in seconds (60, 90, 120, 180). |
| WEIGHT_SKILLS | 35 | Integer | No | Weight assigned to Skills Match criterion in ranking. |
| WEIGHT_EXPERIENCE | 25 | Integer | No | Weight assigned to Experience Relevance criterion. |
| WEIGHT_EDUCATION | 15 | Integer | No | Weight assigned to Education Fit criterion. |
| WEIGHT_PROJECTS | 15 | Integer | No | Weight assigned to Projects & Practical Work criterion. |
| WEIGHT_DOMAIN | 10 | Integer | No | Weight assigned to Domain Alignment criterion. |
| MIN_EXPERIENCE_YEARS | 0.0 | Float | No | Experience knockout threshold in years (0.0 = disabled). |
| SHORTLIST_TOP_N | 5 | Integer | No | Number of top candidates shortlisted for interview scheduling. |

---

## 17. Complete Codebase Directory & File Inventory

### 17.1 Root Entrypoints & Configuration
- main.py: Application entry point; initializes database, boots Waitress and Flask servers, launches native pywebview desktop container.
- pyproject.toml: Project package specification, dependency tree, version declaration (3.0.0), and Ruff/pytest tool configurations.
- config/__init__.py: Dynamic database-backed configuration module providing runtime access to all app_settings.

### 17.2 Application Core & Utilities (app/)
- app/__init__.py: Flask application factory (create_app); mounts blueprints, configures error handlers, registers static asset routes.
- app/core.py: Thread-safe log queue and Server-Sent Events (SSE) streaming infrastructure.
- app/database.py: Relational database layer; SQLite connection lifecycle, schema initialization DDL for all 13 tables, and transactional CRUD helper functions.
- app/folder_opener.py: Cross-platform utility invoking the native operating system shell to reveal files in Windows File Explorer.
- app/rate_limiter.py: In-memory sliding-window IP rate limiting middleware.
- app/utils.py: Security decorators (login_required, csrf_protect), IP network resolution, and session helpers.

### 17.3 Application Route Handlers (app/routes/)
- app/routes/api.py: Primary administrative API routes (pipeline execution, candidate notes, CSV export, output folders).
- app/routes/auth.py: Authentication routes (login, logout, session verification, CSRF token generation).
- app/routes/candidate.py: Public candidate interview portal routes on Port 5000 (interview flows, device checks, proctoring events).
- app/routes/intelligence.py: Talent Intelligence API routes (vector search, candidate comparison, feedback letter generation, 6 analytics modules).
- app/routes/reports.py: PDF report viewing, metadata inspection, and streaming routes.
- app/routes/settings.py: System configuration, AI provider management, email verification, and dynamic model discovery routes.
- app/routes/views.py: Front-end page rendering routes for the desktop dashboard.

### 17.4 Pipeline Processing Modules (src/)
- src/common.py: Core paths resolver, centralized AI dispatcher (call_ollama), atomic file write utilities, and JSON parsers.
- src/ai_mode.py: Provider registry and execution mode selector.
- src/provider_router.py: Multi-provider router with RPM rate-limit tracking, round-robin load balancing, and automatic failover.
- src/security.py: Hardware-bound AES-Fernet encryption at rest, PBKDF2 key derivation, sensitive key lists, and GDPR candidate purging.
- src/pdf_to_txt.py: Resume ingestion and text extraction (digital PDF, Word .docx, scanned OCR).
- src/txt_to_nlp.py: Natural language processing and structured JSON candidate profile extraction.
- src/rank_candidates.py: Multi-criteria fit scoring, knockout filtering, weight normalization, and leaderboard generation.
- src/schedule_candidates.py: Top-N shortlist isolation, timetable slot allocation, and iCalendar generation.
- src/email_sender.py: Automated SMTP email dispatch with STARTTLS encryption and custom template interpolation.
- src/google_calendar.py: Google Calendar API OAuth 2.0 integration and free/busy slot detection.
- src/generate_questions.py: Dynamic interview question generation with role blueprints and adaptive follow-up probing.
- src/proctoring.py: Real-time computer vision proctoring engine (MediaPipe, OpenCV) and anomaly scoring.
- src/voice_system.py: Offline text-to-speech and speech-to-text fallback engine.
- src/evaluate_interview.py: Interview transcript evaluation, rubric scoring, and 40/60 combined fit scoring.
- src/generate_reports.py: Standardized PDF evaluation report generation using FPDF2.
- src/talent_intelligence.py: Vector semantic embeddings, comparison matrix, and 6 talent analytics calculators.

### 17.5 User Interface Assets (app/templates/ & app/static/)
- app/templates/base.html: Master administrative layout with navigation sidebar, status trays, and notification badges.
- app/templates/dashboard.html: Pipeline execution console, progress meters, and live SSE log stream.
- app/templates/ranking.html: Ranked candidate leaderboard, criteria breakdown, notes modal, and CSV export.
- app/templates/scheduling.html: Interview timetable, calendar slot view, and email dispatch controls.
- app/templates/interview.html: Candidate interview portal, video proctoring feed, timers, and question flow.
- app/templates/reports.html: Evaluation reports catalog, combined score summaries, and PDF viewer.
- app/templates/intelligence.html: Talent intelligence suite, semantic search interface, and visual analytics dashboards.
- app/templates/settings.html: Configuration controls, AI provider manager, scoring weights, and question parameters.
- app/static/css/styles.css: Complete design system styles, CSS custom properties, and responsive layout rules.
- app/static/fonts/inter/: Local Inter font files (Regular, Medium, SemiBold, Bold).
- app/static/fonts/jetbrains-mono/: Local JetBrains Mono font files.
- app/static/js/chart.umd.min.js: Bundled offline Chart.js library.

### 17.6 Automated Test Suite (tests/)
- tests/conftest.py: Shared pytest fixtures, temporary directories, database mock factories, and sample data.
- tests/test_airgap.py: Air-gapped offline compliance verification.
- tests/test_api.py: Administrative API route tests.
- tests/test_auth.py: Authentication and session security tests.
- tests/test_db.py: Database schema and transactional CRUD tests.
- tests/test_intelligence.py: Talent intelligence, vector search, and analytics tests.
- tests/test_interview.py: Interview flow, question generation, and timer tests.
- tests/test_nlp.py: NLP profile extraction and schema tests.
- tests/test_proctor.py: Computer vision proctoring and violation detection tests.
- tests/test_ranking.py: Fit scoring, weight normalization, and knockout tests.
- tests/test_reports.py: PDF report compilation and Latin-1 encoding tests.
- tests/test_resume.py: Document parsing (PDF, DOCX, OCR) tests.
- tests/test_schedule.py: Scheduling, calendar sync, and email dispatch tests.
- tests/test_security.py: Cryptography, encryption at rest, and GDPR purge tests.
- tests/test_voice.py: Offline speech recognition and synthesis tests.

### 17.7 Build & Deployment Scripts (build/ & scripts/)
- build/build.spec: PyInstaller compilation specification.
- build/installer.iss: Inno Setup Windows installer build script.
- scripts/build_installer.bat: Automated batch script orchestrating PyInstaller and Inno Setup builds.
- scripts/setup_firewall.bat: Windows firewall helper script configuring Port 5000 inbound access.
- scripts/verify_providers.py: Standalone diagnostic utility testing connectivity across all configured AI providers.
