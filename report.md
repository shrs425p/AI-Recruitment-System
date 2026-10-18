# AI Recruitment System — Comprehensive System Report

## 1. Executive Summary and System Mission

The AI Recruitment System (ARS) is an offline-capable, privacy-first desktop application designed to automate and orchestrate the complete technical recruitment pipeline. The system provides hiring managers and recruitment teams with automated capabilities across the talent lifecycle:

- Ingestion and text parsing of resumes in digital, scanned, and word processor formats.
- Natural language extraction of candidate attributes, competencies, and career histories into a structured JSON schema.
- Algorithmic candidate ranking and knockout filtering against customized job descriptions.
- Manual and automated calendar slot scheduling with Google Calendar synchronization and email notifications.
- Execution of token-authenticated, proctored candidate interviews via a dedicated local-network HTTPS portal.
- Real-time computer vision proctoring and behavior integrity tracking.
- Combined fit scoring synthesizing resume credentials with dynamic interview transcript performance.
- Generation of detailed, standardized PDF evaluation reports.
- Advanced talent intelligence, vector semantic search, candidate comparison, and six visual talent analytics modules.
- Complete air-gapped operation with zero external CDN dependencies, bundled typography, local charting libraries, and on-device machine learning inference.

The application operates as an offline-first desktop solution where all sensitive data—including candidate contact details, resumes, evaluation transcripts, and API credentials—remains under the direct ownership of the operating organization.

---

## 2. System Architecture and Topology

### Two-Server Architectural Separation

The platform utilizes a strict two-server network model that segregates administrative control from candidate interview interactions.

1. **Internal Desktop HR Application Server:**
   - Host Binding: Local loopback address (127.0.0.1) on Port 5001.
   - WSGI Server: Waitress WSGI application server.
   - Access Scope: Restricted strictly to the local machine hosting the software. Outside devices on the local area network cannot establish connections to this port.
   - UI Delivery: Rendered within a native desktop window container via pywebview.

2. **Candidate Interview Portal Server:**
   - Host Binding: All network interfaces (0.0.0.0) on Port 5000.
   - Transport Security: HTTPS with auto-generated self-signed TLS certificates (2048-bit RSA key and X.509 certificate).
   - Access Scope: Reachable by candidates over the local area network (LAN) or secure VPN tunnel.
   - Route Boundary: Only serves candidate interview routes (/candidate-interview and related endpoints). All administrative, pipeline execution, settings, and reporting routes are strictly blocked on this server.

### Native Desktop Window Container (pywebview)

Rather than requiring recruitment staff to manage web server terminals and external browser tabs, the system wraps the administrative interface in a native operating system window powered by pywebview.

- Window Configuration: Native borders, customizable title bar, minimum dimensions of 1200 by 800 pixels.
- Session Isolation: Uses dedicated WebView2 (Chromium-based) storage partitions to avoid interference with the user's personal browser data or cookies.
- Single-Use Nonce Authentication: The desktop launcher injects a single-use cryptographic token during initialization to automatically authenticate the native desktop session without exposing administrative credentials over the loopback network.

### Runtime Storage and Path Resolution Topology

The application enforces a clean separation between the static application installation directory (which may reside in read-only directories such as Program Files) and mutable runtime data.

All runtime databases, uploaded resumes, parsed outputs, cryptographic salts, and logs are resolved dynamically to the operating system's local application data repository:

- Windows Path: %LOCALAPPDATA%\AI Recruitment System\
- Canonical Structure:
  - data/ars.db: The primary SQLite relational database.
  - data/resumes/: Storage directory for uploaded candidate resume files.
  - data/credentials.json: Google Calendar OAuth client credentials.
  - data/token.json: Google Calendar OAuth refresh and access tokens.
  - data/output/txt/: Plaintext documents extracted from raw resumes.
  - data/output/nlp/: Structured candidate profile JSON and text summaries.
  - data/output/ranking/: Evaluated candidate scorecards and ranked leaderboards.
  - data/output/scheduling/: Generated interview timetables and iCalendar files.
  - data/output/interviews/: Transcripts, proctoring logs, and candidate responses.
  - data/output/reports/: Compiled PDF evaluation reports and report JSONs.
  - data/output/ssl/: Auto-generated TLS certificates and private keys.
  - .secret_salt: 16-byte cryptographic salt used for hardware-bound key derivation.
  - crash.log: Operating system diagnostic dump generated on unhandled runtime termination.

---

## 3. Document Ingestion and Optical Character Recognition

### Supported File Formats

The ingestion engine processes incoming candidate application documents across four standard formats:
- Portable Document Format (.pdf): Digital vector-based documents and raster-scanned documents.
- Microsoft Word Document (.docx): Office Open XML zipped document packages.
- Portable Network Graphics (.png): High-resolution document scans and screenshots.
- Joint Photographic Experts Group (.jpg, .jpeg): Photo-scanned resumes and mobile uploads.

### Word Document Parsing Engine (python-docx)

Word documents (.docx) are parsed natively using python-docx to extract hierarchical text without external format conversion:
- Extracts structural paragraph elements and runs.
- Traverses embedded tables row-by-row and cell-by-cell to capture tabular layout data such as employment history and education tables.
- Strips non-printable XML control characters while preserving sentence and paragraph boundaries.
- Employs streaming file handles to avoid loading entire binary file payloads into unmanaged memory.

### Digital PDF Parsing Engine (pypdf)

For PDF files, the system first attempts direct text layer extraction:
- Uses pypdf stream decoders to extract character maps, text blocks, and line structures.
- Detects whether a PDF contains an active digital text stream or consists solely of embedded bitmap images.
- Implements a density threshold heuristic: if the total extracted character count falls below 50 characters or averages fewer than 10 characters per page, the document is automatically flagged as scanned and routed to the OCR engine.

### Optical Character Recognition Subsystem (Tesseract OCR)

For scanned PDFs and image uploads (.png, .jpg), the system invokes an offline OCR processing pipeline:
- Engine: Bundled Google Tesseract OCR 5.3 engine stored locally within the models/Tesseract-OCR/ directory.
- Preprocessing: Converts images to grayscale, applies Otsu automatic thresholding for binarization, and performs morphological deskewing via OpenCV.
- Page Segmentation: Uses Page Segmentation Mode 3 (Fully automatic page segmentation without OSD) to parse multi-column resume layouts.
- Language Models: Bundled English language training data (eng.traineddata) ensuring full offline execution without remote API reliance.

### Input Sanitization and Security Guardrails

To prevent malicious uploads from compromising the host server:
- Filename Sanitization: All filenames are stripped of path traversal sequences (such as ../ and ..\\), control characters, and non-ASCII glyphs.
- Collision Avoidance: Colliding filenames receive timestamped unique suffixes rather than overwriting existing records.
- Size Limitation: Enforces a strict upload limit of 16 megabytes per file; files exceeding this threshold are rejected at the HTTP gateway with status code 413.
- Magic Byte Verification: File formats are verified against underlying binary signatures rather than trusting client-provided file extensions.

---

## 4. Structured Natural Language Processing (NLP) & Profile Extraction

### Two-Stage Profile Extraction Architecture

Transforming unstructured resume text into a normalized candidate profile involves a two-stage hybrid approach combining deterministic heuristic parsing with large language model extraction.

1. **Deterministic Pre-Parsing:**
   - Evaluates regular expression patterns to extract common contact markers (email addresses, phone numbers, URLs, GitHub handles, LinkedIn profiles).
   - Detects standard resume section headers (Experience, Education, Skills, Projects, Certifications) to establish document offsets.

2. **Large Language Model Structural Transformation:**
   - Feeds the raw text into the configured AI provider using a strict, comprehensive JSON schema.
   - Parses complex work timelines, maps synonymous technologies, and synthesizes career accomplishments.
   - Temperature is locked at 0.0 to ensure deterministic, reproducible extraction across runs.

### Candidate Profile Attributes Schema

The extraction subsystem normalizes candidate information into the following structured components:

- **Personal Information:**
  - Candidate Full Name
  - Primary Contact Email Address
  - Telephone Number (normalized to international formats where applicable)
  - Geographic Location (City, State, Country)
  - Portfolio, GitHub, and LinkedIn Uniform Resource Identifiers (URIs)

- **Skills Taxonomy:**
  - Technical Skills: Programming languages, frameworks, developer tools, cloud infrastructure platforms, databases, libraries.
  - Soft Skills: Leadership, verbal and written communication, stakeholder management, problem solving, agile collaboration.

- **Professional Experience:**
  - Job Title / Role
  - Employing Organization / Company Name
  - Start Date and End Date (normalized to standard calendar dates or 'Present')
  - Total Duration: Computed tenure in months and years.
  - Core Responsibilities and Achievements: Quantifiable accomplishments and bulleted project summaries.

- **Educational Background:**
  - Degree Conferred (e.g., Bachelor of Science, Master of Technology)
  - Field of Study / Academic Major (e.g., Computer Science, Electrical Engineering)
  - Educational Institution / University Name
  - Graduation Year / Attendance Period
  - Academic Score / Cumulative Grade Point Average (where reported)

- **Projects & Open Source Contributions:**
  - Project Title
  - Applied Technologies and Tooling
  - Project Description and Quantifiable Metrics
  - Repository / Live Demonstration Link

- **Certifications & Professional Licenses:**
  - Certification Title
  - Issuing Body / Vendor (e.g., AWS, Microsoft, Google Cloud)
  - Issue Date and Expiration Date

- **Domain Categorization:**
  - Categorizes the profile into an industry archetype (e.g., Backend Engineering, Frontend Development, Full Stack Development, DevOps/SRE, Data Science, Machine Learning, Cloud Architecture, Mobile Development, Security Engineering).

### Prompt Engineering and Injection Containment

To prevent malicious resume text from executing prompt injection attacks (such as instructions attempting to override scoring rubrics):
- Candidate text is encapsulated within strict XML boundaries (<resume_text>...</resume_text>).
- System prompts explicitly direct the model to treat all text within the XML block purely as data and to ignore any meta-instructions, role assignments, or prompt override attempts contained inside the resume.
- JSON output parsing applies strict schema validation; unexpected attributes or malformed responses trigger automated cleanup and schema enforcement routines.

---

## 5. Candidate Ranking, Scoring & Knockout Rules

### Multi-Criteria Fit Scoring Architecture

Candidate ranking evaluates candidate profiles against a target job description using five distinct evaluation criteria. Each criterion is evaluated on a normalized scale of 0 to 100, which is then multiplied by an assigned weight:

1. **Skills Match Score (Default Weight: 35%):**
   - Assesses the coverage of required and preferred skills specified in the job description against the technical and soft skills extracted from the candidate resume.
   - Evaluates synonymous technologies (e.g., recognizing that proficiency in PostgreSQL satisfies relational database requirements).

2. **Experience Relevance Score (Default Weight: 25%):**
   - Evaluates the total career tenure alongside the direct relevance of past job titles, seniority levels, and responsibilities to the target position.

3. **Education Fit Score (Default Weight: 15%):**
   - Compares the candidate's degree level, major, and institutional background against the job description's academic requirements.

4. **Projects & Practical Work Score (Default Weight: 15%):**
   - Evaluates personal projects, open-source work, and practical implementations demonstrating applied capability with the target stack.

5. **Domain Alignment Score (Default Weight: 10%):**
   - Measures candidate familiarity with industry-specific methodologies, business logic, architectural patterns, and domain contexts.

### Dynamic Weight Normalization

The system allows recruitment operators to adjust criteria weights via the Settings dashboard. To guarantee statistical validity:
- If the sum of user-defined weights does not equal 100%, the scoring engine dynamically normalizes each weight proportionately:
  - Normalized Weight = User Weight divided by Sum of All User Weights.
- The composite Fit Score is calculated as the sum of all normalized weighted criterion scores.

### Automated Knockout Filters

The ranking pipeline incorporates automated knockout filters to triage high-volume applicant pools:
- **Tenure Knockout:** Sets a hard minimum threshold for total professional experience (e.g., minimum 3.0 years). Candidates falling below this threshold are automatically flagged with a knockout disqualification.
- **Mandatory Competency Filter:** Identifies non-negotiable required skills from the job description. Applicants lacking these critical competencies are separated into a disqualified tier regardless of other scores.
- Disqualified candidates are preserved in the database for auditing purposes but are excluded from the interview scheduling shortlist.

### Candidate Tiers and Qualitative Summaries

Based on final composite scores, candidates are grouped into standardized recruitment tiers:
- Tier 1: Strong Match (Composite Score: 85 to 100) — Immediate interview recommendation.
- Tier 2: Potential Match (Composite Score: 70 to 84) — Secondary interview shortlist.
- Tier 3: Review Required (Composite Score: 50 to 69) — Manual recruiter evaluation advised.
- Tier 4: Unmatched (Composite Score: 0 to 49) — Rejection or alternate role pooling.

For every evaluated candidate, the engine generates qualitative bulleted summaries identifying top technical strengths, identified skill or experience gaps, and a concise hiring justification.

### Recruiter Notes and Triage Tagging

Recruiters can enrich candidate records directly from the ranking dashboard:
- In-place text notes allow recruiters to log qualitative observations (e.g., notice period, compensation expectations, specific project nuances).
- Status tags categorize candidate progression (e.g., Shortlisted, On Hold, Interviewed, Rejected, Follow Up).
- Updates are written transactionally to the candidate_notes table in SQLite with immediate synchronization to UI dashboards.

### RFC 4180 Candidate Spreadsheet (CSV/Excel) Export Engine

To support external reporting and legacy ATS ingestion, the ranking subsystem includes a single-click CSV export engine:
- Format: Fully RFC 4180-compliant comma-separated values file.
- Header Structure: Rank, Full Name, Email Address, Composite Fit Score, Skills Match Score, Experience Score, Education Score, Projects Score, Domain Fit Score, Key Strengths, Identified Gaps, Hiring Recommendation.
- Special Character Escaping: Strings containing commas, line breaks, or double quotes are automatically quoted and escaped to prevent spreadsheet formula injection.

---

## 6. Interview Scheduling & Calendar Synchronization

### Top-N Shortlist Allocation

Following candidate ranking, the scheduling stage isolates the top N performing candidates (customizable by the recruiter, defaulting to the top 5 applicants):
- Disqualified candidates are bypassed.
- Tied scores are resolved deterministically using technical skills match as the primary tiebreaker.

### Timetable Generation and Slot Allocation

The system generates structured interview schedules mapping candidates to discrete interview windows:
- Configurable Parameters: Working day start time (e.g., 09:00), end time (e.g., 18:00), interview duration (e.g., 60 minutes), buffer intervals (e.g., 15 minutes), and lookahead horizon (e.g., next 14 calendar days).
- Deterministic Allocation: Allocates slots sequentially across working weekdays, skipping weekends and conflicting appointments.

### Google Calendar API OAuth 2.0 Integration

When connected to Google Cloud:
- Protocol: OAuth 2.0 desktop authorization flow utilizing locally stored credentials.json.
- Scope: Read-write calendar authorization (https://www.googleapis.com/auth/calendar).
- Free/Busy Analysis: The engine queries the recruiter's primary calendar using the FreeBusy query API to detect real-time conflicts and proposes only unoccupied slots.
- Automated Event Dispatch: Once an interview is scheduled, the engine creates an event on the recruiter's Google Calendar with candidate summary details, unique candidate portal links, and automated calendar invitations emailed to the candidate.

### iCalendar (.ics) File Generation

For environments operating without Google Cloud integration:
- Generates standard RFC 5545 iCalendar (.ics) event files for every scheduled session.
- Files include unique UID strings, UTC start/end timestamps, event titles, location URIs, and description summaries.
- Attached automatically to outbound invitation emails, enabling one-click import into Microsoft Outlook, Apple Calendar, and Thunderbird.

### Automated SMTP Dispatch Engine

- Delivery Protocol: Python smtplib with mandatory STARTTLS transport encryption.
- Multi-Part MIME Construction: Delivers both multipart/plain and multipart/html payloads with responsive email layout styling.
- Template Customization: Recruitment operators can customize email templates in the Settings dashboard using dynamic interpolation tags:
  - Candidate Full Name ({candidate_name})
  - Target Job Title ({job_title})
  - Allocated Interview Slot ({selected_slot})
  - Recruiter Name ({hr_name})
  - Company / Organization Name ({company})
  - Unique Candidate Interview Portal Link ({interview_link})

---

## 7. Candidate Interview Portal & Anti-Tampering Engine

### Isolated HTTPS Candidate Portal

The candidate interview portal operates on Port 5000 as an independent web application:
- Accessible across the local area network using the host's IPv4 address.
- Secured using self-signed TLS certificates generated during application setup.
- Enforces an isolated routing boundary: candidate requests cannot traverse or access any administrative routes, ranking databases, or recruiter dashboards.

### Single-Use Token Lifecycle and Session Binding

- Token Generation: When an interview slot is confirmed, the system generates a secure, cryptographically random token (e.g., T_1792180299_151492) stored in the interview_tokens table.
- Validation: When a candidate visits /candidate-interview/<token>, the server verifies:
  1. The token exists in the database.
  2. The token has not expired.
  3. The token has not already been used (used = 0).
- Session Initialization: Upon successful validation, the server creates an active session entry in interview_sessions and marks the token as used, preventing replay attacks or simultaneous sessions.

### Candidate Onboarding and Device Authorization

Prior to beginning the interview:
- The portal presents an informed consent screen outlining the automated AI interview process, data handling policies, and proctoring parameters.
- Hardware Checks: Browser APIs verify access to the candidate's webcam and microphone.
- Verification Preview: Displays a live video feed to confirm camera positioning and audio level indicators to ensure microphone clarity.

### Anti-Tampering and Server Pacing Architecture

To maintain the integrity of automated assessments:
- Server-Controlled Clock: The elapsed time per question is tracked on the server. Client-side timer manipulations cannot extend response allowances.
- Linear Progression: Questions must be answered in strict chronological sequence. Candidates cannot skip ahead, revisit completed questions, or alter submitted transcripts.
- State Persistence: In the event of a momentary network disruption, the candidate's existing progress is maintained in SQLite, allowing resumption within the active session window.

---

## 8. Real-Time Proctoring & Integrity Monitoring

### Dual-Engine Computer Vision Architecture

The interview portal incorporates a computer vision proctoring engine that analyzes webcam video streams directly within the candidate's browser session:

1. **Primary Vision Engine (MediaPipe Face Mesh):**
   - Utilizes Google MediaPipe to track 468 facial landmarks in real time.
   - Monitors facial presence, eye gaze vector estimation, head pose angles (yaw, pitch, roll), and mouth movement during verbal answers.

2. **Fallback Vision Engine (OpenCV Haar Cascade):**
   - In environments where WebGL or hardware acceleration is unavailable, the system automatically falls back to an OpenCV Haar Cascade frontal face detection model (haarcascade_frontalface_default.xml) bundled with the software.

### Proctoring Anomaly Classifications

The proctoring system monitors and logs five specific integrity violations during the interview:

1. **Face Absence Anomaly:**
   - Triggered when no face is detected within the camera frame for more than 3 consecutive seconds.
   - Differentiates between momentary glances and prolonged abandonment of the interview station.

2. **Multiple Faces Anomaly:**
   - Triggered when two or more distinct faces are detected within the camera frame.
   - Identifies unauthorized third-party coaching or collaborative answering attempts.

3. **Window Blur & Tab Switching Anomaly:**
   - Monitors HTML5 Page Visibility APIs and browser window blur events.
   - Logs an immediate violation whenever the candidate leaves the interview tab, opens an external application, minimizes the browser, or switches desktop workspaces.

4. **Clipboard & Copy-Paste Deterrence:**
   - Intercepts and blocks paste events (Ctrl+V, Shift+Insert, right-click paste) within answer input fields.
   - Analyzes keystroke timing dynamics: text strings appearing instantaneously (e.g., 50 words appearing in under 200 milliseconds) are flagged as automated clipboard injections.

5. **Response Timeout Anomaly:**
   - Triggered when the per-question timer expires before the candidate submits an answer.
   - Automatically commits whatever text or audio has been captured and transitions to the subsequent question.

### Proctoring Risk Scoring Formula

At the conclusion of the interview, the proctoring engine aggregates all detected violations into a composite Proctoring Integrity Score (0 to 100):
- Scoring Deductions:
  - Tab Switch / Window Blur: 15 points deducted per occurrence.
  - Multiple Faces Detected: 20 points deducted per occurrence.
  - Extended Face Absence: 10 points deducted per occurrence.
  - Copy-Paste Attempt: 10 points deducted per occurrence.
  - Question Timeout: 5 points deducted per occurrence.
- Risk Classifications:
  - Clean (Score: 90 to 100): Zero to minimal minor flags (e.g., single momentary gaze shift). High integrity confidence.
  - Low Warning (Score: 70 to 89): Occasional minor flags (e.g., 1–2 brief window blurs). Manual transcript review recommended.
  - High Risk (Score: 0 to 69): Multiple severe violations (e.g., persistent tab switching, multiple individuals present, repeated copy-paste injections). Integrity compromised.

---

## 9. Adaptive Interview Execution & Voice System

### Role-Adaptive Question Blueprints

The interview generation engine adapts its questions dynamically based on the target role classification:
- **Technical Role Blueprint:**
  - Coding paradigms, algorithmic efficiency, system design patterns, debugging methodology, API architecture, data storage strategies, cloud infrastructure, and technical trade-off decisions.
- **Non-Technical Role Blueprint:**
  - Stakeholder communication, cross-functional collaboration, conflict resolution, prioritization frameworks, project lifecycle management, leadership scenarios, and organizational problem solving.

### Configurable Question Structure

Recruitment administrators can configure interview parameters in the Settings dashboard:
- Technical Questions Count: Configurable from 3 to 10 questions (default: 5).
- Behavioral Questions Count: Configurable from 1 to 5 questions (default: 3).
- Per-Question Timer Limit: Selectable between 60, 90, 120, or 180 seconds per question (default: 120 seconds).
- Settings are persisted to the app_settings table in SQLite and take effect dynamically across all subsequent interview sessions without restarting the server.

### Dynamic Follow-Up Probing Engine

To prevent shallow or rote answers from passing evaluation:
- The system evaluates candidate responses in real time.
- If an answer is identified as superficial, incomplete, or ambiguous (e.g., answering "I used Docker" without explaining the containerization architecture or deployment strategy), the engine dynamically injects a targeted follow-up probing question:
  - Example: "Could you elaborate on how you configured the networking and persistence volumes for those Docker containers in production?"
- Follow-up questions inherit a proportional time allocation and are recorded as linked sub-items in the final transcript.

### Dual-Layer Voice Subsystem

The candidate portal supports fully conversational voice interviews via speech-to-text and text-to-speech:

1. **Client-Side Speech Processing (HTML5 Web Speech API):**
   - Text-to-Speech (TTS): Uses window.speechSynthesis to vocalize interview questions using natural OS voice synthesis engines.
   - Speech-to-Text (STT): Uses window.SpeechRecognition to transcribe spoken candidate answers in real time directly inside the browser. Operates with zero network latency.

2. **Offline Backend Voice Fallback:**
   - In environments where browser speech APIs are unavailable:
     - Offline TTS: Generates audio waveforms using pyttsx3, saved to temporary WAV buffers.
     - Offline STT: Spoken candidate audio chunks are processed locally using a bundled Vosk speech recognition engine (vosk-model-small-en-in-0.4) located in models/. Operates entirely on CPU without internet access.

---

## 10. Automated Candidate Evaluation & PDF Reporting

### Transcript Scoring Across Dimensions

Upon interview completion, the evaluation engine analyzes the complete transcript across four core dimensions:
1. **Technical Accuracy (0 to 10):** Correctness of technical concepts, frameworks, and architecture explanations.
2. **Communication Clarity (0 to 10):** Structure, conciseness, articulation, and professional delivery of ideas.
3. **Problem-Solving Depth (0 to 10):** Analytical methodology, handling of edge cases, and reasoning around trade-offs.
4. **Behavioral Alignment (0 to 10):** Alignment with organizational values, ownership mindset, and collaborative approach.

### Combined Fit Score Formulation

To produce an objective final hiring index, the system synthesizes pre-interview credentials with live interview performance:
- Formula:
  - Combined Score = (Resume Fit Score multiplied by 0.40) plus (Interview Evaluation Score multiplied by 0.60).
- Rationale: While resume credentials demonstrate foundational skills and career history, verified performance in the live, proctored interview is prioritized at 60% of the final decision metric.

### Standardized PDF Report Generation (FPDF2)

The system generates multi-page evaluation reports in PDF format using the FPDF2 library:
- Visual Design: Follows a clean, monochrome Material Design 3 layout optimized for both screen viewing and black-and-white printing.
- Typography & Encoding: Enforces strict Latin-1 string sanitization to prevent unicode substitution errors or character clipping during rendering.
- Document Sections:
  1. Header: Candidate full name, role title, evaluation timestamp, and unique report identifier.
  2. Executive Scorecard: Resume Fit Score, Interview Score, Combined Fit Score, and Proctoring Integrity Score.
  3. Rubric Matrix: Breakdown of individual scoring dimensions with comparative visual score bars.
  4. Proctoring Summary: Total flagged events, itemized violation tally, and overall risk categorization.
  5. Recruiter Notes: Consolidated notes and tags logged during the evaluation cycle.
  6. Complete Interview Transcript: Chronological transcript displaying each question, the candidate's submitted response, the elapsed response time, and the AI evaluator's per-question feedback.
  7. Final Recommendation: Clear verdict (Hire, Hold, or Reject) with structured qualitative rationale.

---

## 11. Real-Time Notification & Alerting Subsystem

### Desktop Operating System Notifications

When a candidate concludes an interview session on Port 5000, the system immediately alerts recruitment managers working on the desktop:
- Platform: Uses native Windows desktop notification systems (via plyer or native Win32 toast APIs).
- Content: "Candidate Interview Completed — [Candidate Name] has finished their interview for [Job Title]. Evaluation report and transcript are ready for review."
- Execution: Dispatched asynchronously in background worker threads to avoid blocking server operations or user interface interactions.

### Persistent In-App Notification Tray

In addition to desktop pop-ups, notifications are stored permanently in the SQLite database:
- Table: hr_notifications.
- Attributes: Notification identifier, candidate reference, event type, message text, creation timestamp, and read status boolean.
- Dashboard Display: The top navigation bar displays an interactive notification badge showing unread alert counts.
- Interaction: Clicking an alert navigates directly to the candidate's detailed evaluation scorecard and marks the notification as read.

---

## 12. Talent Intelligence & Analytics Engine

The Talent Intelligence suite provides high-level organizational analytics, vector search capabilities, and comparative talent evaluation across applicant batches.

### Vector Semantic Search Engine

- Vector Storage: candidate_embeddings table in SQLite.
- Embedding Generation: Computes 384-dimensional dense semantic vectors representing candidate competencies, experiences, and achievements.
- Search Mechanics: Recruiters can execute natural language semantic queries (e.g., "Find engineers experienced in distributed caching and high-throughput financial transactions").
- Retrieval: Queries are embedded and compared against candidate vectors using cosine similarity mathematics executed directly inside SQLite query routines.

### Candidate Comparison Matrix

- Enables side-by-side comparative analysis of up to 4 shortlisted candidates simultaneously.
- Renders an aligned matrix contrasting:
  - Total years of professional experience.
  - Technical skills overlap against job description requirements.
  - Individual rubric scores (Skills, Experience, Education, Projects, Domain).
  - Live interview performance ratings.
  - Proctoring risk classifications.
  - Highlighted strengths and gaps.

### Automated Candidate Feedback Generation

- Generates personalized, constructive feedback letters for candidates following their assessment.
- Structure:
  - Appreciation for participation.
  - Detailed commendations highlighting technical strengths demonstrated in the resume and interview.
  - Constructive recommendations outlining specific areas for technical growth and deeper study.
- Tone: Professional, objective, encouraging, and free of automated rejection clichés.

### The Six Visual Talent Analytics Modules

The system includes six specialized analytics engines that compute aggregate insights across candidate pools:

1. **Skill Supply vs. Demand Gap Analytics:**
   - Visual Widget: Side-by-side comparative bar chart.
   - Computation: Aggregates mandatory skills from job descriptions and compares them against skill frequencies extracted across the entire candidate resume repository.
   - Recruiter Insight: Highlights candidate surpluses (e.g., "92% of applicants possess Python and Git") versus talent bottlenecks (e.g., "Only 6% of applicants possess Kubernetes or Terraform"), alerting hiring managers if job requirements are unrealistically restrictive.

2. **Experience vs. Score Quadrant Matrix:**
   - Visual Widget: Four-quadrant scatter matrix plotting Total Years of Experience (X-axis) against Composite Fit Score (Y-axis).
   - Quadrant Breakdown:
     - Upper-Left (Rising Stars): Low experience, high fit score. Identifies high-potential junior talent outperforming senior applicants.
     - Upper-Right (Seasoned Veterans): High experience, high fit score. Validated senior talent ready for immediate placement.
     - Lower-Left (Entry Level / Needs Preparation): Low experience, low fit score. Standard junior applicants requiring further development.
     - Lower-Right (Mismatched Experience): High experience, low fit score. Veteran applicants whose career stack fails to align with modern role requirements.

3. **Interview Question Difficulty Breakdown:**
   - Visual Widget: Ranked horizontal bar chart displaying average candidate score (0 to 10) and average response latency per interview topic.
   - Recruiter Insight: Identifies filter questions that effectively separate top candidates from average applicants, while highlighting questions that may be ambiguous or consistently misunderstood.

4. **Proctoring Integrity & Risk Breakdown:**
   - Visual Widget: Tiered integrity distribution chart and violation breakdown visualization.
   - Metrics: Displays pool-wide percentages of Clean, Low Warning, and High Risk sessions, alongside categorical tallies of tab switches, face absences, multiple faces, and timeouts.
   - Recruiter Insight: Allows department heads to assess batch integrity at a glance without manually inspecting dozens of individual proctoring logs.

5. **Hiring Velocity & Pipeline Bottleneck Tracker:**
   - Visual Widget: Sequential pipeline milestone timeline card.
   - Metrics Tracked:
     - Average Time to Screen: Resume upload to ranking completion.
     - Average Candidate Turnaround: Interview invite dispatch to candidate interview completion.
     - Average Time to Final Report: Interview completion to compiled PDF generation.
   - Recruiter Insight: Measures candidate responsiveness and pinpoints operational bottlenecks across recruitment stages.

6. **Education & Domain Talent Mix Demographics:**
   - Visual Widget: Dual doughnut / progress-bar distribution charts.
   - Demographics: Aggregates candidate distribution across educational degree levels (Bachelor's, Master's, Doctorate, Diploma) and primary technical domain classifications (Software Development, DevOps, Cloud Engineering, Data Science).
   - Recruiter Insight: Provides an executive talent pool snapshot for stakeholder reviews and workforce planning.

---

## 13. Completely Air-Gapped Offline Infrastructure

The platform is designed to operate in strict air-gapped, zero-trust network environments without requiring external internet connectivity.

### Zero Outbound CDN Architecture

All frontend styling, interactive behaviors, typography, and charts run completely from local assets:
- No remote script tags (<script src="https://...">) or remote stylesheet links (<link href="https://...">) exist anywhere in the application templates.
- Eliminates tracking risks, external network dependencies, and browser security blocks in air-gapped corporate intranets.

### Bundled Offline Font Assets

Typography is delivered locally via standard TrueType and WOFF2 fonts located in app/static/fonts/:
- Inter Font Family: Regular, Medium, SemiBold, and Bold weights located in app/static/fonts/inter/.
- JetBrains Mono Font Family: Monospace styling for code elements, hashes, and tokens located in app/static/fonts/jetbrains-mono/.
- Fonts are declared via standard local @font-face rules in app/static/css/styles.css.

### Bundled Chart.js Data Visualization Library

All interactive talent analytics charts, quadrant matrices, and score bars are rendered using a locally bundled Chart.js UMD distribution:
- File Location: app/static/js/chart.umd.min.js.
- License: Open-source MIT license.
- Front-End Rendering: Canvas-based rendering executed on the client without external telemetry or remote asset requests.

### Offline Local AI Model Server (Ollama)

When operating in Privacy Mode, all natural language processing, question generation, and candidate evaluations are processed locally:
- Local Host: Connects to an on-device Ollama daemon (http://localhost:11434).
- Default Model: llama3.2:3b (optimized for fast local CPU/GPU execution).
- Data Privacy: Zero candidate data, resume text, or interview transcripts ever egress from the local workstation.

---

## 14. Multi-Provider Artificial Intelligence Subsystem

### Dual Operation Modes

The system provides flexible deployment configurations:

1. **Cloud Mode:** Routes AI requests through cloud API providers, offering high throughput and state-of-the-art model capabilities.
2. **Privacy Mode:** Enforces 100% offline local inference via Ollama, ensuring compliance with strict data sovereignty and confidentiality mandates.

### The Provider Router Architecture

In Cloud Mode, the ProviderRouter subsystem in src/provider_router.py coordinates request dispatch:
- Multi-Provider Support: Manages concurrent connections across up to 8 AI providers.
- Health Monitoring: Skips providers with missing keys, placeholder credentials, or inactive endpoints.
- Rate-Limit Tracking: Tracks request timestamps per provider over sliding 60-second windows. If a provider reaches its RPM limit, requests are routed to alternate enabled providers automatically.
- Automatic Fallback: If a cloud provider encounters an HTTP 429 (Rate Limit) or HTTP 500 (Service Error), the router immediately retries the operation against the next eligible provider in the pool.

### Dynamic Provider Model Catalog

Rather than relying on hardcoded model lists:
- The system queries provider model endpoints dynamically (/api/provider-models).
- Entering an API key and requesting model discovery populates model selection dropdowns with all models currently available under that account (e.g., retrieving NVIDIA's catalog of 80+ active NIM models).

### Supported AI Providers Catalog

1. **NVIDIA NIM:** High-speed inference via NVIDIA API Catalog (Default: meta/llama-3.1-8b-instruct).
2. **Anthropic Claude:** High-reasoning evaluation via Anthropic API (Default: claude-3-5-haiku-latest, claude-3-5-sonnet-latest). Also serves as the automatic cloud fallback if local Ollama encounters execution timeouts.
3. **Google Gemini:** Multimodal and text models via Google AI Studio (Default: gemini-1.5-flash).
4. **Groq:** Ultra-low-latency LPU inference (Default: llama3-8b-8192, llama-3.1-70b-versatile).
5. **OpenAI:** GPT model family (Default: gpt-4o-mini, gpt-4o).
6. **OpenRouter:** Unified gateway aggregating multiple open and proprietary models.
7. **GitHub Models:** Developer tier models accessible via GitHub Personal Access Tokens.
8. **Local Ollama:** On-device local LLM server (Default: llama3.2:3b).

---

## 15. Relational Database Architecture (SQLite Schema)

The persistent data layer is implemented via a SQLite database (ars.db) managed through a custom ORM abstraction layer in app/database.py. The database contains 13 relational tables:

### 1. pipeline_runs
Tracks execution runs of the recruitment pipeline.
- run_id (TEXT, Primary Key): Unique run identifier (e.g., RUN_20261019_001).
- run_ts (TEXT): ISO 8601 creation timestamp.
- job_title (TEXT): Job title evaluated in this pipeline run.
- candidate_count (INTEGER): Total resumes processed.
- status (TEXT): Pipeline state (Pending, Running, Completed, Failed).
- error_msg (TEXT): Diagnostic error string in the event of failure.

### 2. candidates
Stores extracted candidate profiles and evaluated fit scores.
- candidate_id (TEXT, Primary Key): Unique candidate identifier.
- run_id (TEXT, Foreign Key): Reference to the associated pipeline run.
- full_name (TEXT): Candidate full name.
- email (TEXT): Primary contact email address.
- phone (TEXT): Telephone contact number.
- resume_filename (TEXT): Filename of the uploaded resume document.
- total_experience_years (REAL): Computed career tenure in years.
- domain (TEXT): Classified technical domain specialization.
- fit_score (REAL): Composite resume ranking fit score (0 to 100).
- skills_json (TEXT): Serialized JSON array of extracted technical and soft skills.
- profile_json (TEXT): Complete serialized JSON candidate profile.
- created_at (TEXT): ISO 8601 creation timestamp.

### 3. schedules
Stores allocated candidate interview slots.
- schedule_id (TEXT, Primary Key): Unique schedule record identifier.
- candidate_id (TEXT, Foreign Key): Reference to the scheduled candidate.
- job_title (TEXT): Target role title.
- slot_start (TEXT): ISO 8601 interview start time.
- slot_end (TEXT): ISO 8601 interview end time.
- ics_path (TEXT): Filesystem path to the generated .ics calendar file.
- gcal_event_id (TEXT): Remote Google Calendar event identifier.
- status (TEXT): Slot status (Scheduled, Confirmed, Completed, Cancelled).
- created_at (TEXT): ISO 8601 creation timestamp.

### 4. email_log
Maintains an audit log of all outbound SMTP email communications.
- email_id (TEXT, Primary Key): Unique email event identifier.
- recipient (TEXT): Recipient email address.
- subject (TEXT): Message subject header.
- body_snippet (TEXT): First 200 characters of the sent message body.
- status (TEXT): Dispatch status (Sent, Failed, Queued).
- error (TEXT): SMTP error diagnostic string if failed.
- sent_at (TEXT): ISO 8601 dispatch timestamp.

### 5. interview_tokens
Manages access tokens for the candidate interview portal.
- token (TEXT, Primary Key): Unique candidate access token (e.g., T_1792180299_151492).
- candidate_id (TEXT, Foreign Key): Reference to the candidate record.
- role (TEXT): Target job role for question generation.
- expires_at (TEXT): ISO 8601 expiration timestamp.
- created_at (TEXT): ISO 8601 generation timestamp.
- used (INTEGER): Binary flag (0 = unused, 1 = session initiated/used).

### 6. job_templates
Stores job description templates and evaluation rubrics.
- template_id (TEXT, Primary Key): Unique template identifier.
- title (TEXT): Target job role title.
- domain (TEXT): Role domain archetype.
- description (TEXT): Complete job description text.
- required_skills (TEXT): Comma-delimited or JSON string of mandatory skills.
- preferred_skills (TEXT): Comma-delimited or JSON string of optional skills.
- min_experience_years (REAL): Minimum tenure required.
- created_at (TEXT): ISO 8601 creation timestamp.

### 7. app_settings
Key-value storage for application configurations and encrypted secrets.
- key (TEXT, Primary Key): Configuration setting key.
- value (TEXT): Stored value (plaintext or encrypted ciphertext).
- is_encrypted (INTEGER): Binary flag (1 if value is encrypted via AES-Fernet).
- updated_at (TEXT): ISO 8601 update timestamp.

### 8. interview_sessions
Captures interview execution transcripts, proctoring metrics, and evaluations.
- session_id (TEXT, Primary Key): Unique session identifier.
- token (TEXT, Foreign Key): Reference to the authentication token used.
- candidate_id (TEXT, Foreign Key): Reference to the candidate.
- transcript_json (TEXT): Complete serialized JSON transcript of questions and answers.
- proctor_data_json (TEXT): Serialized JSON logs of proctoring events and violations.
- interview_score (REAL): Evaluated interview performance score (0 to 100).
- combined_score (REAL): Composite fit score (40% resume + 60% interview).
- status (TEXT): Session state (In_Progress, Completed, Terminated).
- created_at (TEXT): ISO 8601 session start timestamp.
- completed_at (TEXT): ISO 8601 session completion timestamp.

### 9. candidate_embeddings
Stores dense vector representations for semantic search.
- candidate_id (TEXT, Primary Key): Reference to the candidate.
- embedding_json (TEXT): Serialized 384-dimensional dense vector array.
- indexed_at (TEXT): ISO 8601 indexing timestamp.

### 10. ai_telemetry
Records latency, token consumption, and operational metrics for AI invocations.
- telemetry_id (TEXT, Primary Key): Unique telemetry record identifier.
- provider (TEXT): Name of the AI provider called (e.g., nvidia, groq, ollama).
- model (TEXT): Specific model identifier used.
- prompt_tokens (INTEGER): Estimated or reported prompt token count.
- completion_tokens (INTEGER): Estimated or reported completion token count.
- latency_ms (INTEGER): Execution duration in milliseconds.
- success (INTEGER): Binary success flag.
- created_at (TEXT): ISO 8601 timestamp.

### 11. candidate_feedback
Stores AI-generated candidate feedback letters.
- feedback_id (TEXT, Primary Key): Unique feedback record identifier.
- candidate_id (TEXT, Foreign Key): Reference to the candidate.
- feedback_text (TEXT): Complete candidate feedback letter.
- created_at (TEXT): ISO 8601 generation timestamp.

### 12. candidate_notes
Stores recruiter notes, annotations, and recruitment triage tags.
- note_id (TEXT, Primary Key): Unique note identifier.
- candidate_id (TEXT, Foreign Key): Reference to the candidate.
- note_text (TEXT): Recruiter notes and comments.
- tag (TEXT): Triage tag (e.g., Shortlisted, Hold, Follow Up, Rejected).
- updated_at (TEXT): ISO 8601 timestamp.

### 13. hr_notifications
Stores real-time alerts notifying recruitment staff of interview completions.
- notification_id (TEXT, Primary Key): Unique notification identifier.
- candidate_id (TEXT, Foreign Key): Reference to the candidate who completed the interview.
- event_type (TEXT): Event category (e.g., interview_completed).
- message (TEXT): Human-readable alert notification text.
- is_read (INTEGER): Binary read status flag (0 = unread, 1 = read).
- created_at (TEXT): ISO 8601 creation timestamp.

---

## 16. Application Programming Interface (API) Specification

The system exposes RESTful HTTP endpoints across its administrative and candidate service boundaries:

### Core HR Administrative Endpoints (Port 5001)

- GET /: Renders the primary desktop dashboard interface.
- GET /ranking: Renders the candidate ranking leaderboard and fit scorecards.
- GET /scheduling: Renders the interview scheduling calendar and slot manager.
- GET /reports: Renders the evaluation reports list and PDF viewer interface.
- GET /settings: Renders system configuration, provider setup, and weighting controls.
- GET /talent-intelligence: Renders the Talent Intelligence suite and analytics dashboards.

### Pipeline Execution & Control Endpoints

- POST /api/run-auto-pipeline: Triggers the end-to-end autonomous recruitment pipeline.
- POST /api/reset-pipeline: Clears generated pipeline artifacts while preserving application settings and database configuration.
- GET /api/pipeline-status: Returns real-time execution progress, current stage, and percentage completion.
- GET /api/logs/stream: Server-Sent Events (SSE) stream broadcasting live runtime log output to the desktop console.
- POST /api/open-output-folder: Invokes the operating system shell to open the runtime output directory in Windows File Explorer.

### Candidate Management, Notes & Export Endpoints

- GET /api/ranking/export/csv: Generates and streams an RFC 4180 CSV spreadsheet containing candidate rankings and scores.
- GET /api/candidate/<candidate_id>/notes: Retrieves recruiter notes and triage tags for a specific candidate.
- POST /api/candidate/<candidate_id>/notes: Saves or updates recruiter notes and triage tags in the database.
- DELETE /api/candidate/<candidate_id>/purge: GDPR compliance endpoint; permanently purges all candidate PII, database rows, and filesystem assets.

### Talent Intelligence & Analytics Endpoints

- POST /api/intelligence/search: Executes semantic vector search across candidate embeddings based on natural language queries.
- POST /api/intelligence/compare: Compares up to 4 candidate profiles across scoring dimensions and returns an aligned comparison matrix.
- GET /api/intelligence/feedback/<candidate_id>: Retrieves or generates a personalized candidate feedback letter.
- GET /api/intelligence/analytics: Computes and returns JSON data for all six talent analytics modules (skill gaps, quadrant matrix, question difficulty, proctoring risks, hiring velocity, demographics).

### Settings, Providers & Notifications Endpoints

- POST /api/settings/save: Saves updated application configurations, scoring weights, question limits, and encrypted API keys.
- POST /api/provider-models: Connects to a specified AI provider using supplied credentials and returns the active live model catalog.
- POST /api/email/test: Tests outgoing SMTP connectivity and authentication credentials.
- GET /api/notifications: Retrieves the list of recent HR notifications and unread alert counts.
- POST /api/notifications/mark-read: Updates the read status of all or specified notifications.

### Public Candidate Portal Endpoints (Port 5000)

- GET /candidate-interview/<token>: Validates an interview token, verifies device permissions, and renders the interview interface.
- POST /api/interview/start: Initializes an interview session and marks the token as used.
- GET /api/interview/question: Retrieves the current active interview question, timer limit, and sequence index.
- POST /api/interview/answer: Submits a candidate response, records elapsed response time, and triggers dynamic follow-up analysis.
- POST /api/interview/proctor-event: Logs a real-time proctoring anomaly (e.g., window blur, face absence, multiple faces) to the session record.
- POST /api/interview/finish: Finalizes the interview session, computes final scores, triggers PDF report compilation, and issues an HR desktop notification.

---

## 17. Security, Cryptography & Privacy Safeguards

### Hardware-Bound AES-Fernet Encryption at Rest

Sensitive configurations—including AI provider API keys, SMTP passwords, and Google Calendar tokens—are encrypted at rest within SQLite using AES-128 in Cipher Block Chaining (CBC) mode with PKCS7 padding and HMAC-SHA256 authentication (Fernet specification):
- Key Derivation: Cryptographic keys are derived dynamically using PBKDF2 with HMAC-SHA256 across 100,000 iterations.
- Hardware Binding: The PBKDF2 derivation inputs combine a persistent 16-byte random cryptographic salt stored in .secret_salt with the host workstation's unique hardware machine GUID (queried from Windows Registry at HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Cryptography\MachineGuid).
- Portability Protection: If the database (ars.db) is copied to another physical computer, encrypted secrets cannot be decrypted because the machine GUID will not match, preventing credential exfiltration from offline backups.

### Cryptographic CSRF Protection

To prevent Cross-Site Request Forgery attacks:
- All state-modifying administrative HTTP endpoints (POST, PUT, DELETE) require a valid cryptographic CSRF token.
- Tokens are bound to the active user session and verified using constant-time string comparison algorithms to prevent timing attacks.

### Sliding Window Rate Limiting

The candidate portal incorporates an in-memory sliding-window IP rate limiter:
- Limits requests to a maximum of 60 requests per minute per IP address.
- Defends against denial-of-service attempts and rapid automated answer submission attacks.

### Loopback Single-Use Desktop Nonces

To prevent unauthorized local applications from accessing the desktop HR API on Port 5001:
- The pywebview launcher generates a high-entropy cryptographic nonce on startup.
- The desktop webview injects this nonce into its initial handshake. Requests lacking a valid session cookie or matching nonce are rejected with HTTP 403 Forbidden.

### XML Prompt Injection Containment Boundary

To defend AI parsing modules against adversarial prompt injections embedded within resume text:
- Resume content is encapsulated within strict XML boundaries (<resume_text>...</resume_text>).
- System prompts instruct models to treat all internal content strictly as data and ignore any commands attempting to reset system instructions, alter scoring rubrics, or bypass knockout criteria.

### GDPR Right to Erasure (Candidate Data Purging)

The platform provides full compliance with data protection mandates (GDPR, CCPA) through an automated candidate purge routine:
- When triggered via the dashboard or /api/candidate/<id>/purge:
  1. Deletes the candidate record from candidates.
  2. Deletes all associated notes from candidate_notes.
  3. Deletes session transcripts and proctoring logs from interview_sessions.
  4. Invalidates and deletes authentication tokens from interview_tokens.
  5. Purges semantic vector representations from candidate_embeddings.
  6. Deletes candidate feedback records from candidate_feedback.
  7. Clears notification logs from hr_notifications.
  8. Deletes all associated filesystem assets: original resume (.pdf/.docx), extracted plaintext (.txt), NLP profile (.json), and compiled PDF reports.

---

## 18. Quality Assurance & Automated Test Architecture

### Structural Test Suite Layout

The test suite is structured into 14 domain-scoped modules covering all functional boundaries of the application:

1. **test_airgap.py:** Validates 100% offline air-gapped compliance; verifies local existence of Inter and JetBrains Mono fonts, verifies local Chart.js bundle, and audits all HTML templates to confirm zero external CDN links.
2. **test_api.py:** Exercises all administrative Flask routes, CSRF token validation, candidate notes and tags endpoints, CSV export generation, and error handling.
3. **test_auth.py:** Tests user authentication, password hashing, session management, sliding window rate limiting, and desktop nonce validation.
4. **test_db.py:** Tests SQLite database initialization, table creation across all 13 schemas, migration scripts, transactional integrity, and CRUD operations.
5. **test_intelligence.py:** Tests vector search cosine similarity calculations, candidate comparison matrix generation, AI feedback synthesis, and all six talent analytics calculators.
6. **test_interview.py:** Tests token authentication, role blueprint selection, question limits, per-question timers, adaptive follow-up probing, and transcript persistence.
7. **test_nlp.py:** Tests regular expression heuristic parsing, contact information extraction, skills taxonomy classification, and structured JSON normalization.
8. **test_proctor.py:** Tests proctoring anomaly detection algorithms, tab switch tracking, webcam face count logic, and integrity score deductions.
9. **test_ranking.py:** Tests the 5-criterion fit scoring engine, weight normalization math, tenure knockout filters, and mandatory skill checks.
10. **test_reports.py:** Tests FPDF2 PDF generation, Latin-1 character sanitization, 40/60 combined fit score weighting, and layout rendering.
11. **test_resume.py:** Tests document parsing across digital PDFs, python-docx Word documents, Tesseract OCR text recovery, and corrupt file rejection.
12. **test_schedule.py:** Tests interview slot allocation, lookahead schedule generation, iCalendar (.ics) syntax compliance, and email dispatch routines.
13. **test_security.py:** Tests AES-Fernet hardware-bound encryption, machine GUID salt mixing, sensitive configuration protection, and GDPR candidate purging.
14. **test_voice.py:** Tests speech-to-text and text-to-speech fallbacks, audio buffer processing, and offline Vosk model discovery.

### Automated Test Execution Results

- Total Automated Tests: 140 tests.
- Status: 140 passed (100% pass rate).
- Execution Duration: Approximately 34.17 seconds.
- Static Analysis: Verified with Ruff linter; zero code style or syntax violations.

---

## 19. Packaging, Installation & Windows Deployment

### PyInstaller Packaging Specification

The application is compiled into a standalone Windows distribution using PyInstaller:
- Spec File: build/build.spec.
- Packaging Mode: Onedir mode (bundles Python runtime, compiled C-extensions, and dependencies into dist/ARS/).
- Bundled Binaries:
  - Tesseract-OCR/ binary distribution and English language traineddata.
  - Vosk speech recognition model (vosk-model-small-en-in-0.4).
  - Pre-compiled OpenCV and MediaPipe vision binaries.
- Bundled Static Assets:
  - HTML templates (app/templates/).
  - Static styles, local fonts, and bundled Chart.js (app/static/).

### Inno Setup Windows Installer

The compiled PyInstaller distribution is packaged into a standard Windows installer executable using Inno Setup 6:
- Script File: build/installer.iss.
- Generated Executable: installer_output/ARS_Setup_1.0.exe.
- Installation Directory: C:\Program Files\AI Recruitment System\.
- System Integration:
  - Creates Start Menu shortcuts and optional desktop icons.
  - Registers an uninstaller in Windows Add or Remove Programs.
  - Preserves user data: Uninstalling the software leaves the %LOCALAPPDATA%\AI Recruitment System\ directory intact to safeguard settings, resumes, and candidate databases during application updates.

### Network Firewall Configuration

To permit candidates to access the interview portal on Port 5000:
- Helper Script: scripts/setup_firewall.bat.
- Configuration: Adds an inbound TCP firewall rule to Windows Defender Firewall allowing incoming traffic on Port 5000 across private and domain network profiles.

---

## 20. Complete Project File Inventory

### Core Entrypoints & Configuration
- main.py: Application entrypoint; initializes database, launches Waitress and Flask servers, opens native pywebview window.
- pyproject.toml: Project package definition, dependencies, versioning (3.0.0), and tool configurations.
- config/__init__.py: Dynamic configuration module backed by SQLite app_settings.

### Application Package (app/)
- app/__init__.py: Flask application factory (create_app); registers blueprints, static routes, and error handlers.
- app/core.py: Thread-safe log queue and Server-Sent Events (SSE) streaming engine.
- app/database.py: Relational database abstraction layer; SQLite connection manager, schema DDL, and CRUD functions.
- app/folder_opener.py: Cross-platform utility for revealing files and folders in Windows Explorer.
- app/rate_limiter.py: In-memory sliding-window IP rate limiting middleware.
- app/utils.py: Security decorators (login_required, csrf_protect), network IP resolution utilities.
- app/routes/api.py: Primary administrative API routes (pipeline control, candidate management, CSV export, notes).
- app/routes/auth.py: Authentication routes (login, logout, session verification).
- app/routes/candidate.py: Public candidate interview portal routes on Port 5000.
- app/routes/intelligence.py: Talent Intelligence API routes (vector search, candidate comparison, feedback, analytics).
- app/routes/reports.py: PDF report viewing and file streaming routes.
- app/routes/settings.py: System configuration, AI provider setup, and email testing routes.
- app/routes/views.py: Front-end page rendering routes for the desktop dashboard.

### Processing Pipeline Modules (src/)
- src/common.py: Core paths resolver, centralized AI dispatcher (call_ollama), and atomic JSON utilities.
- src/ai_mode.py: Provider definition registry and execution mode selector.
- src/provider_router.py: Multi-provider router with RPM tracking, load balancing, and failover.
- src/security.py: Hardware-bound AES-Fernet encryption, key derivation, and PII purging logic.
- src/pdf_to_txt.py: Resume ingestion and text extraction (digital PDF, Word .docx, OCR).
- src/txt_to_nlp.py: Natural language processing and structured JSON candidate profile extraction.
- src/rank_candidates.py: Multi-criteria fit scoring, knockout filtering, and ranking leaderboard generator.
- src/schedule_candidates.py: Top-N shortlist isolation, slot allocation, and iCalendar generation.
- src/email_sender.py: Automated SMTP email dispatch with STARTTLS encryption and custom templates.
- src/google_calendar.py: Google Calendar API OAuth 2.0 integration and free/busy slot detection.
- src/generate_questions.py: Dynamic interview question generation with role blueprints and adaptive follow-up probing.
- src/proctoring.py: Real-time computer vision proctoring engine (MediaPipe, OpenCV) and anomaly scoring.
- src/voice_system.py: Offline text-to-speech and speech-to-text fallback engine.
- src/evaluate_interview.py: Interview transcript evaluation, rubric scoring, and 40/60 combined fit scoring.
- src/generate_reports.py: Standardized PDF evaluation report generation using FPDF2.
- src/talent_intelligence.py: Vector semantic embeddings, comparison matrix, and 6 talent analytics calculators.

### User Interface Assets (app/templates/ & app/static/)
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

### Automated Test Suite (tests/)
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

### Build & Utility Scripts (build/ & scripts/)
- build/build.spec: PyInstaller compilation specification.
- build/installer.iss: Inno Setup Windows installer build script.
- scripts/build_installer.bat: Automated batch script orchestrating PyInstaller and Inno Setup builds.
- scripts/setup_firewall.bat: Windows firewall helper script configuring Port 5000 inbound access.
- scripts/verify_providers.py: Standalone diagnostic utility testing connectivity across all configured AI providers.
