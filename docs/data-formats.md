# Data Formats & Schemas

This document defines the database schemas, file system structures, and JSON/CSV data formats used across the application.

---

## 1. SQLite Database Schema

The database file is stored at `data/ars.db`. The transactional schema created and maintained by `app/database.py` contains the following relational tables:

```sql
-- 1. Pipeline Execution Runs
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    run_type   TEXT NOT NULL,
    run_date   TEXT NOT NULL DEFAULT (date('now')),
    run_ts     TEXT NOT NULL DEFAULT (datetime('now')),
    status     TEXT DEFAULT 'RUNNING',
    metadata   TEXT DEFAULT '{}'
);

-- 2. Candidates
CREATE TABLE IF NOT EXISTS candidates (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id       INTEGER NOT NULL REFERENCES pipeline_runs(id),
    name         TEXT NOT NULL,
    email        TEXT DEFAULT '',
    source_file  TEXT DEFAULT '',
    score        REAL DEFAULT 0,
    skills       TEXT DEFAULT '[]',
    created_at   TEXT DEFAULT (datetime('now'))
);

-- 3. Candidate Interview Schedules
CREATE TABLE IF NOT EXISTS schedules (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id         INTEGER NOT NULL REFERENCES pipeline_runs(id),
    candidate_name TEXT NOT NULL,
    job_title      TEXT DEFAULT '',
    rank           INTEGER DEFAULT 0,
    score          REAL DEFAULT 0,
    offered_slots  TEXT DEFAULT '[]',
    selected_slot  TEXT DEFAULT '',
    status         TEXT DEFAULT 'PENDING',
    email_sent     INTEGER DEFAULT 0,
    created_at     TEXT DEFAULT (datetime('now'))
);

-- 4. Outbound Email Dispatch Log
CREATE TABLE IF NOT EXISTS email_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id        INTEGER REFERENCES pipeline_runs(id),
    schedule_id   INTEGER REFERENCES schedules(id),
    recipient     TEXT NOT NULL,
    subject       TEXT DEFAULT '',
    status        TEXT DEFAULT 'SENT',
    error         TEXT DEFAULT '',
    sent_at       TEXT DEFAULT (datetime('now'))
);

-- 5. Candidate Access Tokens
CREATE TABLE IF NOT EXISTS interview_tokens (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    token           TEXT NOT NULL UNIQUE,
    candidate_name  TEXT NOT NULL,
    source_file     TEXT NOT NULL,
    job_title       TEXT DEFAULT '',
    rank            INTEGER DEFAULT 0,
    score           REAL DEFAULT 0,
    used            INTEGER DEFAULT 0,
    created_at      TEXT DEFAULT (datetime('now'))
);

-- 6. Job Description Templates
CREATE TABLE IF NOT EXISTS job_templates (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    jd_text     TEXT NOT NULL,
    created_at  TEXT DEFAULT (datetime('now'))
);

-- 7. Application Configuration Settings
CREATE TABLE IF NOT EXISTS app_settings (
    key          TEXT PRIMARY KEY,
    value        TEXT NOT NULL,
    is_encrypted INTEGER DEFAULT 0,
    updated_at   TEXT DEFAULT (datetime('now'))
);

-- 8. Live Candidate Interview Sessions
CREATE TABLE IF NOT EXISTS interview_sessions (
    session_id     TEXT PRIMARY KEY,
    token          TEXT NOT NULL,
    candidate_name TEXT NOT NULL,
    job_title      TEXT DEFAULT '',
    session_data   TEXT NOT NULL,
    created_at     REAL NOT NULL,
    updated_at     TEXT DEFAULT (datetime('now'))
);

-- 9. Talent Intelligence Vector Embeddings
CREATE TABLE IF NOT EXISTS candidate_embeddings (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_name TEXT NOT NULL UNIQUE,
    source_file    TEXT DEFAULT '',
    domain         TEXT DEFAULT '',
    skills_json    TEXT DEFAULT '[]',
    profile_text   TEXT DEFAULT '',
    vector_json    TEXT DEFAULT '[]',
    updated_at     TEXT DEFAULT (datetime('now'))
);

-- 10. AI Telemetry & Usage Monitoring
CREATE TABLE IF NOT EXISTS ai_telemetry (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    provider          TEXT NOT NULL,
    model             TEXT NOT NULL,
    prompt_tokens     INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    latency_seconds   REAL DEFAULT 0.0,
    status            TEXT DEFAULT 'SUCCESS',
    cost_usd          REAL DEFAULT 0.0,
    created_at        TEXT DEFAULT (datetime('now'))
);

-- 11. Candidate Feedback Records
CREATE TABLE IF NOT EXISTS candidate_feedback (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_name TEXT NOT NULL,
    email          TEXT DEFAULT '',
    job_title      TEXT DEFAULT '',
    feedback_text  TEXT NOT NULL,
    status         TEXT DEFAULT 'DRAFT',
    sent_at        TEXT,
    created_at     TEXT DEFAULT (datetime('now'))
);

-- 12. Candidate Notes and Tags
CREATE TABLE IF NOT EXISTS candidate_notes (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_name TEXT NOT NULL UNIQUE,
    source_file    TEXT DEFAULT '',
    note           TEXT DEFAULT '',
    tags           TEXT DEFAULT '',
    updated_at     TEXT DEFAULT (datetime('now'))
);

-- 13. Real-Time HR Notifications
CREATE TABLE IF NOT EXISTS hr_notifications (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    type           TEXT NOT NULL,
    title          TEXT NOT NULL,
    message        TEXT NOT NULL,
    candidate_name TEXT DEFAULT '',
    job_title      TEXT DEFAULT '',
    link           TEXT DEFAULT '',
    is_read        INTEGER DEFAULT 0,
    created_at     TEXT DEFAULT (datetime('now'))
);
```

---

## 2. Structured NLP Profile (`*_nlp.json`)

Saved to `data/output/nlp/{filename}_nlp.json`:

```json
{
  "personal_info": {
    "name": "Jane Doe",
    "email": "jane.doe@example.com",
    "phone": "+1-555-0199",
    "location": "San Francisco, CA",
    "linkedin": "https://linkedin.com/in/janedoe",
    "portfolio": "https://github.com/janedoe"
  },
  "domain": "Software Engineering",
  "summary": "Full-stack engineer with 6 years building distributed Python backends.",
  "total_experience_years": 6.0,
  "skills": {
    "technical_skills": ["Python", "FastAPI", "Go", "PostgreSQL"],
    "tools_and_technologies": ["Docker", "Kubernetes", "Redis", "Git"],
    "domain_specific_skills": ["Microservices", "Event-Driven Architecture"],
    "soft_skills": ["Team Leadership", "Code Review"]
  },
  "education": [
    {
      "degree": "Bachelor of Science",
      "field_of_study": "Computer Science",
      "institution": "University of California, Berkeley",
      "year": 2018
    }
  ],
  "work_experience": [
    {
      "job_title": "Senior Backend Engineer",
      "employer": "TechCorp",
      "start_date": "2021",
      "end_date": "Present",
      "description": "Led migration of monolithic services to event-driven microservices."
    }
  ],
  "certifications": [
    { "name": "AWS Certified Solutions Architect", "year": 2022 }
  ]
}
```

---

## 3. Candidate Ranking Scores (`ranking_scores_*.json`)

Saved to `data/output/ranking/ranking_scores_{job_title}_{timestamp}.json`:

```json
{
  "job_description": {
    "job_title": "Senior Backend Engineer",
    "domain": "Software Engineering",
    "required_skills": ["Python", "FastAPI", "Docker", "PostgreSQL"],
    "min_experience_years": 3.0
  },
  "applied_weights": {
    "skills_match": 35,
    "experience_years": 20,
    "domain_match": 20,
    "education": 15,
    "certifications": 10
  },
  "knockout_rules": {
    "min_experience_years": 3.0,
    "required_skills": ["Python"]
  },
  "ranked_candidates": [
    {
      "candidate_name": "Jane Doe",
      "email": "jane.doe@example.com",
      "total_score": 92.5,
      "percentage": 92.5,
      "hire_recommendation": "Strongly Recommend",
      "is_knocked_out": false,
      "scores": {
        "domain_match": { "score": 20, "max": 20, "reason": "Exact domain alignment" },
        "skills_match": { "score": 35, "max": 35, "reason": "All required skills present" },
        "experience_years": { "score": 20, "max": 20, "reason": "6 years exceeds requirement" },
        "education": { "score": 9, "max": 15, "reason": "Bachelor of Science" },
        "certifications": { "score": 8, "max": 10, "reason": "AWS Solutions Architect" }
      },
      "strengths": ["Strong distributed systems background", "Direct stack match"],
      "gaps": []
    }
  ]
}
```

---

## 4. RFC 4180 CSV Export Format

Generated via `GET /api/ranking/export/csv`:

```csv
Rank,Name,Email,Total Score,Skills Match,Experience Score,Strengths,Hire Recommendation
1,Jane Doe,jane.doe@example.com,92.5,35,20,"Python, FastAPI, Docker",Strongly Recommend
2,John Smith,john.smith@example.com,81.0,28,18,"Python, PostgreSQL",Recommend
```

---

## 5. Interview Transcript (`interview_*.json`)

Saved to `data/output/interviews/interview_{candidate_name}_{timestamp}.json`:

```json
{
  "candidate_name": "Jane Doe",
  "job_title": "Senior Backend Engineer",
  "total_score": 74,
  "max_score": 80,
  "percentage": 92.5,
  "technical_score": 46,
  "technical_max": 50,
  "behavioral_score": 28,
  "behavioral_max": 30,
  "proctoring_status": "Clean Session",
  "flagged_count": 0,
  "flags": [],
  "responses": [
    {
      "question_num": 1,
      "type": "TECHNICAL",
      "topic": "Microservices & Caching",
      "question": "How do you prevent cache stampedes in a high-concurrency Redis setup?",
      "answer": "We implemented distributed locking using Redis mutexes with randomized exponential backoff and probabilistic early cache expiration.",
      "evaluation": {
        "relevance": 3,
        "depth": 3,
        "clarity": 2,
        "correctness": 2,
        "total": 10,
        "feedback": "Comprehensive technical answer demonstrating practical concurrency experience.",
        "strong_points": ["Probabilistic early expiration", "Distributed mutex backoff"],
        "weak_points": []
      },
      "time_taken": 38.2,
      "proctor": {
        "flagged": false,
        "flags": []
      }
    }
  ]
}
```
