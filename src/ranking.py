# ranking.py — AI-Powered Resume Ranking Engine
#
# Scoring model (total /100):
#   Skills     40 pts  — semantic skill-group matching + JD cosine bonus
#   Domain     20 pts  — tiered fuzzy matching (not binary)
#   Experience 20 pts  — standardised bands
#   Education  15 pts  — degree tier
#   Certs       5 pts  — volume capped
#
# Additional outputs per candidate:
#   confidence    — High / Medium / Low  (data-completeness driven)
#   unique_id     — sha256 hash for deduplication
#   jd_similarity — 0-100 float (cosine overlap with job description)

import json
import logging
import asyncio
import hashlib
import re
import math
from pathlib import Path

from app.utils import call_ollama
from app.database import save_candidate, save_ranking

logger = logging.getLogger(__name__)

# ── Scoring weights (must sum to 100) ────────────────────────────────────────
SCORE_WEIGHTS = {
    "skills":     40,
    "domain":     20,
    "experience": 20,
    "education":  15,
    "certs":       5,
}

# ── Semantic skill groups ─────────────────────────────────────────────────────
# Matching any skill in a group counts as that group being "present".
# Groups are checked independently — a candidate can hit multiple groups.
SKILL_GROUPS: dict[str, list[str]] = {
    "machine_learning":   ["machine learning", "ml", "deep learning", "neural network",
                           "gradient boosting", "xgboost", "random forest", "svm",
                           "naive bayes", "logistic regression"],
    "nlp":                ["nlp", "natural language processing", "text mining",
                           "transformers", "bert", "gpt", "llm", "spacy", "nltk",
                           "sentiment analysis", "named entity recognition"],
    "computer_vision":    ["computer vision", "opencv", "image recognition",
                           "object detection", "yolo", "cnn", "image processing",
                           "mediapipe"],
    "dl_frameworks":      ["tensorflow", "pytorch", "keras", "jax", "mxnet",
                           "caffe", "theano"],
    "data_science":       ["data science", "data analysis", "statistics", "pandas",
                           "numpy", "scipy", "matplotlib", "seaborn", "tableau",
                           "power bi", "data visualization"],
    "programming":        ["python", "java", "c++", "c#", "javascript", "typescript",
                           "go", "rust", "scala", "r", "matlab", "julia"],
    "backend":            ["flask", "fastapi", "django", "node", "express", "spring",
                           "rest api", "graphql", "microservices", "grpc"],
    "cloud_devops":       ["aws", "azure", "gcp", "google cloud", "docker",
                           "kubernetes", "terraform", "ci/cd", "jenkins", "github actions",
                           "ansible", "devops"],
    "databases":          ["sql", "postgresql", "mysql", "mongodb", "redis",
                           "elasticsearch", "sqlite", "cassandra", "dynamodb",
                           "bigquery", "snowflake"],
    "mlops":              ["mlops", "mlflow", "kubeflow", "airflow", "dvc",
                           "model deployment", "model serving", "feature store",
                           "a/b testing", "experiment tracking"],
    "finance_accounting": ["accounting", "finance", "auditing", "taxation",
                           "financial analysis", "investment", "portfolio",
                           "risk management", "excel", "financial modelling"],
    "software_eng":       ["software development", "system design", "agile", "scrum",
                           "git", "version control", "unit testing", "tdd", "solid"],
}

# ── Domain tiers ──────────────────────────────────────────────────────────────
# Each tier is a list of fragments. Match is case-insensitive substring.
DOMAIN_TIERS: list[tuple[int, list[str]]] = [
    (20, ["artificial intelligence", "machine learning", "data science",
          "deep learning", "nlp", "computer vision", "ai/ml", " ai ", "ml"]),
    (15, ["data engineering", "data analytics", "business intelligence",
          "research", "robotics", "bioinformatics"]),
    (12, ["software", "software development", "computer science",
          "information technology", "it ", "devops", "cloud", "cybersecurity",
          "fullstack", "full stack", "backend", "frontend"]),
    (8,  ["electrical", "electronics", "mechanical", "civil", "physics",
          "mathematics", "statistics"]),
    (4,  ["business", "management", "mba", "marketing", "hr", "human resources",
          "finance", "accounting", "economics"]),
]


# ── Public API ────────────────────────────────────────────────────────────────

async def rank_candidates(nlp_dir: Path, job_description: str = "") -> list[dict]:
    """
    Load all NLP JSON results, deduplicate, and rank candidates by score.
    Returns a sorted list of result dicts (highest score first).
    """
    nlp_files = sorted(nlp_dir.glob("*.json"))
    if not nlp_files:
        logger.warning("No NLP files found in %s", nlp_dir)
        return []

    jd_tokens = _tokenize(job_description)

    tasks = [_score_candidate(f, job_description, jd_tokens) for f in nlp_files]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    seen_ids: set[str] = set()
    ranked: list[dict] = []
    dupes = 0

    for r in results:
        if isinstance(r, Exception):
            logger.error("Scoring error: %s", r)
            continue
        if not r:
            continue
        uid = r.get("unique_id", "")
        if uid and uid in seen_ids:
            logger.info("Skipping duplicate candidate: %s (id=%s)", r.get("name"), uid)
            dupes += 1
            continue
        if uid:
            seen_ids.add(uid)
        ranked.append(r)

    if dupes:
        logger.info("Deduplicated %d duplicate candidate(s)", dupes)
        print(f"  [INFO] Removed {dupes} duplicate resume(s) from ranking.")

    ranked.sort(key=lambda x: x["total_score"], reverse=True)
    return ranked


# ── Internal: per-candidate scoring ──────────────────────────────────────────

async def _score_candidate(nlp_path: Path, job_description: str,
                           jd_tokens: list[str]) -> dict | None:
    """Score a single candidate from their NLP JSON file."""
    try:
        with open(nlp_path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.error("Cannot read %s: %s", nlp_path, e)
        return None

    name       = data.get("name", "Unknown")
    skills     = data.get("skills", []) or []
    domain     = data.get("domain", "") or ""
    exp        = data.get("experience_years", 0)
    edu        = data.get("education", "") or ""
    certs      = data.get("certifications", []) or []
    summary    = data.get("summary", "") or ""

    # Build a stable unique ID for deduplication
    unique_id  = _make_unique_id(name, domain, skills)

    # Individual component scores
    s_skills    = _score_skills(skills, jd_tokens)
    s_domain    = _score_domain(domain)
    s_exp       = _score_experience(exp)
    s_edu       = _score_education(edu)
    s_certs     = _score_certs(certs)
    total       = s_skills + s_domain + s_exp + s_edu + s_certs

    # JD cosine similarity (bonus, logged separately — does not inflate total)
    resume_tokens  = _tokenize(" ".join([name, domain, edu, summary] + skills + certs))
    jd_similarity  = _cosine_similarity(resume_tokens, jd_tokens) if jd_tokens else 0.0

    # Data completeness → confidence level
    confidence = _confidence_level(name, skills, domain, edu, exp)

    # AI narrative explanation
    explanation = await _get_ai_explanation(data, total, job_description, confidence)

    result = {
        "unique_id":          unique_id,
        "name":               name,
        "file":               nlp_path.name,
        "skills":             skills,
        "domain":             domain,
        "experience":         exp,
        "education":          edu,
        "certifications":     certs,
        "score_skills":       s_skills,
        "score_domain":       s_domain,
        "score_experience":   s_exp,
        "score_education":    s_edu,
        "score_certs":        s_certs,
        "total_score":        total,
        "jd_similarity":      round(jd_similarity * 100, 1),
        "confidence":         confidence,
        "explanation":        explanation,
    }

    save_candidate(result)
    save_ranking(result)
    return result


# ── Scoring functions ─────────────────────────────────────────────────────────

def _score_skills(candidate_skills: list[str], jd_tokens: list[str]) -> int:
    """
    Score 0-40 using semantic skill-group matching.

    Strategy:
    - Normalize all candidate skills to lowercase.
    - For each SKILL_GROUP, check if any candidate skill substring-matches
      any keyword in the group. Count distinct groups matched.
    - If a JD is provided, weight groups that appear in the JD higher.
    - Score = (groups_matched / total_groups) * weight, capped at max.
    """
    if not candidate_skills:
        return 0

    lowered = [s.lower() for s in candidate_skills]

    # Which groups does the candidate hit?
    matched_groups: set[str] = set()
    for group_name, keywords in SKILL_GROUPS.items():
        for kw in keywords:
            if any(kw in skill or skill in kw for skill in lowered):
                matched_groups.add(group_name)
                break

    if not matched_groups:
        # Fallback: raw volume scoring if no groups matched
        ratio = min(len(candidate_skills) / 15, 1.0)
        return round(ratio * SCORE_WEIGHTS["skills"] * 0.6)

    if jd_tokens:
        # JD-weighted: groups that overlap with JD keywords score double
        jd_text = " ".join(jd_tokens)
        jd_matched = sum(
            1 for g in matched_groups
            if any(kw in jd_text for kw in SKILL_GROUPS[g])
        )
        # Blend: 60% JD-overlap, 40% raw breadth
        jd_ratio    = min(jd_matched / max(len(matched_groups), 1), 1.0)
        raw_ratio   = min(len(matched_groups) / len(SKILL_GROUPS), 1.0)
        final_ratio = 0.6 * jd_ratio + 0.4 * raw_ratio
    else:
        final_ratio = min(len(matched_groups) / len(SKILL_GROUPS), 1.0)

    return round(final_ratio * SCORE_WEIGHTS["skills"])


def _score_domain(domain: str) -> int:
    """
    Score 0-20 using tiered fuzzy domain matching.

    Tiers:
      20 pts — AI/ML/Data Science (exact match to target area)
      15 pts — Data Engineering, Research
      12 pts — Software/IT/Cloud
       8 pts — STEM (Electrical, Physics, Math)
       4 pts — Business/Finance/HR
       0 pts — No domain or no match
    """
    if not domain:
        return 0
    d = domain.lower()
    for score, keywords in DOMAIN_TIERS:
        if any(kw in d for kw in keywords):
            return score
    return 0


def _score_experience(years) -> int:
    """
    Score 0-20 using standardised experience bands.

    Bands:
      0 yrs / not mentioned → 10  (fresher, not penalised)
      0–2 yrs               → 14
      2–5 yrs               → 18
      5+ yrs                → 20
    """
    try:
        y = float(years)
    except (TypeError, ValueError):
        return 10  # unknown — treat as fresher

    if y == 0:
        return 10
    elif y < 2:
        return 14
    elif y < 5:
        return 18
    else:
        return 20


def _score_education(edu: str) -> int:
    """
    Score 0-15 based on highest detected degree.

    PhD        → 15
    Masters    → 12
    Bachelors  → 9
    Diploma    → 5
    Present    → 3
    None       → 0
    """
    if not edu:
        return 0
    e = edu.lower()
    if any(k in e for k in ["phd", "doctorate", "ph.d"]):
        return 15
    if any(k in e for k in ["master", "msc", "m.tech", "mba", "ms ", "m.s", "m.e"]):
        return 12
    if any(k in e for k in ["bachelor", "b.tech", "b.e.", "bsc", "be ", "b.sc", "b.e",
                             "b.s.", "undergraduate", "ug "]):
        return 9
    if any(k in e for k in ["diploma", "associate", "higher secondary", "polytechnic"]):
        return 5
    return 3


def _score_certs(certs: list) -> int:
    """Score 0-5 based on certification count (capped)."""
    if not certs:
        return 0
    return min(len(certs) * 2, SCORE_WEIGHTS["certs"])


# ── Confidence & deduplication helpers ───────────────────────────────────────

def _confidence_level(name: str, skills: list, domain: str,
                       edu: str, exp) -> str:
    """
    Assess how complete/reliable the extracted data is.

    High   — name + skills (3+) + domain + education all present
    Medium — name + skills present, at least one of domain/education
    Low    — sparse data (missing multiple key fields)
    """
    score = 0
    if name and name.lower() not in ("unknown", "null", "none", ""):
        score += 1
    if skills and len(skills) >= 3:
        score += 1
    if domain:
        score += 1
    if edu:
        score += 1
    try:
        if float(exp) > 0:
            score += 1
    except (TypeError, ValueError):
        pass

    if score >= 4:
        return "High"
    elif score >= 2:
        return "Medium"
    else:
        return "Low"


def _make_unique_id(name: str, domain: str, skills: list[str]) -> str:
    """
    Create a stable hash to detect duplicate resumes.
    Uses name + domain + first 5 sorted skills.
    """
    key_parts = [
        (name or "").lower().strip(),
        (domain or "").lower().strip(),
        *sorted(s.lower().strip() for s in (skills or [])[:5]),
    ]
    key = "|".join(key_parts)
    return hashlib.sha256(key.encode()).hexdigest()[:16]


# ── Cosine similarity (TF-IDF style, no external deps) ───────────────────────

def _tokenize(text: str) -> list[str]:
    """Lowercase, strip punctuation, split into tokens (2+ chars)."""
    if not text:
        return []
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return [t for t in text.split() if len(t) >= 2]


def _cosine_similarity(tokens_a: list[str], tokens_b: list[str]) -> float:
    """
    Compute TF-IDF cosine similarity between two token lists.
    Returns a float 0.0 – 1.0.
    """
    if not tokens_a or not tokens_b:
        return 0.0

    def tf(tokens: list[str]) -> dict[str, float]:
        counts: dict[str, int] = {}
        for t in tokens:
            counts[t] = counts.get(t, 0) + 1
        total = len(tokens)
        return {t: c / total for t, c in counts.items()}

    tf_a = tf(tokens_a)
    tf_b = tf(tokens_b)

    vocab = set(tf_a) | set(tf_b)
    dot   = sum(tf_a.get(t, 0) * tf_b.get(t, 0) for t in vocab)
    mag_a = math.sqrt(sum(v ** 2 for v in tf_a.values()))
    mag_b = math.sqrt(sum(v ** 2 for v in tf_b.values()))

    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


# ── AI explanation ────────────────────────────────────────────────────────────

async def _get_ai_explanation(candidate: dict, score: int,
                               jd: str, confidence: str) -> dict:
    """Use LLM to generate a structured hire/no-hire recommendation."""
    prompt = f"""You are a senior HR analyst. Evaluate this candidate profile.

Candidate:
- Name: {candidate.get("name", "Unknown")}
- Domain: {candidate.get("domain", "N/A")}
- Skills: {", ".join((candidate.get("skills") or [])[:15])}
- Experience: {candidate.get("experience_years", "N/A")} years
- Education: {candidate.get("education", "N/A")}
- Certifications: {", ".join((candidate.get("certifications") or [])[:5])}
- System Score: {score}/100
- Data Confidence: {confidence}

Job Requirements: {jd[:300] if jd else "General AI/ML Engineering role"}

Respond with ONLY this JSON (no markdown, no extra text):
{{
  "summary": "2-sentence overall assessment",
  "strengths": ["strength1", "strength2", "strength3"],
  "gaps": ["gap1", "gap2"],
  "recommendation": "Strong Hire / Hire / Maybe / No Hire",
  "confidence": "{confidence}"
}}"""

    try:
        raw = await call_ollama(prompt, max_tokens=400)
        clean = raw.strip()
        if clean.startswith("```"):
            clean = "\n".join(clean.split("\n")[1:])
            if clean.endswith("```"):
                clean = clean[:-3].strip()
        parsed = json.loads(clean)
        # Ensure confidence always reflects the data-completeness value
        parsed["confidence"] = confidence
        return parsed
    except Exception as e:
        logger.warning("AI explanation failed for %s: %s",
                        candidate.get("name"), e)
        top_skills = (candidate.get("skills") or [])[:3]
        return {
            "summary": (
                f"Candidate scored {score}/100 based on skills, domain, "
                f"experience, and education. Data confidence is {confidence}."
            ),
            "strengths": top_skills if top_skills else ["Resume submitted"],
            "gaps": ["Insufficient data for detailed analysis"] if confidence == "Low" else [],
            "recommendation": (
                "Strong Hire" if score >= 75
                else "Hire"   if score >= 60
                else "Maybe"  if score >= 40
                else "No Hire"
            ),
            "confidence": confidence,
        }
