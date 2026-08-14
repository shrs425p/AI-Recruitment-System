# Data Formats

This document describes the exact structure of every JSON file the system produces. Understanding these formats is useful if you want to read output files programmatically, build integrations, or debug pipeline stages.

---

## NLP Output — `*_nlp.json`

**Location:** `%LOCALAPPDATA%\AI Recruitment System\data\output\nlp\`  
**Produced by:** `src/nlp_extractor.py`  
**Used by:** `src/ranking_engine.py`

```json
{
  "personal_info": {
    "name": "John Doe",
    "email": "john@example.com",
    "phone": "+91 98765 43210",
    "location": "Bangalore, India",
    "linkedin": "linkedin.com/in/johndoe",
    "portfolio_or_github": "github.com/johndoe"
  },
  "domain": "Software Engineering",
  "summary": "Experienced backend developer with 4 years in Python and distributed systems.",
  "total_experience_years": 4,
  "skills": {
    "technical_skills": ["Python", "FastAPI", "PostgreSQL", "Docker"],
    "tools_and_technologies": ["Git", "Redis", "Kubernetes", "AWS"],
    "soft_skills": ["Communication", "Problem Solving", "Team Leadership"],
    "domain_specific_skills": ["REST API Design", "Microservices", "CI/CD"],
    "languages_known": ["English", "Hindi"]
  },
  "education": [
    {
      "degree": "B.Tech",
      "field_of_study": "Computer Science",
      "institution": "IIT Bangalore",
      "year_of_completion": "2020",
      "grade_or_cgpa": "8.4"
    }
  ],
  "work_experience": [
    {
      "job_title": "Backend Engineer",
      "company": "TechCorp India",
      "start_date": "Jun 2020",
      "end_date": "Present",
      "duration": "4 years",
      "responsibilities": [
        "Designed and maintained REST APIs serving 1M+ daily requests",
        "Led migration from monolith to microservices"
      ],
      "achievements": [
        "Reduced API latency by 40% through caching layer redesign"
      ]
    }
  ],
  "projects": [
    {
      "title": "Real-time Analytics Dashboard",
      "description": "Built a streaming data pipeline using Kafka and ClickHouse for real-time metrics.",
      "technologies_used": ["Kafka", "ClickHouse", "Python", "React"],
      "outcome": "Reduced report generation time from 10 minutes to under 5 seconds"
    }
  ],
  "certifications": [
    {
      "name": "AWS Certified Solutions Architect",
      "issuer": "Amazon",
      "year": "2022"
    }
  ],
  "awards_and_achievements": [
    "Best Performer Q3 2022 — TechCorp India"
  ],
  "publications_or_research": [],
  "volunteer_or_extracurricular": [
    "Technical blogger — 5K+ monthly readers"
  ],
  "languages": ["English", "Hindi"],
  "candidate_strength_summary": "Strong backend engineer with proven experience in high-traffic systems, cloud infrastructure, and API design. Particularly strong in Python ecosystem."
}
```

**Notes:**
- Any field the AI cannot find is set to `null` (numbers) or `[]` (lists) or `""` (strings)
- `personal_info.name` falls back to `CANDIDATE_UNKNOWN_{filename}` if the AI cannot find a name
- `_source_file` (the filename stem) is added when this file is loaded by `ranking_engine.py`
- A companion `*_nlp.txt` human-readable summary is also generated in the same folder

---

## Ranking Output — `ranking_scores_<timestamp>.json`

**Location:** `%LOCALAPPDATA%\AI Recruitment System\data\output\ranking\`  
**Produced by:** `src/ranking_engine.py`

```json
{
  "job_title": "Senior Python Developer",
  "jd_summary": {
    "job_title": "Senior Python Developer",
    "domain": "Software Engineering",
    "required_experience_years": 4,
    "required_education": "Bachelors in Computer Science or related field",
    "required_skills": ["Python", "FastAPI", "PostgreSQL", "Docker"],
    "preferred_skills": ["Kubernetes", "AWS", "Redis"],
    "required_certifications": [],
    "job_summary": "We are looking for a senior backend developer..."
  },
  "ranked_candidates": [
    {
      "candidate_name": "John Doe",
      "total_score": 84,
      "percentage": 84,
      "overall_verdict": "Strong candidate with directly relevant skills and solid experience.",
      "hire_recommendation": "Strongly Recommend",
      "strengths": ["4 years Python experience", "AWS certified", "Microservices background"],
      "gaps": ["No PostgreSQL certification mentioned"],
      "scores": {
        "domain_match": {
          "score": 18,
          "max": 20,
          "reason": "Direct domain match — Software Engineering for a Python backend role."
        },
        "skills_match": {
          "score": 30,
          "max": 35,
          "reason": "80%+ of required skills present including Python, FastAPI, Docker, PostgreSQL."
        },
        "experience_years": {
          "score": 18,
          "max": 20,
          "reason": "4 years of directly relevant backend experience."
        },
        "education": {
          "score": 9,
          "max": 15,
          "reason": "B.Tech in Computer Science from a reputable institution."
        },
        "certifications": {
          "score": 6,
          "max": 10,
          "reason": "1 relevant certification (AWS Solutions Architect)."
        }
      },
      "_source_file": "john_doe_nlp",
      "_dedup_id": "a3f8b21c"
    }
  ],
  "generated_at": "2026-08-14T15:00:00"
}
```

**Notes:**
- Candidates are sorted by `total_score` descending — index 0 is the top candidate
- `_dedup_id` is a 16-char SHA-256 hash used to detect duplicate resumes
- A `leaderboard_<timestamp>.json` file is also produced with a simplified list (name + score only)

---

## Schedule Output — `schedule_<timestamp>.json`

**Location:** `%LOCALAPPDATA%\AI Recruitment System\data\output\scheduling\`  
**Produced by:** `src/scheduling.py`

```json
{
  "job_title": "Senior Python Developer",
  "generated_at": "2026-08-14T16:00:00",
  "hr_slots": [
    "2026-08-20 10:00",
    "2026-08-20 14:00",
    "2026-08-21 09:00"
  ],
  "schedule": [
    {
      "rank": 1,
      "candidate_name": "John Doe",
      "email": "john@example.com",
      "score": 84,
      "hire_recommendation": "Strongly Recommend",
      "offered_slots": [
        "2026-08-20 10:00",
        "2026-08-20 14:00",
        "2026-08-21 09:00"
      ],
      "selected_slot": "2026-08-20 10:00",
      "status": "CONFIRMED",
      "token": "550e8400-e29b-41d4-a716-446655440000",
      "ics_file": "john_doe_interview.ics",
      "source_file": "john_doe_nlp"
    }
  ]
}
```

**Candidate status values:**
| Status | Meaning |
|---|---|
| `SCHEDULED` | Slots offered, awaiting confirmation |
| `CONFIRMED` | Candidate confirmed their slot |
| `COMPLETED` | Interview finished |
| `CANCELLED` | Interview cancelled |

---

## Interview Transcript — `interview_<name>_<timestamp>.json`

**Location:** `%LOCALAPPDATA%\AI Recruitment System\data\output\interviews\`  
**Produced by:** `src/interview_bot.py` / `app/routes/interview.py`

```json
{
  "session_id": "abc123-...",
  "candidate_name": "John Doe",
  "job_title": "Senior Python Developer",
  "source_file": "john_doe_nlp",
  "started_at": "2026-08-20T10:05:00",
  "completed_at": "2026-08-20T10:47:00",
  "mode": "text",
  "responses": [
    {
      "question_number": 1,
      "question_type": "technical",
      "topic": "Python",
      "difficulty": "medium",
      "question": "How would you implement rate limiting in a FastAPI application?",
      "answer": "I would use a combination of Redis and a token bucket algorithm...",
      "score": 8,
      "max_score": 10,
      "feedback": "Excellent answer. Correctly identifies Redis as a distributed store and explains the token bucket algorithm clearly.",
      "answer_time_seconds": 67
    },
    {
      "question_number": 6,
      "question_type": "behavioral",
      "topic": "Teamwork",
      "question": "Describe a situation where you had to resolve a conflict within your team.",
      "answer": "During a sprint at TechCorp, two developers disagreed on the architecture...",
      "score": 7,
      "max_score": 10,
      "feedback": "Good use of STAR format. Could have elaborated more on the measurable outcome.",
      "answer_time_seconds": 89
    }
  ],
  "proctor_summary": {
    "webcam_available": true,
    "total_checks": 23,
    "no_face_events": 1,
    "multi_face_events": 0,
    "tab_switches": 2,
    "copy_paste_events": 0,
    "total_flags": 3,
    "risk_level": "Low"
  },
  "overall_score": 72,
  "max_possible_score": 80,
  "percentage": 90
}
```

---

## AI Report Output — `report_<name>_<timestamp>.json`

**Location:** `%LOCALAPPDATA%\AI Recruitment System\data\output\reports\`  
**Produced by:** `src/report_generator.py` (JSON version, before PDF generation)

```json
{
  "candidate_name": "John Doe",
  "overall_summary": "John demonstrated strong technical competence across all domains tested...",
  "technical_assessment": "Scored 7.5/10 on average for technical questions. Particular strength in Python internals and system design.",
  "behavioral_assessment": "Solid STAR-format responses. Communication is clear and structured.",
  "key_strengths": [
    "Deep Python knowledge",
    "Clear communication style",
    "Relevant AWS experience"
  ],
  "key_gaps": [
    "Limited mention of testing practices",
    "No experience with PostgreSQL at scale"
  ],
  "proctoring_remarks": "Two minor tab-switch events recorded. One brief face absence. Overall integrity appears good.",
  "risk_level": "Low",
  "combined_score": 85,
  "hire_recommendation": "Recommend",
  "hire_justification": "Strong technical fit with demonstrated experience directly relevant to the role.",
  "suggested_next_steps": [
    "Schedule a follow-up technical round with the engineering team",
    "Request a code sample or GitHub portfolio review"
  ]
}
```

---

## Token Record (in database)

Tokens are stored in the `app_settings` table as a JSON blob under the key `interview_tokens`.

Each token entry:
```json
{
  "token": "550e8400-e29b-41d4-a716-446655440000",
  "candidate_name": "John Doe",
  "job_title": "Senior Python Developer",
  "source_file": "john_doe_nlp",
  "created_at": "2026-08-14T16:00:00",
  "used": false
}
```
