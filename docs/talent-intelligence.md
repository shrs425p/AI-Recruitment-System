# Talent Intelligence & Analytics

The Talent Intelligence subsystem provides semantic candidate discovery, structured candidate comparisons, automated personalized feedback generation, and six executive-level recruitment analytics modules.

---

## Architecture Overview

```
Resume Profiles (*_nlp.json) & Transcripts (interview_*.json)
                        │
                        ▼
           Talent Intelligence Engine
     ┌──────────────────┴──────────────────┐
     ▼                                     ▼
Semantic Discovery & Comparison     Recruitment Analytics Suite
- SQLite Vector Embeddings          1. Skill Supply vs Demand Gap
- Cosine Similarity Matching        2. Experience vs Score Matrix
- Multi-Candidate Comparison        3. Question Difficulty Breakdown
- AI Feedback Letter Generation     4. Proctoring Risk Distribution
                                    5. Hiring Velocity Tracker
                                    6. Education & Domain Mix
```

---

## 1. Semantic Vector Discovery

Unlike keyword-matching search engines that fail when candidates use alternative synonyms (e.g., "PostgreSQL" vs "relational database"), the Talent Intelligence engine builds high-dimensional semantic embeddings from candidate resumes and indexes them into SQLite.

### Indexing Engine (`index_talent_pool`)
- Scans `data/output/nlp/*_nlp.json` files and extracts composite text representations including candidate summary, technical skills, domain, and experience highlights.
- Computes dense vector embeddings using local Ollama embedding models (e.g. `nomic-embed-text` or `all-minilm`) with automatic fallbacks.
- Stores vector payloads into the `talent_embeddings` SQLite table.

### Semantic Search (`semantic_search_talent`)
- Computes cosine similarity between a natural-language query (e.g., *"Distributed caching and message queues in Python"*) and stored candidate vectors.
- Filters candidate skills against a schema keyword blocklist to prevent internal JSON keys (such as `technical_skills` or `tools_and_technologies`) from polluting search results.
- Returns ranked candidate profiles with matching scores, relevant experience snippets, and primary competencies.

---

## 2. Multi-Candidate Comparison Matrix

When evaluating finalists, hiring teams often need side-by-side technical trade-off analyses rather than isolated scores.

### Functionality (`compare_candidates_matrix`)
- Accepts a list of candidate names and an optional role context.
- Aggregates resume NLP profiles, ranking rubric breakdowns, and interview transcripts.
- Produces a multi-dimensional metric matrix:
  - Technical skills match percentage
  - Verified years of experience
  - Interview composite score
  - Proctoring integrity index
- Synthesizes an executive deliberation brief outlining the distinct trade-offs, strengths, and risk factors between the evaluated candidates.

---

## 3. Automated Candidate Feedback Letters

Rejected candidates rarely receive actionable technical feedback due to recruiter time constraints. The feedback generator automates constructive feedback communication.

### Functionality (`generate_candidate_feedback_letter`)
- Gathers candidate interview scores, strengths, gaps, and verbatim evaluation notes.
- Synthesizes a respectful, structured candidate feedback letter detailing:
  - Key technical strengths demonstrated during the interview
  - Conceptual or practical areas requiring further development
  - Recommended technical resources or study topics
- Incorporates deterministic template fallbacks if local or cloud AI generation times out, ensuring candidates always receive clean, professional communication.

---

## 4. Visual Talent Analytics Modules

The analytics suite computes six executive metrics directly from the local pipeline artifacts and SQLite database records without requiring external BI tools.

### Module 1: Skill Supply vs. Demand Gap Analytics
- **Objective:** Identifies talent surpluses and bottlenecks before spending weeks searching for rare skill combinations.
- **Computation:** Compares `required_skills` declared in the active Job Description against the aggregated frequency of skills found in all uploaded candidate resumes (`skills_flat`).
- **Insights:**
  - *Candidate Surplus:* e.g., "85% of applicants have Python and Git."
  - *Talent Bottleneck:* e.g., "Only 8% of applicants have Kubernetes or Kafka."

### Module 2: Experience vs. Score Quadrant Matrix
- **Objective:** Discovers high-potential junior talent and flags mismatched senior profiles.
- **Computation:** Plots Years of Experience (X-axis) against Total Fit Score (Y-axis) into four quadrants:
  - **High-Potential Rising Stars:** Low experience, high fit score.
  - **Seasoned Veterans:** High experience, high fit score.
  - **Entry Level / Needs Prep:** Low experience, low fit score.
  - **Mismatched Experience:** High experience, low fit score (skills outdated relative to role).

### Module 3: Interview Question Difficulty Breakdown
- **Objective:** Identifies which interview questions effectively filter top candidates and flags ambiguous questions.
- **Computation:** Groups all completed interview responses by question topic and computes the average score (0–10) and average response time (seconds).
- **Insights:**
  - Easy questions (>8.0 avg): useful for rapport and basics.
  - Effective filter questions (4.0–6.5 avg): cleanly separate top performers from average applicants.
  - Broken or misunderstood questions (<3.0 avg or excessive timeouts): candidate instructions need revision.

### Module 4: Proctoring Integrity & Risk Breakdown
- **Objective:** Provides an executive overview of test integrity across all completed candidate interviews.
- **Computation:** Aggregates proctoring logs and flags into risk tiers:
  - **Clean Sessions:** 0 flags.
  - **Low Warning:** 1–2 minor window blurs or brief face absences.
  - **High Risk:** Multiple faces detected, copy-paste answers, or excessive timeouts.
- Visualizes flag type distributions: Tab Switches, Face Absence, Copy-Paste Ingestion, and Response Delays.

### Module 5: Hiring Velocity & Bottleneck Tracker
- **Objective:** Measures pipeline turnaround velocity across recruitment stages.
- **Computation:** Calculates time intervals between:
  - `pipeline_runs.run_ts`: Resume upload to ranking completion.
  - `schedules.created_at`: Shortlist creation to invitation dispatch.
  - `interview_sessions.created_at`: Candidate starting and completing the interview.
- Displays metrics such as Average Time to Screen, Average Candidate Turnaround, and Final Report Generation Latency.

### Module 6: Education & Domain Talent Mix
- **Objective:** Delivers a demographic snapshot of applicant pool diversity and background.
- **Computation:** Tallies candidate domain distributions (Software Development, Cloud/DevOps, Data Science, etc.) and highest education degrees (Bachelor's, Master's, PhD, Diploma).

---

## 5. REST API Endpoints

All Talent Intelligence endpoints are authenticated and require valid HR session cookies and CSRF headers.

| Endpoint | Method | Description |
|---|---|---|
| `/api/intelligence/analytics` | `GET` | Returns aggregated data for all 6 visual analytics modules |
| `/api/intelligence/search` | `POST` | Executes semantic vector search against candidate talent pool |
| `/api/intelligence/compare` | `POST` | Generates side-by-side candidate comparison matrix and executive brief |
| `/api/intelligence/feedback-letter` | `POST` | Generates personalized candidate interview feedback letter |

### Example Analytics Response Structure
```json
{
  "success": true,
  "skill_gap": {
    "demand": ["Python", "Docker", "Kubernetes"],
    "supply": {"Python": 12, "Docker": 4, "Kubernetes": 1},
    "surpluses": ["Python"],
    "bottlenecks": ["Kubernetes"]
  },
  "experience_matrix": {
    "points": [
      {"name": "Alice Smith", "experience": 3.0, "score": 92.0, "quadrant": "Rising Star"},
      {"name": "Bob Jones", "experience": 8.0, "score": 54.0, "quadrant": "Mismatched"}
    ]
  },
  "question_difficulty": [
    {"topic": "System Architecture", "avg_score": 5.2, "avg_time_seconds": 94.0, "difficulty": "Hard"}
  ],
  "proctoring_risk": {
    "clean_percent": 80.0,
    "low_warning_percent": 15.0,
    "high_risk_percent": 5.0,
    "violation_counts": {"TAB_SWITCH": 4, "FACE_ABSENT": 2}
  },
  "hiring_velocity": {
    "avg_screen_hours": 0.25,
    "avg_turnaround_hours": 18.5
  },
  "talent_mix": {
    "domains": {"Software Engineering": 65, "DevOps": 25, "Other": 10},
    "education": {"Bachelors": 70, "Masters": 25, "PhD": 5}
  }
}
```
